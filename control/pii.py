import re

PII_PATTERNS = {
    'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    'email': re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', re.IGNORECASE),
    'phone': re.compile(r'(?:(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4})'),
    'credit_card': re.compile(r'\b(?:\d[ -]*?){13,16}\b'),
    'bank_account': re.compile(r'\b\d{8,17}\b'),
    'routing_number': re.compile(r'\b\d{9}\b'),
    'ein': re.compile(r'\b\d{2}-\d{7}\b'),
    'dob': re.compile(r'\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12][0-9]|3[01])[/-](?:19|20)\d{2}\b'),
}

REPLACEMENTS = {
    'ssn': '[REDACTED_SSN]',
    'email': '[REDACTED_EMAIL]',
    'phone': '[REDACTED_PHONE]',
    'credit_card': '[REDACTED_CARD]',
    'bank_account': '[REDACTED_ACCOUNT]',
    'routing_number': '[REDACTED_ROUTING]',
    'ein': '[REDACTED_EIN]',
    'dob': '[REDACTED_DOB]',
}


def detect_pii(text):
    text = text or ''
    matches = []
    for pii_type, pattern in PII_PATTERNS.items():
        if pattern.search(text):
            matches.append(pii_type)
    return matches


def redact_pii(text):
    text = text or ''
    detected = detect_pii(text)
    redacted = text
    replacement_order = [
        'ssn', 'email', 'phone', 'credit_card', 'ein', 'dob', 'routing_number', 'bank_account'
    ]
    for pii_type in replacement_order:
        if pii_type in detected:
            redacted = PII_PATTERNS[pii_type].sub(REPLACEMENTS[pii_type], redacted)
    return {
        'text': redacted,
        'pii_types': detected,
        'contains_pii': bool(detected),
    }
