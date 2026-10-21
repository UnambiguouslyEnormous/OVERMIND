"""Local, data-minimized evidence bundles. Validation never extracts or executes files."""
import hashlib
import json
import os
import re
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
    for name in ('report.json','training-integrity.json','training-metrics.json','environment.json','notebook.json','preflight.json','base-model.json','checkpoint.json'):
        try:files[name]=_bytes(store.read(rid,name))
        except FileNotFoundError:pass
    for name in ('baseline-test.json','candidate-test.json','stock-test.json'):
        try:evaluation=store.read(rid,name)
        except FileNotFoundError:continue
        if not include_dataset:
            private_fields=('input','target','prediction') if config['student']['kind']=='local_lora' else ('input',)
            evaluation={**evaluation,'results':[{k:v for k,v in row.items() if k not in private_fields} | {field+'_sha256':hashlib.sha256(row[field].encode()).hexdigest() for field in private_fields} for row in evaluation['results']]}
        files[name]=_bytes(evaluation)
    if include_dataset:files['dataset.json']=_bytes(store.read(rid,'dataset.json'))
    if include_weights:
        candidate=store.read(rid,'candidate.json')
        if candidate.get('format')=='gafaw.lora.v1':
            name=candidate['adapter_directory']
            if not isinstance(name,str) or not re.fullmatch(r'adapter-epoch-[0-9]+',name):raise ValueError('Invalid adapter directory.')
            directory=store.root/rid/name
            if directory.is_symlink():raise ValueError('Adapter directory must not be a symlink.')
            for filename,expected in candidate['adapter_files_sha256'].items():
                if Path(filename).name!=filename or Path(filename).suffix not in ('.json','.safetensors','.md'):raise ValueError('Unsupported adapter asset.')
                path=directory/filename
                if path.is_symlink() or path.stat().st_size>MAX_BYTES:raise ValueError('Unsafe or oversized adapter asset.')
                raw=path.read_bytes()
                if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Adapter checksum mismatch before export.')
                files[name+'/'+filename]=raw
        elif candidate.get('format')!='overmind.softmax.v1':
            raise ValueError('Weight export supports CPU classifiers and verified local LoRA adapters only.')
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
        if any(not (re.fullmatch(r'[a-zA-Z0-9_-]+\.json',name) or re.fullmatch(r'adapter-epoch-[0-9]+/[a-zA-Z0-9_.-]+\.(json|safetensors|md)',name)) or '\\' in name for name in names):
            raise ValueError('Unsafe bundle entry path or format.')
        if sum(entry.file_size for entry in entries)>MAX_BYTES:raise ValueError('Expanded bundle exceeds 64 MB limit.')
        manifest=json.loads(archive.read('manifest.json'))
        if manifest.get('format')!=FORMAT or not isinstance(manifest.get('files'),dict):raise ValueError('Unsupported evidence bundle manifest.')
        if set(names)!=set(manifest['files'])|{'manifest.json'}:raise ValueError('Manifest does not match archive entries.')
        for name,expected in manifest['files'].items():
            raw=archive.read(name)
            if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Bundle checksum mismatch: '+name)
            # Parse only data; never deserialize pickle, import, extract, or execute anything.
            if name.endswith('.json'):json.loads(raw)
        return manifest
