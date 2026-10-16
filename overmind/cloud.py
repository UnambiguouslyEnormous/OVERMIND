"""Official cloud mentor APIs. No implicit retries, redirects, proxy use, or paid probes."""
import json
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation

from .security import credential
from .mentor import ProposalError

class ProviderError(ValueError): pass
class BudgetExceeded(ValueError): pass
class TruncatedResponse(ProviderError):
    category = 'truncated_response'


def cloud_limits(value):
    if not isinstance(value,dict) or value.get('authorized') is not True or value.get('data_sharing') is not True:
        raise ValueError('Cloud mentoring requires explicit paid-use and dataset-sharing authorization.')
    if set(value)-{'authorized','data_sharing','budget_usd','input_usd_per_million','output_usd_per_million','max_output_tokens'}:raise ValueError('Unknown cloud spending configuration fields.')
    result=dict(value)
    for key in ('budget_usd','input_usd_per_million','output_usd_per_million'):
        try:d=Decimal(str(value.get(key)))
        except InvalidOperation:raise ValueError(f'Configure {key} with a positive finite amount.') from None
        if not d.is_finite() or d<=0 or d>100000:raise ValueError(f'Configure {key} between 0 and 100000.')
        result[key]=str(d)
    if Decimal(result['budget_usd'])<Decimal('.000001'):raise ValueError('Budget must be at least one microdollar.')
    cap=value.get('max_output_tokens',2048)
    if type(cap) is not int or not 256<=cap<=8192:raise ValueError('Cloud output cap must be 256–8192 tokens.')
    result['max_output_tokens']=cap
    return result

