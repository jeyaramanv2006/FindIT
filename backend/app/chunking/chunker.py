"""
Structure-Aware Chunking Engine
Splits extracted document blocks into location-preserved passages
with 350-token sliding window and 50-token overlap.
Never crosses slide boundaries and preserves page, line, and heading coordinates.
"""

import re
from dataclasses import dataclass
from typing import List, Optional
from app.extractors.base import ExtractedBlock, ExtractedDocument


@dataclass
class Chunk:
    """
    A single searchable passage chunk ready for embedding and indexing.
    Maps 1:1 to SQLite passages table record.
    """
    chunk_id: str
    document_id: str
    chunk_ordinal: int
    text: str
    token_count: int
    location_type: str  # "page", "slide", "lines", "section"
    location_value: str  # "Page 4", "Slide 12", "Lines 45–80"
    page_number: Optional[int] = None
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    slide_number: Optional[int] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    section_heading: Optional[str] = None
    paragraph_index: Optional[int] = None


def count_tokens(text: str) -> int:
    """
    Estimates token count for MiniLM embedding model.
    Standard heuristic: ~1.3 tokens per whitespace-delimited word + punctuation tokens.
    """
    if not text:
        return 0
    words = re.findall(r"\w+|[^\w\s]", text)
    return max(1, len(words))


