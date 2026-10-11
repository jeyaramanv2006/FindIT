"""
BaseExtractor & ExtractedDocument domain definitions
Defines the contract and structured representation for all multi-format extractors.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List


@dataclass
class ExtractedBlock:
    """
    A discrete semantic or structural block extracted from a document.
    Preserves exact location metadata (page, slide, line range, section).
    """
    text: str
    location_type: str  # "page", "slide", "lines", "section"
    location_value: str  # Formatted human-readable label: "Page 1 of 12", "Slide 3", "Lines 45–80"
    page_number: Optional[int] = None
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    slide_number: Optional[int] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    section_heading: Optional[str] = None
    paragraph_index: Optional[int] = None


@dataclass
class ExtractedDocument:
    """
    Represents the complete extracted contents of a source document.
    Contains sequence of extracted blocks and file-level metrics.
    """
    file_path: str
    filename: str
    extension: str
    file_type: str
    blocks: List[ExtractedBlock] = field(default_factory=list)
    total_pages: Optional[int] = None
    total_slides: Optional[int] = None
    total_lines: Optional[int] = None
    extraction_status: str = "OK"  # "OK", "NO_TEXT", "ERROR", "UNSUPPORTED"
    error_message: Optional[str] = None

    @property
    def has_content(self) -> bool:
        return any(bool(b.text.strip()) for b in self.blocks)


class BaseExtractor(ABC):
    """Abstract interface that all format-specific extractors must implement."""

    @abstractmethod
    def extract(self, file_path: Path) -> ExtractedDocument:
        """
        Extracts textual content and structural coordinates from the given file.
        Must handle errors gracefully and return ExtractedDocument with appropriate status.
        """
        pass

    @classmethod
    @abstractmethod
    def supported_extensions(cls) -> set[str]:
        """Returns the set of lowercase file extensions supported by this extractor."""
        pass
