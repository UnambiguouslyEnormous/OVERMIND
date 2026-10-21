"""Metadata-only local model inspection. Never imports checkpoint code or loads pickle."""
import json
from pathlib import Path


def _json(path):
    if path.is_symlink() or not path.is_file():raise ValueError('Metadata must be a regular file, not a symlink.')
    if path.stat().st_size > 1_000_000:raise ValueError('Model metadata exceeds 1 MB.')
    data=json.loads(path.read_text())
    if not isinstance(data,dict):raise ValueError('Expected an object in metadata JSON.')
    return data


def inspect_local(path):
    path=Path(path)
    if not path.is_dir():raise ValueError('Select a local HF-compatible checkpoint directory.')
    config=_json(path/'config.json')
    files=[p for p in path.iterdir() if p.is_file() and not p.is_symlink()]
    safe_weights=[p for p in files if p.suffix=='.safetensors']
    tokenizer=any((path/name).is_file() and not (path/name).is_symlink() for name in ('tokenizer.json','tokenizer.model','vocab.json','vocab.txt'))
    license_files=[p.name for p in files if p.name.lower().startswith(('license','copying'))]
    return {'name':path.name,'model_type':config.get('model_type'), 'architectures':config.get('architectures'),
            'declared_dtype':config.get('torch_dtype',config.get('dtype')), 'vocab_size':config.get('vocab_size'),
            'metadata_bytes':sum(p.stat().st_size for p in files),
            'safetensors_files':[p.name for p in safe_weights], 'tokenizer_present':tokenizer,
            'license_files':license_files, 'license_status':'Review license files before use' if license_files else 'Unknown; obtain and review model license',
            'custom_code_declared':bool(config.get('auto_map')), 'adapter_config_present':(path/'adapter_config.json').is_file(),
            'training_status':'Local weights found; architecture, tokenizer and training compatibility unverified' if safe_weights and tokenizer else 'Incomplete local checkpoint; no training compatibility established',
            'notice':'Metadata inspection only. No code executed, weights loaded, license granted, or model downloaded. Top-level storage only; sharded subdirectories are excluded.'}
