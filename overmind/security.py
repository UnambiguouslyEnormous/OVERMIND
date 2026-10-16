"""Session-only authentication, output redaction, and process isolation helpers."""
import contextlib
import os
import sys
from .secret_patterns import PROVIDER_KEY, BEARER, secret_field

ENV_KEYS={'openai':('OVERMIND_OPENAI_API_KEY','OPENAI_API_KEY'),
          'anthropic':('OVERMIND_ANTHROPIC_API_KEY','ANTHROPIC_API_KEY')}
_session={}
_redaction_keys=set()
_blocked=set()


def _remember_environment():
    _redaction_keys.update(os.environ[n] for names in ENV_KEYS.values() for n in names if os.environ.get(n))


def register(kind,key):
    if kind not in ENV_KEYS: raise ValueError('Unknown credential provider.')
    _remember_environment()
    if _session.get(kind): _redaction_keys.add(_session[kind])
    if key:
        if len(key)>4096 or any(c.isspace() for c in key): raise ValueError('Invalid API credential format.')
        _redaction_keys.add(key);_session[kind]=key
    else: _session.pop(kind,None)
    _blocked.discard(kind)


def clear_credentials(kind=None):
    """Clear authentication without changing the user's environment or provider keys."""
    if kind is not None and kind not in ENV_KEYS:raise ValueError('Unknown credential provider.')
    _remember_environment()
    for selected in ([kind] if kind else ENV_KEYS):
        if _session.get(selected):_redaction_keys.add(_session.pop(selected))
        _blocked.add(selected)


def credential(kind):
    _remember_environment()
    if kind in _blocked:raise ValueError('Session credentials cleared. Enter a session key or restart to use environment credentials.')
    key=_session.get(kind) or next((os.environ[n] for n in ENV_KEYS[kind] if os.environ.get(n)),None)
    if not key: raise ValueError(f'No {kind} API credential. Enter a session key or set {ENV_KEYS[kind][-1]}.')
    if len(key)>4096 or any(c.isspace() for c in key):raise ValueError('Invalid API credential format.')
    _redaction_keys.add(key)
    return key


def subprocess_environment():
    """Allowlist ordinary runtime settings; never inherit the full environment."""
    allowed={'PATH','HOME','USER','LOGNAME','LANG','TZ','TMPDIR','SSL_CERT_FILE','SSL_CERT_DIR',
             'PYTHONUTF8','PYTHONIOENCODING','PYTHONDONTWRITEBYTECODE','CUDA_VISIBLE_DEVICES','HIP_VISIBLE_DEVICES'}
    return {k:v for k,v in os.environ.items() if k in allowed or k.startswith('LC_')}


def worker_environment(kind):
    env=subprocess_environment()
    if kind in ENV_KEYS:env[ENV_KEYS[kind][0]]=credential(kind)
    return env


def redact(value):
    _remember_environment()
    keys=_redaction_keys | set(_session.values())
    if isinstance(value,str):
        for key in sorted(keys,key=len,reverse=True):
            if key:value=value.replace(key,'[REDACTED]')
        value=PROVIDER_KEY.sub('[REDACTED]',value)
        return BEARER.sub(r'\1[REDACTED]',value)
    if isinstance(value,dict):return {redact(k):'[REDACTED]' if secret_field(k) else redact(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [redact(v) for v in value]
    return value


def reject_secrets(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if secret_field(key):raise ValueError('Credentials must be session-only or environment variables, never configuration or artifact fields.')
            reject_secrets(item)
    elif isinstance(value,(list,tuple)):
        for item in value:reject_secrets(item)


class RedactingStream:
    def __init__(self,stream):self.stream=stream;self.pending=''
    def write(self,text):
        self.pending+=text
        while '\n' in self.pending:
            line,self.pending=self.pending.split('\n',1)
            self.stream.write(redact(line+'\n'))
        return len(text)
    def writelines(self,lines):
        for line in lines:self.write(line)
    def flush(self):
        if self.pending:self.stream.write(redact(self.pending));self.pending=''
        self.stream.flush()
    def __getattr__(self,name):return getattr(self.stream,name)


@contextlib.contextmanager
def redacted_output():
    stdout,stderr=RedactingStream(sys.stdout),RedactingStream(sys.stderr)
    with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
        try:yield
        finally:stdout.flush();stderr.flush()


def harden_process():
    """Apply to the application process before accepting credentials, including GTK."""
    import resource
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    os.umask(0o077)
    if sys.platform.startswith('linux'):
        import ctypes
        libc=ctypes.CDLL(None,use_errno=True)
        if libc.prctl(4,0,0,0,0)!=0:raise RuntimeError('Cannot disable process dumps; refusing to handle credentials.')
