from abc import ABC, abstractmethod
from typing import Dict, Any
from src.models.schema import NormalizedAlert

class BaseNormalizer(ABC):
    """
    Abstract interface for vendor event normalizers.
    Normalizers translate raw vendor payload dictionaries into SentinelOps NormalizedAlert objects.
    They perform safe canonicalization (e.g. trimming strings, lowercasing users)
    and pass raw timestamp values to NormalizedAlert for strict validation.
    They MUST preserve a deep copy of raw_event.
    """
    @abstractmethod
    def normalize(self, raw_event: Dict[str, Any], tenant_id: str = "default-tenant") -> NormalizedAlert:
        """
        Transforms raw vendor dictionary into a validated NormalizedAlert.
        Does NOT invent missing timestamps or IDs.
        """
        pass
