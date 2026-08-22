from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseConnector(ABC):
    """
    Abstract interface for future external security product connectors.
    Connectors are responsible ONLY for transport, authentication, HTTP requests,
    polling, pagination, and fetching raw vendor event payloads.
    They do NOT perform normalization or schema transformation.
    """
    @abstractmethod
    def fetch_raw_events(self) -> list[Dict[str, Any]]:
        """
        Fetches or receives raw vendor event payloads.
        """
        pass
