from pathlib import Path

from multilingual_rag_lab.domain.errors import DependencyUnavailable, IngestionFailed


class DoclingParser:
    """Docling-backed parser; Markdown/HTML/CSV retain a small deterministic fallback."""

    def parse(self, source: Path, file_type: str) -> str:
        if file_type in {"md", "html", "csv"}:
            return source.read_text(encoding="utf-8", errors="replace")
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as error:
            raise DependencyUnavailable("Docling is unavailable") from error
        try:
            result = DocumentConverter().convert(source)
            return result.document.export_to_markdown()
        except Exception as error:
            raise IngestionFailed("Docling could not parse the supplied document") from error
