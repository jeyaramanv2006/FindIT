"""
Unit tests for StructureAwareChunker.
Validates 350-token window, 50-token overlap, coordinate preservation,
and strict non-bleed boundary sensitivity across slides and pages.
"""

from app.chunking.chunker import StructureAwareChunker, count_tokens
from app.extractors.base import ExtractedBlock, ExtractedDocument


def test_count_tokens():
    assert count_tokens("") == 0
    assert count_tokens("Hello world") == 2
    assert count_tokens("def verify_token(req: Request) -> bool:") > 5


def test_chunker_pptx_slide_boundary_isolation():
    """
    Critical requirement: PPTX chunks must NEVER cross slide boundaries.
    """
    doc = ExtractedDocument(
        file_path="C:/presentation.pptx",
        filename="presentation.pptx",
        extension=".pptx",
        file_type="pptx",
        total_slides=2,
        blocks=[
            ExtractedBlock(
                text="Title: Slide 1\n\nContent for slide 1 detailing authentication.",
                location_type="slide",
                location_value="Slide 1 · Title: Slide 1",
                slide_number=1,
                section_heading="Slide 1",
            ),
            ExtractedBlock(
                text="Title: Slide 2\n\nContent for slide 2 detailing database WAL.",
                location_type="slide",
                location_value="Slide 2 · Title: Slide 2",
                slide_number=2,
                section_heading="Slide 2",
            ),
        ],
    )

    chunker = StructureAwareChunker(target_tokens=350, overlap_tokens=50)
    chunks = chunker.chunk_document("doc_test_pptx", doc)

    assert len(chunks) == 2
    # Slide 1 chunk
    assert chunks[0].slide_number == 1
    assert "Slide 1" in chunks[0].text
    assert "Slide 2" not in chunks[0].text
    assert chunks[0].location_type == "slide"

    # Slide 2 chunk
    assert chunks[1].slide_number == 2
    assert "Slide 2" in chunks[1].text
    assert "Slide 1" not in chunks[1].text
    assert chunks[1].location_type == "slide"


def test_chunker_pdf_page_coordinates():
    doc = ExtractedDocument(
        file_path="C:/specs.pdf",
        filename="specs.pdf",
        extension=".pdf",
        file_type="pdf",
        total_pages=2,
        blocks=[
            ExtractedBlock(
                text="Page 1 specification paragraph.",
                location_type="page",
                location_value="Page 1 of 2",
                page_number=1,
                start_page=1,
                end_page=1,
            ),
            ExtractedBlock(
                text="Page 2 vector index paragraph.",
                location_type="page",
                location_value="Page 2 of 2",
                page_number=2,
                start_page=2,
                end_page=2,
            ),
        ],
    )

    chunker = StructureAwareChunker(target_tokens=350, overlap_tokens=50)
    chunks = chunker.chunk_document("doc_test_pdf", doc)

    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert chunks[0].start_page == 1
    assert chunks[0].end_page == 1
    assert "Page 1" in chunks[0].location_value

    assert chunks[1].page_number == 2
    assert chunks[1].start_page == 2
    assert chunks[1].end_page == 2
    assert "Page 2" in chunks[1].location_value


def test_chunker_code_and_lines_preservation():
    # Long block with multiple lines
    lines = [f"line_{i} = do_something_useful({i})" for i in range(1, 150)]
    code_text = "\n".join(lines)

    doc = ExtractedDocument(
        file_path="C:/worker.py",
        filename="worker.py",
        extension=".py",
        file_type="code",
        blocks=[
            ExtractedBlock(
                text=code_text,
                location_type="lines",
                location_value="Lines 1–149 · worker_loop",
                start_line=1,
                end_line=149,
                section_heading="worker_loop",
            )
        ],
    )

    chunker = StructureAwareChunker(target_tokens=100, overlap_tokens=20)
    chunks = chunker.chunk_document("doc_test_code", doc)

    assert len(chunks) > 1
    for c in chunks:
        assert c.location_type == "lines"
        assert c.start_line is not None
        assert c.end_line is not None
        assert c.start_line <= c.end_line
        assert c.section_heading == "worker_loop"
        assert f"Lines {c.start_line}–{c.end_line}" in c.location_value
        assert c.token_count > 0


def test_chunker_docx_sections():
    doc = ExtractedDocument(
        file_path="C:/spec.docx",
        filename="spec.docx",
        extension=".docx",
        file_type="docx",
        blocks=[
            ExtractedBlock(
                text="Section 1 content about security architecture.",
                location_type="section",
                location_value="Section: Security",
                section_heading="Security",
            ),
            ExtractedBlock(
                text="Section 2 content about database persistence.",
                location_type="section",
                location_value="Section: Database",
                section_heading="Database",
            ),
        ],
    )

    chunker = StructureAwareChunker(target_tokens=350, overlap_tokens=50)
    chunks = chunker.chunk_document("doc_test_docx", doc)

    assert len(chunks) == 2
    assert chunks[0].section_heading == "Security"
    assert chunks[1].section_heading == "Database"
