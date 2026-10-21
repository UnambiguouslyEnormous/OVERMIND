"""Bounded labeled-data import and reproducible splitting; no network or model calls."""
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import random
import unicodedata

from .data import digest, validate

SPLITS = ('train', 'validation', 'test')


def key(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


def rows_from_text(text, kind):
    if len(text.encode('utf-8')) > 8_000_000:
        raise ValueError('Dataset exceeds 8 MB limit.')
    if kind == 'jsonl':
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    elif kind in ('csv', 'tsv', 'txt'):
        rows = list(csv.DictReader(io.StringIO(text), delimiter=',' if kind == 'csv' else '\t'))
    else:
        raise ValueError('Use JSONL or CSV/TSV/TXT with input,target columns (TXT is tab-separated).')
    if not 1 <= len(rows) <= 10000:
        raise ValueError('Import requires 1–10,000 labeled rows.')
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get('input'), str)
                or not 0 < len(row['input']) <= 4000 or not key(row['input'])
                or not isinstance(row.get('target'), str) or not 0 < len(row['target']) < 100):
            raise ValueError('Every row requires nonempty input (≤4,000 characters) and target (label).')
        if row.get('split') not in (None, '', *SPLITS):
            raise ValueError('split must be train, validation, or test.')
    if any(row.get('split') for row in rows) and not all(row.get('split') for row in rows):
        raise ValueError('Specify splits for every row or leave all splits empty.')
    return rows


def prepare(rows, license, name='Imported dataset', seed=42, source_sha256=None):
    """Deduplicate before splitting. Conflicts and explicit-split overlap fail closed."""
    if not isinstance(seed, int) or not 0 <= seed <= 2**32-1:
        raise ValueError('Seed must be an integer from 0 to 4294967295.')
    # Validate again, including callers which did not use a file parser.
    rows = rows_from_text('\n'.join(json.dumps(row) for row in rows), 'jsonl')
    explicit = bool(rows[0].get('split'))
    unique = {}
    removed = 0
    for row in rows:
        identity = key(row['input'])
        if identity in unique:
            previous = unique[identity]
            if previous['target'] != row['target']:
                raise ValueError('Duplicate input has conflicting labels; review the source.')
            if explicit and previous['split'] != row['split']:
                raise ValueError('Duplicate input crosses explicit splits; possible evaluation leakage.')
            removed += 1
        else:
            unique[identity] = row
    data = {'name': name[:200], 'license': license, 'labels': sorted({row['target'] for row in unique.values()}),
            **{split: [] for split in SPLITS}}
    if explicit:
        for row in unique.values():
            data[row['split']].append({'input': row['input'], 'target': row['target']})
    else:
        groups = defaultdict(list)
        for row in unique.values():groups[row['target']].append(row)
        rng = random.Random(seed)
        for target in sorted(groups):
            # Sort first: the same source records in a different order give the same split.
            group = sorted(groups[target], key=lambda row: key(row['input']))
            if len(group) < 3:
                raise ValueError('Every label needs at least three unique examples; each final split needs ≥8 rows.')
            rng.shuffle(group)
            n = max(1, int(len(group) * .15))
            for split, chunk in zip(SPLITS, (group[2*n:], group[:n], group[n:2*n])):
                data[split].extend({'input': row['input'], 'target': target} for row in chunk)
    validate(data)
    data['provenance'] = {'format': 'gafaw.dataset.v1', 'source_sha256': source_sha256,
                          'split_seed': None if explicit else seed, 'split_policy': 'preserved' if explicit else 'stratified 70/15/15, rounded per label',
                          'duplicates_removed': removed, 'content_sha256': digest(data),
                          'notice': 'Text normalization prevents exact overlap; semantic/paraphrase leakage still requires human review.'}
    return data


def import_file(path, license, seed=42):
    path = Path(path)
    if path.stat().st_size > 8_000_000:raise ValueError('Dataset exceeds 8 MB limit.')
    raw = path.read_bytes()
    text = raw.decode('utf-8-sig')
    if path.suffix.lower() == '.json':
        data = validate(json.loads(text))
        # Preserve authored splits; apply stronger normalization check without silently changing them.
        seen = set()
        for split in SPLITS:
            for row in data[split]:
                identity = key(row['input'])
                if identity in seen:raise ValueError('Normalized duplicate in explicit dataset splits.')
                seen.add(identity)
        return data
    return prepare(rows_from_text(text, path.suffix.lower().lstrip('.')), license,
                   path.stem, seed, hashlib.sha256(raw).hexdigest())


def summary(data):
    validate(data)
    if data.get('format')=='gafaw.sft.v1':
        return {'name':data['name'],'format':data['format'],'fingerprint':digest(data),'license':data['license'],
                'splits':{s:{'count':len(data[s])} for s in SPLITS},'notice':'Instruction/response data: explicit reviewed splits; real tokenizer counts are measured in the training worker.'}
    return {'name': data.get('name'), 'fingerprint': digest(data), 'license': data['license'],
            'splits': {split: {'count': len(data[split]), 'labels': dict(Counter(row['target'] for row in data[split]))} for split in SPLITS},
            'estimated_tokens': sum(max(1, (len(row['input']) + 3)//4) for split in SPLITS for row in data[split]),
            'token_notice': 'Character-count estimate (~4 characters/token), not a tokenizer measurement.',
            'provenance': data.get('provenance')}


def editable_jsonl(data):
    return '\n'.join(json.dumps({**row, 'split': split}, ensure_ascii=False) for split in SPLITS for row in data[split])


def export_version(data, path):
    """Create a private immutable dataset version; refuse links and overwrites."""
    import os
    from .security import reject_secrets
    validate(data)
    reject_secrets(data)
    path = Path(path).absolute()
    if any(parent.is_symlink() for parent in path.parents):
        raise ValueError('Dataset export must not traverse symlinks.')
    payload = json.dumps(data, indent=2, ensure_ascii=False).encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(payload)
    return str(path)
