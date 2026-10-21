"""Local, data-minimized evidence bundles. Validation never extracts or executes files."""
import hashlib
import json
import os
from pathlib import Path
import zipfile
from .security import redact

FORMAT='gafaw.evidence.v1'
MAX_BYTES=64_000_000


def _bytes(value):
    return json.dumps(redact(value),indent=2,allow_nan=False,ensure_ascii=False).encode()


def export_bundle(store,rid,path,include_dataset=False,include_weights=False):
    run=store.get(rid)
    if run['status']!='completed':raise ValueError('Export requires a completed experiment with final evidence.')
    config=run['config']
    # Do not expose the original checkpoint location in portable configuration.
    if config.get('student',{}).get('checkpoint'):
        config={**config,'student':{**config['student'],'checkpoint':'original-student.json (optional artifact)'}}
    files={'config.json':_bytes(config)}
    for name in ('report.json','training-integrity.json','training-metrics.json','environment.json','notebook.json'):
        try:files[name]=_bytes(store.read(rid,name))
        except FileNotFoundError:pass
    for name in ('baseline-test.json','candidate-test.json'):
        evaluation=store.read(rid,name)
        if not include_dataset:
            evaluation={**evaluation,'results':[{k:v for k,v in row.items() if k!='input'} | {'input_sha256':hashlib.sha256(row['input'].encode()).hexdigest()} for row in evaluation['results']]}
        files[name]=_bytes(evaluation)
    if include_dataset:files['dataset.json']=_bytes(store.read(rid,'dataset.json'))
    if include_weights:
        candidate=store.read(rid,'candidate.json')
        if candidate.get('format')!='overmind.softmax.v1':
            raise ValueError('Weight export currently supports only the original CPU classifier; prompt/retrieval artifacts may contain dataset text.')
        files['candidate.json']=_bytes(candidate)
        try:files['original-student.json']=_bytes(store.read(rid,'original-student.json'))
        except FileNotFoundError:pass
    manifest={'format':FORMAT,'experiment':rid,'includes_dataset':include_dataset,'includes_weights':include_weights,
              'notice':'Local export. Notebook/free text may contain private information; inspect before sharing. No code is included or executed.',
              'files':{name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()}}
    files['manifest.json']=_bytes(manifest)
    if sum(map(len,files.values()))>MAX_BYTES:raise ValueError('Bundle exceeds 64 MB limit.')
    path=Path(path).absolute()
    if any(parent.is_symlink() for parent in path.parents):raise ValueError('Bundle path must not traverse symlinks.')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream,zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,raw in files.items():archive.writestr(name,raw)
    return manifest


def validate_bundle(path):
    path=Path(path)
    if path.stat().st_size>MAX_BYTES:raise ValueError('Bundle exceeds 64 MB limit.')
    with zipfile.ZipFile(path) as archive:
        entries=archive.infolist()
        names=[entry.filename for entry in entries]
        if len(entries)>32 or len(set(names))!=len(names):raise ValueError('Too many or duplicate bundle entries.')
        if any(Path(name).name!=name or name in ('.','..') or '\\' in name or not name.endswith('.json') for name in names):
            raise ValueError('Unsafe bundle entry path or format.')
        if sum(entry.file_size for entry in entries)>MAX_BYTES:raise ValueError('Expanded bundle exceeds 64 MB limit.')
        manifest=json.loads(archive.read('manifest.json'))
        if manifest.get('format')!=FORMAT or not isinstance(manifest.get('files'),dict):raise ValueError('Unsupported evidence bundle manifest.')
        if set(names)!=set(manifest['files'])|{'manifest.json'}:raise ValueError('Manifest does not match archive entries.')
        for name,expected in manifest['files'].items():
            raw=archive.read(name)
            if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Bundle checksum mismatch: '+name)
            # Parse only data; never deserialize pickle, import, extract, or execute anything.
            json.loads(raw)
        return manifest
