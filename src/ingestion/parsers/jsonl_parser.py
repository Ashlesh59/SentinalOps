import json
from typing import Dict, Any, List
from .base import EventParser, ParseError

class JsonLinesParser(EventParser):
    def parse(self, content: bytes) -> List[Dict[str, Any]]:
        text = content.decode("utf-8")
        res = []
        for line_num, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    res.append(data)
                else:
                    raise ParseError(f"Line {line_num} does not contain a JSON object")
            except json.JSONDecodeError as e:
                raise ParseError(f"Invalid JSON at line {line_num}: {str(e)}")
        return res
