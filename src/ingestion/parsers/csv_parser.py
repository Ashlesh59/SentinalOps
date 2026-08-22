import csv
import io
from typing import Dict, Any, List
from .base import EventParser, ParseError

class CsvParser(EventParser):
    def parse(self, content: bytes) -> List[Dict[str, Any]]:
        try:
            text = content.decode("utf-8")
            f = io.StringIO(text)
            reader = csv.DictReader(f)
            res = []
            for row in reader:
                # Filter out empty keys if any
                clean_row = {k: v for k, v in row.items() if k is not None}
                res.append(clean_row)
            return res
        except Exception as e:
            raise ParseError(f"CSV parsing error: {str(e)}")
