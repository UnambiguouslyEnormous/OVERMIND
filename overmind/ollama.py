"""Local discovery only: never installs, pulls models, or starts a service."""
import shutil
from .providers import LocalProvider

def discover(url='http://127.0.0.1:11434'):
    info={'installed':bool(shutil.which('ollama')),'running':False,'models':[],
        'guidance':'Install Ollama using the instructions at https://docs.ollama.com/linux . Start its service (or ollama serve), then provision a suitably licensed small model yourself. OVERMIND never downloads a model automatically.'}
    try:
        p=LocalProvider('ollama',url,'discovery')
        tags=p.request('/api/tags');info.update(running=True,models=tags.get('models',[]))
        info['guidance']='Server is reachable. Select an installed model; inspect its license and quantization before running.'
        if not info['models']:info['guidance']='Ollama is running but has no local models. Install a suitably licensed small model yourself, then refresh.'
    except (OSError,ValueError):info['guidance']='Ollama endpoint is unreachable. '+info['guidance']
    return info
