"""
PDFExtractor utilizing PyMuPDF (fitz).
Extracts text page by page with precise page number metadata and handles scanned documents.
"""

from pathlib import Path
from typing import List
from app.extractors.base import BaseExtractor, ExtractedBlock, ExtractedDocument


class PDFExtractor(BaseExtractor):
    """
    Extracts text from PDF documents using PyMuPDF (fitz).
    Preserves exact page numbers (1-indexed) and detects non-text / scanned PDFs.
    """

    SUPPORTED_EXTS = {".pdf"}

    @classmethod
    def supported_extensions(cls) -> set[str]:
        return cls.SUPPORTED_EXTS

    def extract(self, file_path: Path) -> ExtractedDocument:
        target = Path(file_path).resolve()
        canonical_str = str(target).replace("\\", "/")
        ext = target.suffix.lower()

        if not target.exists():
            return ExtractedDocument(
                file_path=canonical_str,
                filename=target.name,
                extension=ext,
                file_type="pdf",
                extraction_status="ERROR",
                error_message=f"File not found: {target}",
            )

        try:
            import pymupdf as fitz
        except ImportError:
            try:
                import fitz
            except ImportError:
                return ExtractedDocument(
                    file_path=canonical_str,
                    filename=target.name,
                    extension=ext,
                    file_type="pdf",
                    extraction_status="ERROR",
                    error_message="PyMuPDF is not installed.",
                )

        try:
            doc = fitz.open(target)
        except Exception as e:
            return ExtractedDocument(
                file_path=canonical_str,
                filename=target.name,
                extension=ext,
                file_type="pdf",
                extraction_status="ERROR",
                error_message=f"Failed to open PDF document: {e}",
            )

        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            return ExtractedDocument(
                file_path=canonical_str,
                filename=target.name,
                extension=ext,
                file_type="pdf",
                blocks=[],
                total_pages=0,
                extraction_status="NO_TEXT",
            )

        blocks: List[ExtractedBlock] = []
        has_any_text = False

        try:
            for page_idx in range(total_pages):
                page = doc[page_idx]
                page_number = page_idx + 1
                page_text = page.get_text("text")

                if page_text and page_text.strip():
                    has_any_text = True
                    # Split page into paragraphs to maintain structural granularity
                    raw_paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]
                    
                    if not raw_paragraphs:
                        # Fallback to full page text
                        raw_paragraphs = [page_text.strip()]

                    for p_idx, para in enumerate(raw_paragraphs, start=1):
                        blocks.append(
                            ExtractedBlock(
                                text=para,
                                location_type="page",
                                location_value=f"Page {page_number} of {total_pages}",
                                page_number=page_number,
                                start_page=page_number,
                                end_page=page_number,
                                paragraph_index=p_idx,
                            )
                        )
        except Exception as e:
            doc.close()
            return ExtractedDocument(
                file_path=canonical_str,
                filename=target.name,
                extension=ext,
                file_type="pdf",
                blocks=blocks,
                total_pages=total_pages,
                extraction_status="ERROR",
                error_message=f"Error reading PDF pages: {e}",
            )
        finally:
            doc.close()

        status = "OK" if has_any_text else "NO_TEXT"

        return ExtractedDocument(
            file_path=canonical_str,
            filename=target.name,
            extension=ext,
            file_type="pdf",
            blocks=blocks,
            total_pages=total_pages,
            extraction_status=status,
        )
