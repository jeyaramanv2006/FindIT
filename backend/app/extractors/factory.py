"""
Extractor Factory
Resolves the appropriate BaseExtractor implementation based on file extension.
"""

from pathlib import Path
from typing import Optional
from app.extractors.base import BaseExtractor
from app.extractors.text_extractor import TextExtractor
from app.extractors.pdf_extractor import PDFExtractor
from app.extractors.docx_extractor import DocxExtractor
from app.extractors.pptx_extractor import PptxExtractor

_EXTRACTORS = [
    TextExtractor(),
    PDFExtractor(),
    DocxExtractor(),
    PptxExtractor(),
]


def get_extractor_for_file(file_path: Path | str) -> Optional[BaseExtractor]:
    """
    Returns the appropriate BaseExtractor for the file's extension,
    or None if the extension is unsupported.
    """
    ext = Path(file_path).suffix.lower()
    for extractor in _EXTRACTORS:
        if ext in extractor.supported_extensions():
            return extractor
    return None
