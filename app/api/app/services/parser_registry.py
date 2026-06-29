from abc import ABC, abstractmethod
from typing import Type

from .doc_parser import ParsedClause


class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> list[ParsedClause]:
        ...

    @classmethod
    def supported_extensions(cls) -> list[str]:
        return []


_REGISTRY: dict[str, Type[BaseParser]] = {}


def register_parser(ext: str, parser_cls: Type[BaseParser]):
    _REGISTRY[ext.lower().lstrip(".")] = parser_cls


def get_parser(ext: str) -> BaseParser | None:
    cls = _REGISTRY.get(ext.lower().lstrip("."))
    return cls() if cls else None


def supported_formats() -> list[str]:
    return sorted(_REGISTRY.keys())


class DocxParser(BaseParser):
    def parse(self, file_path: str) -> list[ParsedClause]:
        from .doc_parser import parse_docx
        return parse_docx(file_path)

    @classmethod
    def supported_extensions(cls) -> list[str]:
        return ["docx"]


class PdfParser(BaseParser):
    def parse(self, file_path: str) -> list[ParsedClause]:
        from .pdf_parser import parse_pdf
        return parse_pdf(file_path)

    @classmethod
    def supported_extensions(cls) -> list[str]:
        return ["pdf"]


register_parser("docx", DocxParser)
register_parser("pdf", PdfParser)
