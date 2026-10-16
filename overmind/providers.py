"""Provider boundary: local Ollama and local OpenAI-compatible engines, interchangeable roles.
No commercial SDK dependency and no remote network or paid requests in v0.1.
"""
import ipaddress
import json
import urllib.request
import urllib.parse

class LocalProvider:
    def __init__(self, kind, url, model):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'http' or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Use an http:// loopback endpoint without credentials or query parameters.')
        # IP literals avoid DNS rebinding; localhost is normalized before connecting.
        host = parsed.hostname
        if host == 'localhost': host = '127.0.0.1'
        try:
            if not ipaddress.ip_address(host).is_loopback: raise ValueError()
        except ValueError:
            raise ValueError('Only loopback inference endpoints are enabled. Paid/cloud usage is disabled.')
        port = parsed.port
        authority = f'[{host}]' if ':' in host else host
        if port: authority += f':{port}'
        self.url = urllib.parse.urlunsplit(('http',authority,parsed.path.rstrip('/'),'',''))
        if kind not in ('ollama','compatible'): raise ValueError('Unknown provider.')
        if not isinstance(model,str) or not model.strip() or len(model)>200: raise ValueError('Enter a model name.')
        self.kind, self.model = kind, model

    def request(self, route, body=None):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                raise ValueError('Inference endpoint redirects are forbidden.')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        req = urllib.request.Request(self.url+route, None if body is None else json.dumps(body).encode(), {'Content-Type':'application/json'})
        with opener.open(req, timeout=30) as response:
            raw = response.read(2_000_001)
            if len(raw)>2_000_000: raise ValueError('Provider response exceeds 2 MB.')
            return json.loads(raw)

    def inspect(self):
        if self.kind == 'ollama':
            r = self.request('/api/show',{'model':self.model})
            return {k:r.get(k) for k in ('details','model_info','capabilities','license')}
        r = self.request('/v1/models')
        ids = [x['id'] for x in r.get('data',[])]
        if self.model not in ids: raise ValueError(f'Model not listed by endpoint. Available: {ids}')
        return {'model':self.model,'architecture':'Not exposed by compatible endpoint','available':ids}

    def generate(self, system, prompt, max_tokens=512):
        if len(system)+len(prompt)>24000: raise ValueError('Context exceeds laboratory input cap.')
        if self.kind == 'ollama':
            r = self.request('/api/generate', {'model':self.model,'system':system,'prompt':prompt,'stream':False,'keep_alive':0,
                'options':{'temperature':0,'seed':42,'num_predict':max_tokens,'num_ctx':8192}})
            answer = r['response']
        else:
            r = self.request('/v1/chat/completions',{'model':self.model,'messages':[{'role':'system','content':system},{'role':'user','content':prompt}], 'temperature':0,'max_tokens':max_tokens})
            answer = r['choices'][0]['message']['content']
        if not isinstance(answer,str) or len(answer)>16000: raise ValueError('Invalid provider text response.')
        return answer

def provider(config):
    return LocalProvider(config['kind'],config['url'],config['model'])

def json_reply(text):
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n',1)[1].rsplit('```',1)[0]
    result = json.loads(text)
    if not isinstance(result,dict): raise ValueError('Mentor must return a JSON object.')
    return result
