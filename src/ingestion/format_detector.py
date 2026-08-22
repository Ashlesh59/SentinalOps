import json
from typing import Tuple

class FormatDetector:
    @staticmethod
    def detect(filename: str, content_preview: bytes = b"") -> str:
        """
        Deterministically detects format based on filename and content.
        Returns one of: JSON, JSONL, CSV, UNKNOWN
        """
        filename_lower = filename.lower()
        if filename_lower.endswith(".csv"):
            return "CSV"
        elif filename_lower.endswith(".jsonl") or filename_lower.endswith(".ndjson"):
            return "JSONL"
        elif filename_lower.endswith(".json"):
            return "JSON"
            
        # Fallback to basic content sniffing if extension is ambiguous
        try:
            text = content_preview.decode("utf-8").strip()
            if text.startswith("[") or (text.startswith("{") and "\n" not in text and len(text) > 2 and text.endswith("}")):
                # This could be JSON array or single JSON.
                # Actually, JSONL can also start with {, but typically has multiple lines.
                return "JSON"
        except Exception:
            pass
            
        return "UNKNOWN"
