"""Offline recognizers shared by output redaction and the Git secret check."""
import re

PROVIDER_KEY = re.compile(r'(?<![A-Za-z0-9_-])sk-(?:ant-[A-Za-z0-9_-]{16,}|proj-[A-Za-z0-9_-]{16,}|[A-Za-z0-9_-]{20,})(?![A-Za-z0-9_-])')
PRIVATE_KEY = re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----')
BEARER = re.compile(r'(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]{8,}')
ASSIGNMENT = re.compile(r'''(?im)["']?(?:[A-Z_]*(?:API_KEY|ACCESS_TOKEN|CLIENT_SECRET)|api_key|access_token|client_secret|password)["']?\s*[:=]\s*["']([^\r\n"']{12,})["']''')
UNQUOTED = re.compile(r'(?im)^\s*(?:export\s+)?[A-Z_]*(?:API_KEY|ACCESS_TOKEN|CLIENT_SECRET)\s*=\s*([^\s#\r\n\x22\x27]{12,})')


def secret_field(name):
    normalized = re.sub(r'[^a-z0-9]', '', str(name).lower())
    return normalized in {'apikey','authorization','password','secret','accesstoken','clientsecret','credential','credentials',
        'openaiapikey','anthropicapikey','overmindopenaiapikey','overmindanthropicapikey'}


def detections(text):
    kinds = set()
    if PROVIDER_KEY.search(text): kinds.add('provider key pattern')
    if PRIVATE_KEY.search(text): kinds.add('private key block')
    for pattern in (ASSIGNMENT, UNQUOTED):
        for match in pattern.finditer(text):
            value = match.group(1)
            # Explicit non-secret examples remain allowed; provider-shaped keys are always blocked.
            if any(word in value.lower() for word in ('fixture','placeholder','your_','change_me','[redacted]')):
                continue
            kinds.add('credential assignment')
    return sorted(kinds)
