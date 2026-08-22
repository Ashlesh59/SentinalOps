import json
from typing import Dict, Any, List
from .base import EventParser, ParseError

class JsonParser(EventParser):
    def parse(self, content: bytes) -> List[Dict[str, Any]]:
        try:
            data = json.loads(content)
            if isinstance(data, list):
                # Ensure all elements are dicts
                res = []
                for item in data:
                    if isinstance(item, dict):
                        res.append(item)
                    else:
                        raise ParseError("JSON array contains non-object elements")
                return res
            elif isinstance(data, dict):
                # We need to extract the events. Maybe it's a single event, or maybe under a key.
                # The prompt says "single REST JSON" or standard JSON files. 
                # If it's a dict, we treat it as a single event.
                return [data]
            else:
                raise ParseError("Root of JSON must be an object or array")
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON: {str(e)}")
