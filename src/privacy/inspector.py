import re
from typing import Tuple
from src.privacy.redactor import SecretRedactor
from src.privacy.tokenization import AliasService

class FreeTextInspector:
    """
    Deterministically inspects and sanitizes unstructured free-text strings.
    Tokenizes embedded emails and private IPs, redacts secrets, and fails safe
    to <WITHHELD_UNSAFE_TEXT> if text cannot be confidently sanitized.
    """
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
    PRIVATE_IP_PATTERN = re.compile(r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b')
    
    # Suspicious pattern indicator for unclassifiable/unknown text
    UNKNOWN_UNSAFE_PATTERN = re.compile(r'\b(UNRECOGNIZED_SECRET_FORMAT_[a-zA-Z0-9]+)\b')

    def __init__(self, redactor: SecretRedactor, alias_service: AliasService):
        self.redactor = redactor
        self.alias_service = alias_service

    def inspect_and_sanitize(self, text: str) -> Tuple[str, bool]:
        """
        Returns (sanitized_text, is_safe).
        If is_safe is False, caller should withhold the text or set to <WITHHELD_UNSAFE_TEXT>.
        """
        if not text:
            return text, True

        # Check for unclassifiable unknown dangerous text
        if self.UNKNOWN_UNSAFE_PATTERN.search(text):
            return "<WITHHELD_UNSAFE_TEXT>", False

        # Step 1: Redact recognized secrets
        sanitized = self.redactor.redact_secrets(text)

        # Step 2: Tokenize embedded emails
        def replace_email(match):
            email = match.group(0)
            return self.alias_service.get_or_create_alias(email, "USER")
        sanitized = self.EMAIL_PATTERN.sub(replace_email, sanitized)

        # Step 3: Tokenize embedded private IPs
        def replace_ip(match):
            ip = match.group(0)
            return self.alias_service.get_or_create_alias(ip, "PRIVATE_IP")
        sanitized = self.PRIVATE_IP_PATTERN.sub(replace_ip, sanitized)

        return sanitized, True
