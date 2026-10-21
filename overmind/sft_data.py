"""Instruction/response datasets: explicit reviewed splits, no holdout synthesis."""
import json
from .workshop import key
from .data import digest

FORMAT='gafaw.sft.v1'
SPLITS=('train','validation','test')


def validate(data):
    if not isinstance(data,dict) or data.get('format')!=FORMAT:raise ValueError('Instruction data requires format gafaw.sft.v1.')
    if not isinstance(data.get('license'),str) or not 0<len(data['license'])<=500:raise ValueError('Declare the dataset license or permission.')
    if not isinstance(data.get('name'),str) or not 0<len(data['name'])<=200:raise ValueError('Give the instruction dataset a name.')
    seen=set();total=0
    for split in SPLITS:
        rows=data.get(split)
        if not isinstance(rows,list) or not 2<=len(rows)<=2000:raise ValueError(f'{split} needs 2–2,000 independently reviewed examples.')
        for row in rows:
            if not isinstance(row,dict) or set(row)-{'input','target','axis'}:raise ValueError('Instruction rows support input, target, and optional axis only.')
            for field in ('input','target'):
                if not isinstance(row.get(field),str) or not 0<len(row[field])<=8000 or not key(row[field]):raise ValueError('Instruction/response text must contain 1–8,000 characters.')
            if row.get('axis','instruction') not in ('instruction','technical','style','consistency'):raise ValueError('axis must be instruction, technical, style or consistency.')
            identity=key(row['input'])
            if identity in seen:raise ValueError('Duplicate instruction within/across splits; possible holdout leakage.')
            seen.add(identity)
        total+=len(rows)
    if total>5000:raise ValueError('Instruction dataset exceeds 5,000 examples.')
    if len(json.dumps(data).encode())>8_000_000:raise ValueError('Instruction dataset exceeds 8 MB.')
    return data


def reviewed_jsonl(text,license,name='Reviewed instructions',parent=None):
    if len(text.encode())>8_000_000:raise ValueError('Instruction dataset exceeds 8 MB.')
    data={'format':FORMAT,'name':name,'license':license,**{s:[] for s in SPLITS}}
    for line in text.splitlines():
        if not line.strip():continue
        row=json.loads(line)
        if not isinstance(row,dict) or row.get('split') not in SPLITS:raise ValueError('Every instruction row needs an explicit train/validation/test split. Holdout is never inferred from generated lessons.')
        row=dict(row);split=row.pop('split');data[split].append(row)
    validate(data)
    data['provenance']={'reviewed':True,'content_sha256':digest(data),'parent_sha256':digest(parent) if parent else None,
                        'notice':'Explicit splits reviewed by the user; exact normalized instruction overlap is blocked, paraphrases require review.'}
    return data


def editable_jsonl(data):
    return '\n'.join(json.dumps({**row,'split':split},ensure_ascii=False) for split in SPLITS for row in data[split])


def example():
    """Original CC0 examples: educational seed, not proof of Qwen improvement."""
    rows={
        'train':[
            ('Explain a fuse in one sentence.','A fuse breaks the circuit when current becomes excessive; replace it only with the specified rating.','technical'),
            ('I made a bug. Be encouraging and concise.','A bug is a clue with terrible manners. Reproduce it, isolate the cause, and change one thing at a time.','style'),
            ('Should I probe an energized circuit blindly?','No. Identify the circuit, follow its service procedure, and use suitable measurement tools and protection.','technical'),
            ('Answer in exactly two words: what should experiments preserve?','Independent evidence','instruction'),
            ('What is a voltage drop?','Voltage drop is the potential difference across a component or connection while current flows.','technical'),
            ('How should you handle uncertainty?','State what is measured, label hypotheses, and ask for the missing evidence.','consistency'),
            ('Give a friendly debugging motto.','One change, one measurement, fewer gremlins.','style'),
            ('What separates prompting from training?','Prompting changes the input context; training updates model parameters.','instruction')],
        'validation':[
            ('What does a blown fuse tell me?','It indicates excessive current occurred; investigate the cause before fitting the specified replacement.','technical'),
            ('My first experiment failed. Say something useful and warm.','That result still earned its keep. Save the evidence and test one narrower hypothesis next.','style')],
        'test':[
            ('How can I distinguish a guess from an observation?','An observation comes from recorded evidence; a guess is a hypothesis that still needs testing.','consistency'),
            ('A tricky software fault keeps returning. Offer one brief next step.','Capture a minimal reproducible case; give the gremlin a smaller room to hide in.','style'),
            ('Does a lower training loss establish better factual accuracy?','No. Evaluate factual accuracy independently on held-out tasks.','technical'),
            ('Reply with exactly one word: should evaluation prompts be added to training?','No','instruction')]
    }
    return validate({'format':FORMAT,'name':'GAFAW collaborator seed · review before training','license':'CC0-1.0',
                     **{split:[{'input':i,'target':t,'axis':a} for i,t,a in group] for split,group in rows.items()}})
