"""Session-only credentials. No key files or OS-wide environment mutation."""
import os

ENV_KEYS={'openai':('OVERMIND_OPENAI_API_KEY','OPENAI_API_KEY'),
          'anthropic':('OVERMIND_ANTHROPIC_API_KEY','ANTHROPIC_API_KEY')}
_session={}

def register(kind,key):
    if kind not in ENV_KEYS: raise ValueError('Unknown credential provider.')
    if key:
        if len(key)>4096 or any(c.isspace() for c in key): raise ValueError('Invalid API credential format.')
        _session[kind]=key
    else: _session.pop(kind,None)

def credential(kind):
    key=_session.get(kind) or next((os.environ[n] for n in ENV_KEYS[kind] if os.environ.get(n)),None)
    if not key: raise ValueError(f'No {kind} API credential. Enter a session key or set {ENV_KEYS[kind][-1]}.')
    if len(key)>4096 or any(c.isspace() for c in key):raise ValueError('Invalid API credential format.')
    return key

def worker_environment(kind):
    env=dict(os.environ)
    # Only the selected mentor credential is inherited by the worker.
    for names in ENV_KEYS.values():
        for name in names:env.pop(name,None)
    if kind in ENV_KEYS:env[ENV_KEYS[kind][0]]=credential(kind)
    return env

def redact(value):
    keys=set(_session.values()) | {os.environ[n] for names in ENV_KEYS.values() for n in names if os.environ.get(n)}
    if isinstance(value,str):
        for key in sorted(keys,key=len,reverse=True):value=value.replace(key,'[REDACTED]')
        return value
    if isinstance(value,dict):return {redact(k):redact(v) for k,v in value.items()}
    if isinstance(value,list):return [redact(v) for v in value]
    if isinstance(value,tuple):return [redact(v) for v in value]
    return value

def reject_secrets(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if str(key).lower() in ('api_key','apikey','authorization','password','secret','access_token','credential','credentials'):
                raise ValueError('Credentials must be session-only or environment variables, never configuration fields.')
            reject_secrets(item)