class CloudProvider:
    def __init__(self,kind,model):
        if kind not in ('openai','anthropic'):raise ValueError('Unknown cloud provider.')
        if not isinstance(model,str) or not 1<=len(model)<=200 or any(c.isspace() for c in model):raise ValueError('Select a valid mentor model ID.')
        self.kind,self.model=kind,model
        self.url='https://api.openai.com' if kind=='openai' else 'https://api.anthropic.com'
        self.last_usage=None
        self.reservation=None
        self._dispatch_active=False
        self.proposal_schema=None

    def request(self,route,body=None):
        if body is not None and not self._dispatch_active:raise ProviderError('Cloud generation requires an authorized experiment reservation.')
        key=credential(self.kind)
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):raise ProviderError('Cloud redirects are forbidden.')
        headers={'Content-Type':'application/json','Accept':'application/json'}
        if self.kind=='openai':headers['Authorization']='Bearer '+key
        else:headers.update({'x-api-key':key,'anthropic-version':'2023-06-01'})
        req=urllib.request.Request(self.url+route,None if body is None else json.dumps(body).encode(),headers)
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        try:
            with opener.open(req,timeout=30) as response:
                raw=response.read(2_000_001)
                if len(raw)>2_000_000:raise ProviderError('Cloud response exceeds the 2 MB limit.')
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            # Never log response bodies, headers, request objects, or server-reflected credentials.
            status=e.code;e.close()
            message={400:'Request or selected model is unsupported.',401:'Authentication failed; check the session API key.',
                     403:'API key lacks access.',404:'Model or endpoint is unavailable.',429:'Rate or account quota limit reached; no automatic retry.'}.get(status,'Provider request failed; no automatic retry.')
            raise ProviderError(f'{self.kind} HTTP {status}: {message}') from None
        except (urllib.error.URLError,TimeoutError,OSError):
            raise ProviderError(f'{self.kind} connection failed or timed out; reservation retained. Check connectivity.') from None
        except (json.JSONDecodeError,UnicodeError):raise ProviderError('Cloud provider returned invalid JSON.') from None

    def models(self):
        result=[];route='/v1/models'
        for _ in range(10):
            reply=self.request(route)
            for row in reply.get('data',[]):
                if isinstance(row,dict) and isinstance(row.get('id'),str):result.append(row['id'])
            if self.kind!='anthropic' or not reply.get('has_more'):return sorted(set(result))
            from urllib.parse import quote
            cursor=reply.get('last_id')
            if not isinstance(cursor,str):raise ProviderError('Invalid models pagination.')
            route='/v1/models?after_id='+quote(cursor,safe='')
        raise ProviderError('Model listing exceeded 10 pages. Enter an explicit model ID.')

    def inspect(self):
        ids=self.models()
        if self.model not in ids:raise ProviderError('Selected model is not accessible with this API key. Refresh model discovery.')
        return {'provider':self.kind,'model':self.model,'authenticated':True,'inference_tested':False,
                'notice':'Metadata connection succeeds; generation compatibility is tested by the authorized experiment.'}

    def payload(self,system,prompt,max_tokens):
        if not isinstance(system,str) or not isinstance(prompt,str) or len(system)+len(prompt)>24000:raise ValueError('Cloud context exceeds the laboratory input cap.')
        if type(max_tokens) is not int or not 1<=max_tokens<=8192:raise ValueError('Invalid output token cap.')
        if self.kind=='openai':
            body={'model':self.model,'instructions':system,'input':prompt,'max_output_tokens':max_tokens,'store':False}
            if self.proposal_schema:
                body['text']={'format':{'type':'json_schema','name':'overmind_proposal','strict':True,'schema':self.proposal_schema}}
            return '/v1/responses',body
        body={'model':self.model,'system':system,'messages':[{'role':'user','content':prompt}],'max_tokens':max_tokens}
        if self.proposal_schema:body['output_config']={'format':{'type':'json_schema','schema':self.proposal_schema}}
        return '/v1/messages',body

    def generate(self,system,prompt,max_tokens=512):
        route,body=self.payload(system,prompt,max_tokens)
        if not self.reservation:raise ProviderError('Cloud generation requires an authorized experiment reservation.')
        self.reservation=None
        self.last_usage=None
        self._dispatch_active=True
        try:reply=self.request(route,body)
        finally:self._dispatch_active=False
        usage=reply.get('usage',{})
        i,o=usage.get('input_tokens'),usage.get('output_tokens')
        if type(i) is not int or type(o) is not int or i<0 or o<0:raise ProviderError('Missing or invalid provider token usage; reservation retained.')
        if self.kind=='anthropic':
            for field in ('cache_creation_input_tokens','cache_read_input_tokens'):
                n=usage.get(field,0)
                if type(n) is not int or n<0:raise ProviderError('Invalid provider cache usage.')
                i+=n
        self.last_usage={'input_tokens':i,'output_tokens':o}
        if self.kind=='openai':
            if reply.get('status')=='incomplete' and (reply.get('incomplete_details') or {}).get('reason')=='max_output_tokens':
                raise TruncatedResponse('Mentor response reached the output token cap; return a shorter complete proposal. The configured cap is unchanged.')
            if reply.get('status')!='completed':raise ProviderError('Cloud generation incomplete or refused; increase output cap within budget or select another model.')
            answer=''.join(part.get('text','') for item in reply.get('output',[]) if item.get('type')=='message'
                for part in item.get('content',[]) if part.get('type')=='output_text')
        else:
            if reply.get('stop_reason')=='max_tokens':
                raise TruncatedResponse('Mentor response reached the output token cap; return a shorter complete proposal. The configured cap is unchanged.')
            if reply.get('stop_reason')!='end_turn':raise ProviderError('Claude generation did not complete; increase output cap within budget or select another model.')
            answer=''.join(item.get('text','') for item in reply.get('content',[]) if item.get('type')=='text')
        if not answer.strip():
            refused=self.kind=='openai' and any(part.get('type')=='refusal' for item in reply.get('output',[]) if item.get('type')=='message' for part in item.get('content',[]))
            if refused:raise ProviderError('Mentor refused the proposal request; no corrective retry. Review the objective and provider policy.')
            raise ProposalError('empty_response','Mentor returned no proposal text; return the complete JSON proposal.')
        if len(answer)>16000:raise ProposalError('oversized_response','Mentor response exceeds 16000 characters; return a concise complete proposal.')
        return answer
