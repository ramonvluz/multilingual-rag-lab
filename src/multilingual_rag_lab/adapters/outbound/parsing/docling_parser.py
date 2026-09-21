from pathlib import Path

from multilingual_rag_lab.domain.errors import DependencyUnavailable, IngestionFailed


class DoclingParser:
    """Produces Docling's structured document for the Docling HybridChunker."""

    def parse(self, source: Path, file_type: str) -> object:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as error:
            raise DependencyUnavailable("Docling is unavailable") from error
        try:
            return DocumentConverter().convert(source).document
        except Exception as error:
            raise IngestionFailed("Docling could not parse the supplied document") from error
