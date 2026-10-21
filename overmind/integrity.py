"""Evidence from actual classifier parameters, never from claimed improvement alone."""
import hashlib
import json


def parameter_digest(artifact):
    return hashlib.sha256(json.dumps({k:artifact[k] for k in ('labels','dimensions','weights')},
                                     sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def training_evidence(base, candidate):
    before,after=parameter_digest(base),parameter_digest(candidate)
    steps=(candidate['optimizer_steps']-base.get('optimizer_steps',0)) if 'optimizer_steps' in candidate else None
    changed=sum(a!=b for row_a,row_b in zip(base['weights'],candidate['weights']) for a,b in zip(row_a,row_b))
    if base['labels']!=candidate['labels'] or base['dimensions']!=candidate['dimensions']:
        raise ValueError('Training changed the classifier architecture; comparison is invalid.')
    return {'base_parameters_sha256':before,'candidate_parameters_sha256':after,
            'parameters_changed':changed,'optimizer_steps':steps,
            'verified':before!=after and changed>0 and steps is not None and steps>0,
            'notice':'Optimizer steps count SGD examples, including extra practice; legacy checkpoints may lack counters.'}
