"""Original CC0 intent benchmark. Splits are authored separately, never inferred by mentor."""
import hashlib
import json
from pathlib import Path

LABELS = ['account', 'billing', 'security', 'technical']
# Original examples authored for OVERMIND, dedicated to CC0-1.0.
TEXTS = {
'account': [
'I want to change my profile name', 'Update my email address', 'How can I delete my account',
'Please edit my display name', 'I need to reset my password', 'Help me sign in to my account',
'Change my profile photo', 'Where are my account preferences', 'I forgot my login password',
'Please close my account', 'I want to update my username', 'How do I change my contact details',
'I cannot remember my password', 'Can I edit my personal profile', 'Help me recover my login',
'Change the email on my account', 'I need help with account registration', 'Please update my profile',
'How can I sign up', 'I need a password reset link',
# validation
'My profile needs a new photo', 'How do I recover my password', 'Edit my account name please',
'I would like to close my profile', 'Can I change my login email', 'Help with registration please',
# held out
'Please send a link to reset my password', 'I wish to delete my profile', 'Change my registered email',
'My account name should be updated', 'How do I replace my profile image', 'I have forgotten my login',
'I want to register an account', 'Where can I edit my username', 'Help me update my contact email',
'I need to recover access to my account'],
'billing': [
'Why was my card charged twice', 'I need a refund for my purchase', 'Send me an invoice',
'How much does the subscription cost', 'Please cancel my paid subscription', 'My payment was declined',
'Update my billing address', 'Where is my payment receipt', 'I was charged the wrong amount',
'How do I change my credit card', 'I need a copy of my invoice', 'Please refund this charge',
'What is the monthly price', 'My credit card payment failed', 'Cancel automatic renewal',
'I want to upgrade my subscription plan', 'The invoice total is incorrect', 'Help with a payment dispute',
'I need to update my payment method', 'When will my refund arrive',
# validation
'Please explain this charge on my card', 'I want my purchase refunded', 'Download my billing invoice',
'What does a yearly subscription cost', 'Stop renewing my paid plan', 'My payment method needs changing',
# held out
'Could you send a receipt for my payment', 'I need to dispute a duplicate charge',
'Please change the card used for billing', 'How much is the annual plan', 'My refund has not arrived',
'I was billed more than expected', 'The subscription payment was rejected', 'I need my latest invoice',
'Can I stop the subscription renewal', 'Update the address on my invoice'],
'security': [
'Someone hacked my account', 'I received a suspicious login alert', 'Enable two factor authentication',
'I think someone stole my password', 'Report a phishing email', 'There is an unknown device logged in',
'How can I secure my account', 'I found a security vulnerability', 'Revoke a stolen access token',
'My account has been compromised', 'Someone is impersonating me', 'Help me turn on multifactor authentication',
'I see unauthorized login attempts', 'Is this suspicious email a scam', 'Please block an intruder',
'I accidentally exposed my API key', 'Remove an unknown session', 'How do I report a data breach',
'Set up an authenticator app', 'I suspect credential theft',
# validation
'A stranger signed into my account', 'Please enable two factor protection', 'I received a phishing message',
'My secret token was leaked', 'An unknown device has access', 'Where can I report a vulnerability',
# held out
'I believe my credentials were stolen', 'Please revoke my exposed API token', 'Someone broke into my account',
'I need help enabling multifactor protection', 'A login from an unfamiliar device worries me',
'This email looks like a phishing scam', 'How do I report a security breach', 'Terminate a suspicious session',
'A person is impersonating my identity', 'An intruder has my password'],
 'technical': [
'The app crashes on startup', 'My screen stays blank', 'The download keeps failing',
'I get an error when uploading a file', 'The application is very slow', 'How do I fix a connection timeout',
'The page will not load', 'Installation failed with an error', 'The button does not respond',
'My files are not syncing', 'The server returns an error', 'Audio playback is broken',
'The app freezes when I open it', 'I cannot connect to the server', 'Help troubleshoot a broken upload',
'The software update will not install', 'The interface flickers', 'My download is stuck',
'Search returns an unexpected error', 'The application uses too much memory',
# validation
'Opening the application causes a crash', 'My upload gets stuck', 'The server connection timed out',
'An update failed to install', 'The interface is not responding', 'My documents will not sync',
# held out
'The program crashes whenever I launch it', 'I see an empty screen after startup',
'File uploads fail with an error message', 'My connection to the server keeps dropping',
'The application freezes during use', 'A download never finishes', 'Why is the software running slowly',
'Clicking the button does nothing', 'I cannot install the latest update', 'My files stopped synchronizing']
}

def benchmark():
    parts = {x: [] for x in ('train','validation','test')}
    for label, texts in TEXTS.items():
        for i, text in enumerate(texts):
            parts['train' if i < 20 else 'validation' if i < 26 else 'test'].append({'input':text,'target':label})
    return validate({'name':'Support routing v1', 'license':'CC0-1.0', 'labels':LABELS, **parts})

def validate(data):
    if isinstance(data,dict) and data.get('format')=='gafaw.sft.v1':
        from .sft_data import validate as validate_sft
        return validate_sft(data)
    if not isinstance(data, dict) or not data.get('license') or len(str(data['license'])) > 500:
        raise ValueError('Dataset requires an explicit license identifier or permission statement.')
    labels = data.get('labels', [])
    if not 2 <= len(labels) <= 32 or len(set(labels)) != len(labels) or not all(isinstance(x,str) and 0 < len(x) < 100 for x in labels):
        raise ValueError('Provide 2–32 distinct text labels.')
    seen = set()
    total = 0
    for split in ('train','validation','test'):
        rows = data.get(split)
        if not isinstance(rows,list) or not 8 <= len(rows) <= 5000:
            raise ValueError(f'{split} requires 8–5000 examples.')
        for row in rows:
            if not isinstance(row,dict) or not isinstance(row.get('input'),str) or not 0 < len(row['input']) <= 4000 or row.get('target') not in labels:
                raise ValueError(f'Invalid example in {split}.')
            key = ' '.join(row['input'].lower().split())
            if key in seen:
                raise ValueError('Duplicate inputs across or within splits are forbidden.')
            seen.add(key)
        if set(x['target'] for x in rows) != set(labels):
            raise ValueError(f'Every label must be represented in {split}.')
        total += len(rows)
    if total > 10000:
        raise ValueError('This CPU experiment supports at most 10,000 examples.')
    return data

def load(path=None):
    if path:
        p = Path(path)
        if p.stat().st_size > 8_000_000:
            raise ValueError('Dataset exceeds 8 MB limit.')
        return validate(json.loads(p.read_text()))
    return benchmark()

def digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
