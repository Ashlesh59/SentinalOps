import secrets
from typing import Dict

class AliasService:
    """
    Generates investigation/package-scoped aliases for protected identities and assets.
    Ensures identical entities within the same package share the exact same alias,
    while mapping details are strictly preserved in local context only.
    Includes a random namespace per package to avoid cross-package identity continuity leakage.
    """
    def __init__(self):
        # Raw value -> Alias (e.g. "alice@bank.com" -> "USER_A7F3_001")
        self._raw_to_alias: Dict[str, str] = {}
        # Alias -> Raw value (e.g. "USER_A7F3_001" -> "alice@bank.com")
        self._alias_to_raw: Dict[str, str] = {}
        
        self.namespace = secrets.token_hex(2).upper()
        
        self._counters: Dict[str, int] = {
            "USER": 0,
            "HOST": 0,
            "PRIVATE_IP": 0,
            "ASSET": 0
        }

    def get_or_create_alias(self, raw_value: str, prefix: str) -> str:
        if not raw_value:
            return raw_value
            
        clean_value = raw_value.strip().lower()
        if clean_value in self._raw_to_alias:
            return self._raw_to_alias[clean_value]
            
        prefix_key = prefix.upper()
        if prefix_key not in self._counters:
            self._counters[prefix_key] = 0
            
        self._counters[prefix_key] += 1
        num = self._counters[prefix_key]
        alias = f"{prefix_key}_{self.namespace}_{num:03d}"
        
        self._raw_to_alias[clean_value] = alias
        self._alias_to_raw[alias] = clean_value
        return alias

    def get_alias_map(self) -> Dict[str, str]:
        """Returns alias -> raw_value map for local PackagePrivacyContext."""
        return dict(self._alias_to_raw)
