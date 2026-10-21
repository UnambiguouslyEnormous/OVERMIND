"""Small reproducibility snapshot without imports of optional training runtimes."""
import hashlib
import importlib.metadata
from pathlib import Path
import platform
import sys


def snapshot():
    sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob('*.py'))}
    versions={}
    for name in ('torch','transformers','peft','accelerate'):
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]=None
    return {'python':platform.python_version(),'implementation':sys.implementation.name,
            'os':platform.platform(),'machine':platform.machine(),'libraries':versions,
            'source_sha256':sources,'training_seed_policy':'Classifier shuffles with random.Random(42 + epoch); dataset split seeds are recorded separately.'}
