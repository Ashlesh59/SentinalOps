import re

class SecretRedactor:
    """
    Scans for recognized credential, API key, password, and token patterns
    and replaces them with <SECRET_REDACTED>.
    Secrets are strictly destroyed/redacted, never tokenized or saved in alias maps.
    """
    SECRET_PATTERNS = [
        # Known API Key prefixes
        (re.compile(r'\b(sk[-_](?:live|prod|test)[-_][a-zA-Z0-9]+)\b', re.IGNORECASE), r'<SECRET_REDACTED>'),
        (re.compile(r'\b(AKIA[0-9A-Z]{16})\b'), r'<SECRET_REDACTED>'),
        # Key-Value commandline / header patterns: -apikey val, -token val, password=val, secret=val, bearer val
        (re.compile(r'(-{1,2}(?:api_?key|token|pass(?:word)?|secret|cred(?:ential)?))\s+([^\s]+)', re.IGNORECASE), r'\1 <SECRET_REDACTED>'),
        (re.compile(r'((?:api_?key|token|pass(?:word)?|secret|cred(?:ential)?)=)([^\s;&]+)', re.IGNORECASE), r'\1<SECRET_REDACTED>'),
        (re.compile(r'\b(Bearer)\s+([a-zA-Z0-9\-\._~\+\/]+=*)', re.IGNORECASE), r'Bearer <SECRET_REDACTED>'),
        # curl basic auth -u user:password
        (re.compile(r'(-u\s+[a-zA-Z0-9_.-]+:)([^\s]+)', re.IGNORECASE), r'\1<REDACTED_SECRET>'),
    ]

    def redact_secrets(self, text: str) -> str:
        if not text:
            return text
        result = text
        for pattern, replacement in self.SECRET_PATTERNS:
            result = pattern.sub(replacement, result)
        return result
