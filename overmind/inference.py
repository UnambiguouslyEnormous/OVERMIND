"""Use saved artifacts without changing evaluations. Manual LLM trials are local-only."""
from .model import TextStudent
from .providers import LocalProvider
from .retrieval import augment

def predict_artifact(artifact,text,allow_local=False):
    if not isinstance(text,str) or not 1<=len(text)<=4000:raise ValueError('Enter 1–4000 characters.')
    if artifact.get('format')=='overmind.softmax.v1':return TextStudent.restore(artifact).predict(text)
    if artifact.get('format')!='overmind.prompt.v1':raise ValueError('Unknown student artifact format.')
    if not allow_local:raise ValueError('Authorize one local LLM request with --allow-local-inference.')
    config=artifact['provider']
    # Deliberately construct the local transport directly: artifacts cannot dispatch cloud requests.
    p=LocalProvider(config['kind'],config['url'],config['model'])
    if artifact.get('technique')=='retrieval_augmentation':text=augment(artifact['retrieval_rows'],text,artifact.get('retrieval_k',2))
    return p.generate(artifact['system_prompt'],text,32).strip()
