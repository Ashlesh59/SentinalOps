from abc import ABC, abstractmethod
from typing import Dict, Any, List

class ParseError(Exception):
    pass

class EventParser(ABC):
    @abstractmethod
    def parse(self, content: bytes) -> List[Dict[str, Any]]:
        """
        Parses raw bytes into a list of raw event dictionaries.
        """
        pass