class StructureAwareChunker:
    """
    Chunks extracted document blocks into ~350 token passages with ~50 token overlap.
    Preserves document structure:
    - PPTX slides are chunked independently (never cross slide boundaries).
    - PDF pages maintain exact page numbers (or page spans).
    - Code and Markdown track exact 1-indexed line ranges and heading paths.
    - DOCX tracks sections and paragraph groupings.
    """

    def __init__(self, target_tokens: int = 350, overlap_tokens: int = 50):
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens

    def chunk_document(self, document_id: str, doc: ExtractedDocument) -> List[Chunk]:
        if not doc.blocks:
            return []

        if doc.file_type == "pptx":
            return self._chunk_pptx(document_id, doc)
        elif doc.file_type == "pdf":
            return self._chunk_pdf(document_id, doc)
        elif doc.file_type in {"code", "md", "txt", "config"}:
            return self._chunk_text_with_lines(document_id, doc)
        elif doc.file_type == "docx":
            return self._chunk_docx(document_id, doc)
        else:
            return self._chunk_generic(document_id, doc)

    def _create_chunk(
        self,
        document_id: str,
        ordinal: int,
        text: str,
        location_type: str,
        location_value: str,
        page_number: Optional[int] = None,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
        slide_number: Optional[int] = None,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        section_heading: Optional[str] = None,
        paragraph_index: Optional[int] = None,
    ) -> Chunk:
        token_count = count_tokens(text)
        chunk_id = f"{document_id}_{ordinal:04d}"
        return Chunk(
            chunk_id=chunk_id,
            document_id=document_id,
            chunk_ordinal=ordinal,
            text=text.strip(),
            token_count=token_count,
            location_type=location_type,
            location_value=location_value,
            page_number=page_number,
            start_page=start_page,
            end_page=end_page,
            slide_number=slide_number,
            start_line=start_line,
            end_line=end_line,
            section_heading=section_heading,
            paragraph_index=paragraph_index,
        )

    def _split_text_into_sliding_windows(self, text: str) -> List[str]:
        """
        Splits text by sentences or paragraphs using a sliding window.
        """
        # Split into sentence-like units
        units = [s.strip() for s in re.split(r"(?<=[.!?\n])\s+", text) if s.strip()]
        if not units:
            return [text] if text.strip() else []

        windows: List[str] = []
        current_window: List[str] = []
        current_tokens = 0

        for unit in units:
            unit_tokens = count_tokens(unit)
            if current_tokens + unit_tokens > self.target_tokens and current_window:
                windows.append(" ".join(current_window))

                # Compute overlap window
                overlap: List[str] = []
                overlap_tokens = 0
                for prev in reversed(current_window):
                    p_tokens = count_tokens(prev)
                    if overlap_tokens + p_tokens <= self.overlap_tokens:
                        overlap.insert(0, prev)
                        overlap_tokens += p_tokens
                    else:
                        break

                current_window = overlap + [unit]
                current_tokens = overlap_tokens + unit_tokens
            else:
                current_window.append(unit)
                current_tokens += unit_tokens

        if current_window:
            windows.append(" ".join(current_window))

        return windows

    def _chunk_pptx(self, document_id: str, doc: ExtractedDocument) -> List[Chunk]:
        """
        Each slide is chunked independently. Never crosses slide boundaries.
        """
        chunks: List[Chunk] = []
        ordinal = 0

        for block in doc.blocks:
            slide_num = block.slide_number or 1
            tokens = count_tokens(block.text)

            if tokens <= self.target_tokens:
                chunks.append(
                    self._create_chunk(
                        document_id=document_id,
                        ordinal=ordinal,
                        text=block.text,
                        location_type="slide",
                        location_value=block.location_value or f"Slide {slide_num}",
                        slide_number=slide_num,
                        section_heading=block.section_heading,
                    )
                )
                ordinal += 1
            else:
                # Sub-chunk within slide only
                sub_windows = self._split_text_into_sliding_windows(block.text)
                for part_idx, win in enumerate(sub_windows, start=1):
                    loc_val = f"Slide {slide_num}"
                    if block.section_heading:
                        loc_val += f" · {block.section_heading}"
                    if len(sub_windows) > 1:
                        loc_val += f" (Part {part_idx})"

                    chunks.append(
                        self._create_chunk(
                            document_id=document_id,
                            ordinal=ordinal,
                            text=win,
                            location_type="slide",
                            location_value=loc_val,
                            slide_number=slide_num,
                            section_heading=block.section_heading,
                        )
                    )
                    ordinal += 1

        return chunks

    def _chunk_pdf(self, document_id: str, doc: ExtractedDocument) -> List[Chunk]:
        """
        PDF chunking preserves page coordinates.
        Groups paragraphs per page or splits oversized pages.
        """
        chunks: List[Chunk] = []
        ordinal = 0

        # Group blocks by page
        pages: dict[int, List[ExtractedBlock]] = {}
        for block in doc.blocks:
            p_num = block.page_number or 1
            pages.setdefault(p_num, []).append(block)

        total_pages = doc.total_pages or len(pages)

        for p_num in sorted(pages.keys()):
            page_blocks = pages[p_num]
            page_text = "\n\n".join(b.text for b in page_blocks if b.text.strip())
            p_tokens = count_tokens(page_text)

            if p_tokens <= self.target_tokens:
                chunks.append(
                    self._create_chunk(
                        document_id=document_id,
                        ordinal=ordinal,
                        text=page_text,
                        location_type="page",
                        location_value=f"Page {p_num} of {total_pages}",
                        page_number=p_num,
                        start_page=p_num,
                        end_page=p_num,
                    )
                )
                ordinal += 1
            else:
                # Multi-chunk on this page
                windows = self._split_text_into_sliding_windows(page_text)
                for win in windows:
                    chunks.append(
                        self._create_chunk(
                            document_id=document_id,
                            ordinal=ordinal,
                            text=win,
                            location_type="page",
                            location_value=f"Page {p_num} of {total_pages}",
                            page_number=p_num,
                            start_page=p_num,
                            end_page=p_num,
                        )
                    )
                    ordinal += 1

        return chunks

    def _chunk_text_with_lines(self, document_id: str, doc: ExtractedDocument) -> List[Chunk]:
        """
        Plain text, Markdown, code, and config chunking preserving exact 1-indexed lines.
        """
        chunks: List[Chunk] = []
        ordinal = 0

        for block in doc.blocks:
            b_tokens = count_tokens(block.text)
            if b_tokens <= self.target_tokens:
                chunks.append(
                    self._create_chunk(
                        document_id=document_id,
                        ordinal=ordinal,
                        text=block.text,
                        location_type="lines",
                        location_value=block.location_value,
                        start_line=block.start_line,
                        end_line=block.end_line,
                        section_heading=block.section_heading,
                    )
                )
                ordinal += 1
            else:
                # Break large block into sub-lines
                lines = block.text.splitlines()
                start_line = block.start_line or 1
                current_lines: List[str] = []
                current_tokens = 0
                sub_start = start_line

                for offset, line in enumerate(lines):
                    line_tokens = count_tokens(line)
                    curr_line_num = start_line + offset

                    if current_tokens + line_tokens > self.target_tokens and current_lines:
                        sub_end = curr_line_num - 1
                        loc_val = f"Lines {sub_start}–{sub_end}"
                        if block.section_heading:
                            loc_val += f" · {block.section_heading}"

                        chunks.append(
                            self._create_chunk(
                                document_id=document_id,
                                ordinal=ordinal,
                                text="\n".join(current_lines),
                                location_type="lines",
                                location_value=loc_val,
                                start_line=sub_start,
                                end_line=sub_end,
                                section_heading=block.section_heading,
                            )
                        )
                        ordinal += 1

                        # Keep overlap lines
                        overlap_lines: List[str] = []
                        overlap_tok = 0
                        for rev_line in reversed(current_lines):
                            r_tok = count_tokens(rev_line)
                            if overlap_tok + r_tok <= self.overlap_tokens:
                                overlap_lines.insert(0, rev_line)
                                overlap_tok += r_tok
                            else:
                                break

                        current_lines = overlap_lines + [line]
                        current_tokens = overlap_tok + line_tokens
                        sub_start = curr_line_num - len(overlap_lines)
                    else:
                        current_lines.append(line)
                        current_tokens += line_tokens

                if current_lines:
                    sub_end = start_line + len(lines) - 1
                    loc_val = f"Lines {sub_start}–{sub_end}"
                    if block.section_heading:
                        loc_val += f" · {block.section_heading}"

                    chunks.append(
                        self._create_chunk(
                            document_id=document_id,
                            ordinal=ordinal,
                            text="\n".join(current_lines),
                            location_type="lines",
                            location_value=loc_val,
                            start_line=sub_start,
                            end_line=sub_end,
                            section_heading=block.section_heading,
                        )
                    )
                    ordinal += 1

        return chunks

    def _chunk_docx(self, document_id: str, doc: ExtractedDocument) -> List[Chunk]:
        """
        DOCX chunking grouping paragraphs and sections.
        """
        chunks: List[Chunk] = []
        ordinal = 0

        current_heading: Optional[str] = None
        current_paragraphs: List[str] = []
        current_tokens = 0

        for block in doc.blocks:
            b_tokens = count_tokens(block.text)

            # If section changed, flush previous group to maintain section cohesion
            if block.section_heading != current_heading and current_paragraphs:
                loc_val = f"Section: {current_heading}" if current_heading else "Document Body"
                chunks.append(
                    self._create_chunk(
                        document_id=document_id,
                        ordinal=ordinal,
                        text="\n\n".join(current_paragraphs),
                        location_type="section",
                        location_value=loc_val,
                        section_heading=current_heading,
                    )
                )
                ordinal += 1
                current_paragraphs = []
                current_tokens = 0

            current_heading = block.section_heading

            if current_tokens + b_tokens > self.target_tokens and current_paragraphs:
                loc_val = f"Section: {current_heading}" if current_heading else "Document Body"
                chunks.append(
                    self._create_chunk(
                        document_id=document_id,
                        ordinal=ordinal,
                        text="\n\n".join(current_paragraphs),
                        location_type="section",
                        location_value=loc_val,
                        section_heading=current_heading,
                    )
                )
                ordinal += 1
                current_paragraphs = [block.text]
                current_tokens = b_tokens
            else:
                current_paragraphs.append(block.text)
                current_tokens += b_tokens

        if current_paragraphs:
            loc_val = f"Section: {current_heading}" if current_heading else "Document Body"
            chunks.append(
                self._create_chunk(
                    document_id=document_id,
                    ordinal=ordinal,
                    text="\n\n".join(current_paragraphs),
                    location_type="section",
                    location_value=loc_val,
                    section_heading=current_heading,
                )
            )
            ordinal += 1

        return chunks

    def _chunk_generic(self, document_id: str, doc: ExtractedDocument) -> List[Chunk]:
        chunks: List[Chunk] = []
        ordinal = 0
        for block in doc.blocks:
            chunks.append(
                self._create_chunk(
                    document_id=document_id,
                    ordinal=ordinal,
                    text=block.text,
                    location_type=block.location_type or "section",
                    location_value=block.location_value or "Content",
                )
            )
            ordinal += 1
        return chunks
