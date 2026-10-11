"""
DocxExtractor utilizing python-docx.
Extracts headings and paragraphs preserving section hierarchy.
"""

from pathlib import Path
from typing import List, Optional
from app.extractors.base import BaseExtractor, ExtractedBlock, ExtractedDocument


class DocxExtractor(BaseExtractor):
    """
    Extracts text from DOCX files using python-docx.
    Tracks heading hierarchies and paragraph indices.
    """

    SUPPORTED_EXTS = {".docx"}

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
                file_type="docx",
                extraction_status="ERROR",
                error_message=f"File not found: {target}",
            )

        try:
            import docx
        except ImportError:
            return ExtractedDocument(
                file_path=canonical_str,
                filename=target.name,
                extension=ext,
                file_type="docx",
                extraction_status="ERROR",
                error_message="python-docx is not installed.",
            )

        try:
            doc = docx.Document(target)
        except Exception as e:
            return ExtractedDocument(
                file_path=canonical_str,
                filename=target.name,
                extension=ext,
                file_type="docx",
                extraction_status="ERROR",
                error_message=f"Failed to open DOCX document: {e}",
            )

        blocks: List[ExtractedBlock] = []
        current_heading: Optional[str] = None
        paragraph_counter = 0

        # 1. Process paragraphs
        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue

            paragraph_counter += 1
            style_name = p.style.name.lower() if p.style and p.style.name else ""

            if "heading" in style_name:
                current_heading = text
                blocks.append(
                    ExtractedBlock(
                        text=text,
                        location_type="section",
                        location_value=f"Section: {text}",
                        section_heading=text,
                        paragraph_index=paragraph_counter,
                    )
                )
            else:
                loc_val = f"Section: {current_heading}" if current_heading else f"Paragraph {paragraph_counter}"
                blocks.append(
                    ExtractedBlock(
                        text=text,
                        location_type="section",
                        location_value=loc_val,
                        section_heading=current_heading,
                        paragraph_index=paragraph_counter,
                    )
                )

        # 2. Process tables (if any)
        table_counter = 0
        for table in doc.tables:
            table_counter += 1
            table_rows_text = []
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_cells:
                    table_rows_text.append(" | ".join(row_cells))

            if table_rows_text:
                table_content = "\n".join(table_rows_text)
                loc_val = f"Table {table_counter}"
                if current_heading:
                    loc_val += f" · Section: {current_heading}"
                blocks.append(
                    ExtractedBlock(
                        text=table_content,
                        location_type="section",
                        location_value=loc_val,
                        section_heading=current_heading,
                    )
                )

        status = "OK" if blocks else "NO_TEXT"

        return ExtractedDocument(
            file_path=canonical_str,
            filename=target.name,
            extension=ext,
            file_type="docx",
            blocks=blocks,
            extraction_status=status,
        )
