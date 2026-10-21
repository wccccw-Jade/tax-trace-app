"""Demo identities and response redaction. Original packet is never a public static asset."""
import re

STAFF_ROLES = {'preparer', 'reviewer', 'partner', 'firm_administrator', 'quality_reviewer'}


def actors(packet):
    return packet.data['firm']['staff'] + packet.data['firm']['client_users']


def actor_by_id(packet, actor_id):
    return next((a for a in actors(packet) if a['id'] == actor_id), None)


def sensitive_tokens(packet):
    values = set()
    def walk(value, key=''):
        if isinstance(value, dict):
            for k, v in value.items():
                walk(v, k)
        elif isinstance(value, list):
            for v in value:
                walk(v, key)
        elif value is not None and any(x in key.lower() for x in ('ssn','account','routing','ip_pin','ero_pin','efin','ptin')):
            if len(str(value)) >= 4:
                values.add(str(value))
    walk(packet.data['household'])
    walk(packet.data['firm']['firm_identity'])
    for e in packet.data['extracted_values']:
        if e['value_type'] in ('ssn','account_number') or 'pin' in e['field'].lower():
            for value in (e.get('value'), e.get('text_as_read')):
                if value and len(str(value)) >= 4:
                    values.add(str(value))
    # Also capture formatted SSNs in source pages and other text.
    values.update(re.findall(r'\b\d{3}-\d{2}-\d{4}\b', packet.original))
    return sorted(values, key=len, reverse=True)


def redact(value, tokens):
    if isinstance(value, dict):
        return {k: redact(v, tokens) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, tokens) for v in value]
    if isinstance(value, str):
        for token in tokens:
            value = value.replace(token, '[masked]')
        return value
    if isinstance(value, (int, float)) and str(value) in tokens:
        return '[masked]'
    return value
