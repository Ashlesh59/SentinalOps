from typing import Dict
from pydantic import BaseModel, Field
from src.models.privacy import PrivacyClass, PrivacyAction

class PrivacyPolicy(BaseModel):
    name: str = Field(default="STRICT_EXTERNAL")
    class_actions: Dict[PrivacyClass, PrivacyAction] = Field(default_factory=dict)
    
    @classmethod
    def strict_external(cls) -> "PrivacyPolicy":
        return cls(
            name="STRICT_EXTERNAL",
            class_actions={
                PrivacyClass.SECRET: PrivacyAction.REDACT,
                PrivacyClass.DIRECT_IDENTIFIER: PrivacyAction.TOKENIZE,
                PrivacyClass.INTERNAL_ASSET_IDENTIFIER: PrivacyAction.TOKENIZE,
                PrivacyClass.QUASI_IDENTIFIER: PrivacyAction.GENERALIZE,
                PrivacyClass.PUBLIC_SECURITY_INDICATOR: PrivacyAction.ALLOW,
                PrivacyClass.SECURITY_SEMANTIC: PrivacyAction.ALLOW,
                PrivacyClass.SECURITY_CONTEXT: PrivacyAction.ALLOW,
                PrivacyClass.SAFE_METADATA: PrivacyAction.ALLOW,
                PrivacyClass.UNCLASSIFIED_FREE_TEXT: PrivacyAction.LOCAL_ONLY,
            }
        )

    def get_action(self, p_class: PrivacyClass) -> PrivacyAction:
        return self.class_actions.get(p_class, PrivacyAction.REDACT)
