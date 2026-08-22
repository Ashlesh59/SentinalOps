from enum import Enum
from pydantic import BaseModel

class PrivacyClass(str, Enum):
    SECRET = "SECRET"
    DIRECT_IDENTIFIER = "DIRECT_IDENTIFIER"
    INTERNAL_ASSET_IDENTIFIER = "INTERNAL_ASSET_IDENTIFIER"
    QUASI_IDENTIFIER = "QUASI_IDENTIFIER"
    PUBLIC_SECURITY_INDICATOR = "PUBLIC_SECURITY_INDICATOR"
    SECURITY_SEMANTIC = "SECURITY_SEMANTIC"
    SECURITY_CONTEXT = "SECURITY_CONTEXT"
    SAFE_METADATA = "SAFE_METADATA"
    UNCLASSIFIED_FREE_TEXT = "UNCLASSIFIED_FREE_TEXT"

class PrivacyAction(str, Enum):
    ALLOW = "ALLOW"
    TOKENIZE = "TOKENIZE"
    REDACT = "REDACT"
    GENERALIZE = "GENERALIZE"
    LOCAL_ONLY = "LOCAL_ONLY"

class FieldPrivacyContract(BaseModel):
    field_name: str
    privacy_class: PrivacyClass
    recommended_action: PrivacyAction
