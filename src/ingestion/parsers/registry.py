from typing import Type
from .base import EventParser
from .json_parser import JsonParser
from .jsonl_parser import JsonLinesParser
from .csv_parser import CsvParser

class ParserRegistry:
    _parsers = {
        "JSON": JsonParser,
        "JSONL": JsonLinesParser,
        "CSV": CsvParser
    }

    @classmethod
    def get_parser(cls, format_name: str) -> EventParser:
        parser_cls = cls._parsers.get(format_name.upper())
        if not parser_cls:
            raise ValueError(f"No parser available for format: {format_name}")
        return parser_cls()
