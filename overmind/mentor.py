"""Shared mentor proposal contract. Validation messages contain no response/user text."""
import json
import math


class ProposalError(ValueError):
    def __init__(self, category, message):
        super().__init__(message)
        self.category = category


def proposal_schema(linear=False):
    properties = ({
        'learning_rate': {'type': 'number', 'description': 'SGD learning rate from 0.01 to 1.5.'},
        'reason': {'type': 'string', 'description': 'Nonempty experiment rationale, at most 4000 characters.'},
    } if linear else {
        'technique': {'type': 'string', 'enum': ['prompt_optimization', 'retrieval_augmentation']},
        'system_prompt': {'type': 'string', 'description': 'Nonempty student classification instructions, 1–3000 characters.'},
        'retrieval_k': {'type': 'integer', 'description': '1–4 training examples; use 2 when retrieval is not selected.'},
        'reason': {'type': 'string', 'description': 'Nonempty diagnosis and experiment rationale, at most 4000 characters.'},
    })
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def parse_proposal(text, linear=False, require_all=False):
    if not isinstance(text, str):
        raise ProposalError('invalid_type', 'Mentor response must contain a JSON object.')
    text = text.strip()
    if text.startswith('```') and text.endswith('```'):
        lines = text.splitlines()
        if lines[0].lower() in ('```json', '```'):
            text = '\n'.join(lines[1:-1])

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ProposalError('ambiguous_structure', 'Duplicate JSON fields are not allowed; return one flat proposal.')
            result[key] = value
        return result

    def invalid_constant(_):
        raise ProposalError('invalid_type', 'JSON must not contain NaN or Infinity.')

    try:
        plan = json.loads(text, object_pairs_hook=unique, parse_constant=invalid_constant)
    except json.JSONDecodeError as e:
        raise ProposalError('malformed_json', f'Malformed proposal JSON at line {e.lineno}, column {e.colno}; return only a complete JSON object.') from None
    if not isinstance(plan, dict):
        raise ProposalError('invalid_type', 'Proposal must be a JSON object, not an array or scalar.')
    # Compatibility with the exact live failure: accept one unambiguous experiment wrapper.
    # Never guess recursively, merge conflicting plans, or invent missing prompt text.
    wrapped = 'experiment' in plan
    fields = proposal_schema(linear)['properties']
    if wrapped:
        if any(key in plan for key in fields):
            raise ProposalError('ambiguous_structure', 'Conflicting flat and wrapped proposals; return one flat proposal.')
        plan = plan['experiment']
        if not isinstance(plan, dict):
            raise ProposalError('invalid_type', 'The experiment wrapper must contain an object.')
    required = tuple(fields) if require_all else ('learning_rate', 'reason') if linear else ('system_prompt', 'reason')
    for key in required:
        if key not in plan:
            raise ProposalError('missing_field', f'Missing required field {key}; return the complete proposal including this field.')
    if not linear:
        prompt = plan['system_prompt']
        if not isinstance(prompt, str):
            raise ProposalError('invalid_type', 'system_prompt must be a string.')
        if not prompt.strip():
            raise ProposalError('empty_prompt', 'system_prompt must contain non-whitespace instructions.')
        if len(prompt) > 3000:
            raise ProposalError('oversized_prompt', 'system_prompt exceeds 3000 characters; shorten it without omitting the field.')
        # Existing local mentors may omit these optional fields. New cloud schemas require them.
        technique = plan.get('technique', 'prompt_optimization')
        if not isinstance(technique, str):
            raise ProposalError('invalid_type', 'technique must be a string.')
        if technique not in ('prompt_optimization', 'retrieval_augmentation'):
            raise ProposalError('unsupported_strategy', 'technique must be prompt_optimization or retrieval_augmentation.')
        k = plan.get('retrieval_k', 2)
        if type(k) is not int:
            raise ProposalError('invalid_type', 'retrieval_k must be an integer, not a boolean or string.')
        if not 1 <= k <= 4:
            raise ProposalError('invalid_range', 'retrieval_k must be between 1 and 4.')
        result = {'technique': technique, 'system_prompt': prompt, 'retrieval_k': k}
    else:
        rate = plan['learning_rate']
        if type(rate) not in (int, float):
            raise ProposalError('invalid_type', 'learning_rate must be a number.')
        if not math.isfinite(rate) or not .01 <= rate <= 1.5:
            raise ProposalError('invalid_range', 'learning_rate must be finite and between 0.01 and 1.5.')
        result = {'learning_rate': rate}
    reason = plan['reason']
    if not isinstance(reason, str):
        raise ProposalError('invalid_type', 'reason must be a string.')
    if not reason.strip() or len(reason) > 4000:
        raise ProposalError('invalid_reason', 'reason must contain 1–4000 characters of experiment rationale.')
    return {**result, 'reason': reason}, wrapped
