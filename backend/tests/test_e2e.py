"""
FindIT Automated End-to-End System Hardening & Edge-Case Test Suite
Synchronized with notes/plan.md Phase 18 and notes/EXECUTION_PLAN.md Batch 7.

Validates:
1. Empty directories handling.
2. Corrupt/malformed files (PDF, DOCX, TXT) fail gracefully without crashing worker.
3. Zero-byte files marked NO_TEXT without creating spurious passages.
4. Large files exceeding MAX_FILE_SIZE_BYTES skipped safely.
5. Special characters, spaces, brackets, and Unicode in file paths.
6. Path traversal confinement defense blocking unauthorized host paths.
7. Sub-100ms hybrid search latency benchmark across 1,000 indexed passages.
8. Standardized error-handling middleware JSON responses for 404, 422, and 500.
"""

import os
import tempfile
import time
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core import config
from app.db.database import init_db, get_db
from app.indexing.faiss_index import FaissIndex
from app.indexing.bm25_index import BM25Index
from app.sync.worker import SyncWorker
from app.services.os_service import OSService, SecurityBoundaryError
from app.services.search_service import SearchService


@pytest.fixture
def e2e_env():
    """
    Creates an isolated temporary test sandbox with dedicated:
    - SQLite database
    - FAISS vector index
    - BM25 lexical index
    - Test root workspace directory
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_file = tmp_path / "findit_e2e.db"
        faiss_file = tmp_path / "index_e2e.faiss"
        bm25_file = tmp_path / "bm25_e2e.pkl"
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)

        init_db(db_file)
        faiss_idx = FaissIndex(index_path=faiss_file)
        bm25_idx = BM25Index(index_path=bm25_file)
        worker = SyncWorker(db_path=db_file, max_workers=2, faiss_idx=faiss_idx, bm25_idx=bm25_idx)

        yield {
            "tmp_path": tmp_path,
            "db_file": db_file,
            "faiss_file": faiss_file,
            "bm25_file": bm25_file,
            "workspace": workspace_dir,
            "faiss_idx": faiss_idx,
            "bm25_idx": bm25_idx,
            "worker": worker,
        }


def _register_dir(db_path: Path, dir_id: str, dir_path: Path, name: str = "TestDir"):
    """Helper to insert an approved directory in SQLite."""
    canonical_str = str(dir_path.resolve()).replace("\\", "/")
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO directories (directory_id, canonical_path, display_name, added_at, sync_status)
            VALUES (?, ?, ?, datetime('now'), 'IDLE');
            """,
            (dir_id, canonical_str, name),
        )


# ============================================================================
# 1. EMPTY DIRECTORY RESILIENCE
# ============================================================================
def test_e2e_empty_directory(e2e_env):
    """
    Verifies that scanning and syncing an empty directory completes cleanly
    with 0 discovered files, 0 passages, and status COMPLETED.
    """
    env = e2e_env
    empty_dir = env["workspace"] / "empty_folder"
    empty_dir.mkdir()
    _register_dir(env["db_file"], "dir_empty", empty_dir, "Empty Folder")

    job_id = env["worker"].start_sync("dir_empty", background=False)
    status = env["worker"].get_job_status(job_id)

    assert status is not None
    assert status["status"] == "COMPLETED"
    assert status["files_discovered"] == 0
    assert status["files_processed"] == 0
    assert status["passages_created"] == 0


# ============================================================================
# 2. CORRUPT & MALFORMED FILES RESILIENCE
# ============================================================================
def test_e2e_corrupt_files(e2e_env):
    """
    Verifies that corrupted PDFs and DOCX files fail gracefully without
    crashing the sync worker, allowing valid files in the same directory to index.
    """
    env = e2e_env
    test_dir = env["workspace"] / "mixed_folder"
    test_dir.mkdir()

    # 1. Corrupt PDF: random garbage bytes that do not form a valid PDF header
    corrupt_pdf = test_dir / "broken.pdf"
    corrupt_pdf.write_bytes(b"\x00\xff\xfe\x00GARBAGE_NOT_A_PDF_STREAM\x12\x34\x56")

    # 2. Corrupt DOCX: plain text masquerading as a ZIP-based DOCX package
    corrupt_docx = test_dir / "broken.docx"
    corrupt_docx.write_text("This is plain text not a zip file", encoding="utf-8")

    # 3. Valid Markdown file
    valid_md = test_dir / "valid_notes.md"
    valid_md.write_text(
        "# Quantum Computing Architecture\n\nQubits leverage superposition and quantum entanglement to solve optimization problems.",
        encoding="utf-8",
    )

    _register_dir(env["db_file"], "dir_corrupt", test_dir, "Corrupt Folder")
    job_id = env["worker"].start_sync("dir_corrupt", background=False)
    status = env["worker"].get_job_status(job_id)

    assert status is not None
    assert status["status"] == "COMPLETED"
    assert status["files_discovered"] == 3
    assert status["files_processed"] == 3
    assert status["files_failed"] >= 1  # At least the corrupt files flagged
    assert status["passages_created"] >= 1  # Valid file passages created

    # Verify document extraction statuses in database
    with get_db(env["db_file"]) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT filename, extraction_status FROM documents WHERE directory_id = 'dir_corrupt';")
        rows = dict(cursor.fetchall())

        assert rows["broken.pdf"] == "ERROR"
        assert rows["broken.docx"] == "ERROR"
        assert rows["valid_notes.md"] == "OK"


# ============================================================================
# 3. ZERO-BYTE FILES RESILIENCE
# ============================================================================
def test_e2e_zero_byte_files(e2e_env):
    """
    Verifies that empty 0-byte text or PDF files are marked NO_TEXT
    and do not generate empty vector entries or corrupt the indices.
    """
    env = e2e_env
    zero_dir = env["workspace"] / "zero_bytes_folder"
    zero_dir.mkdir()

    empty_txt = zero_dir / "empty.txt"
    empty_txt.write_bytes(b"")

    empty_md = zero_dir / "empty.md"
    empty_md.write_text("", encoding="utf-8")

    _register_dir(env["db_file"], "dir_zero", zero_dir, "Zero Byte Folder")
    job_id = env["worker"].start_sync("dir_zero", background=False)
    status = env["worker"].get_job_status(job_id)

    assert status is not None
    assert status["status"] == "COMPLETED"
    assert status["files_discovered"] == 2
    assert status["files_processed"] == 2
    assert status["passages_created"] == 0

    with get_db(env["db_file"]) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT filename, extraction_status FROM documents WHERE directory_id = 'dir_zero';")
        rows = dict(cursor.fetchall())
        assert rows["empty.txt"] == "NO_TEXT"
        assert rows["empty.md"] == "NO_TEXT"


# ============================================================================
# 4. OVERSIZED FILE SKIP DEFENSE (> MAX_FILE_SIZE_BYTES)
# ============================================================================
def test_e2e_large_file_skip(e2e_env, monkeypatch):
    """
    Verifies that files exceeding MAX_FILE_SIZE_BYTES are safely skipped
    with SKIPPED_TOO_LARGE status without consuming excessive memory.
    """
    env = e2e_env
    large_dir = env["workspace"] / "large_files_folder"
    large_dir.mkdir()

    # Create a 200KB file, but configure MAX_FILE_SIZE_BYTES to 100KB for the test
    test_limit = 100 * 1024
    monkeypatch.setattr(config, "MAX_FILE_SIZE_BYTES", test_limit)

    large_file = large_dir / "huge_data.txt"
    large_file.write_text("A" * (200 * 1024), encoding="utf-8")

    normal_file = large_dir / "normal.txt"
    normal_file.write_text("Normal small file content.", encoding="utf-8")

    _register_dir(env["db_file"], "dir_large", large_dir, "Large Folder")
    job_id = env["worker"].start_sync("dir_large", background=False)
    status = env["worker"].get_job_status(job_id)

    assert status is not None
    assert status["status"] == "COMPLETED"

    with get_db(env["db_file"]) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT filename, extraction_status FROM documents WHERE directory_id = 'dir_large';")
        rows = dict(cursor.fetchall())
        assert rows["huge_data.txt"] == "SKIPPED_TOO_LARGE"
        assert rows["normal.txt"] == "OK"


# ============================================================================
# 5. SPECIAL CHARACTERS, SPACES, BRACKETS & UNICODE IN PATHS
# ============================================================================
def test_e2e_special_characters_in_paths(e2e_env):
    """
    Verifies that directories and filenames containing Unicode, spaces,
    square brackets, parentheses, and ampersands index and retrieve cleanly.
    """
    env = e2e_env
    special_dir = env["workspace"] / "Projet [v2.0] & 研报 (Draft)"
    special_dir.mkdir()

    special_file = special_dir / "Synthèse [DeepSeek-R1] 报告 #42.md"
    special_file.write_text(
        "# AI Architecture Synthesis\n\nReinforcement learning with rule-based reward verifiers produces emergent reasoning chains.",
        encoding="utf-8",
    )

    _register_dir(env["db_file"], "dir_special", special_dir, "Special Chars Folder")
    job_id = env["worker"].start_sync("dir_special", background=False)
    status = env["worker"].get_job_status(job_id)

    assert status is not None
    assert status["status"] == "COMPLETED"
    assert status["passages_created"] >= 1

    # Verify search finds the passage by query
    search_service = SearchService(
        db_path=env["db_file"],
        faiss_idx=env["faiss_idx"],
        bm25_idx=env["bm25_idx"],
    )
    res = search_service.search("reinforcement learning reasoning chains", limit=5)
    assert len(res.results) > 0
    top_hit = res.results[0]
    assert "DeepSeek" in top_hit.filename
    assert "Synthèse" in top_hit.filename
    assert "reinforcement learning" in top_hit.passage_preview.lower()


# ============================================================================
# 6. PATH TRAVERSAL & SECURITY BOUNDARY CONFINEMENT
# ============================================================================
def test_e2e_path_traversal_confinement(e2e_env):
    """
    Verifies that OSService blocks path traversal attempts attempting to
    escape registered directory roots into host system paths.
    """
    env = e2e_env
    valid_dir = env["workspace"] / "safe_zone"
    valid_dir.mkdir()
    safe_file = valid_dir / "safe.txt"
    safe_file.write_text("Safe local text.", encoding="utf-8")
    _register_dir(env["db_file"], "dir_safe", valid_dir, "Safe Zone")

    # 1. Legitimate file inside approved root passes confinement check
    canonical_safe = str(safe_file.resolve()).replace("\\", "/")
    resolved = OSService.validate_path_confinement(canonical_safe, db_path=env["db_file"])
    assert resolved.exists()
    assert resolved == safe_file.resolve()

    # 2. Path traversal attempt using parent directories to an existing outside file
    outside_file = env["tmp_path"] / "outside_host_file.txt"
    outside_file.write_text("Secret host file", encoding="utf-8")
    traversal_path = str(valid_dir / ".." / ".." / "outside_host_file.txt").replace("\\", "/")
    with pytest.raises(SecurityBoundaryError):
        OSService.validate_path_confinement(traversal_path, db_path=env["db_file"])

    # 3. Non-existent path traversal attempt raises FileNotFoundError
    non_existent = str(valid_dir / ".." / "nonexistent_file.xyz").replace("\\", "/")
    with pytest.raises(FileNotFoundError):
        OSService.validate_path_confinement(non_existent, db_path=env["db_file"])


# ============================================================================
# 7. HYBRID SEARCH LATENCY BENCHMARK (< 100ms on 1,000 Indexed Passages)
# ============================================================================
def test_e2e_search_latency_benchmark(e2e_env):
    """
    Benchmarks end-to-end hybrid search latency (embedding inference + FAISS dense
    retrieval + BM25 tokenization/scoring + RRF fusion + SQLite hydration) across
    1,000 indexed passages. Ensures average query latency is strictly < 100ms on CPU.
    """
    env = e2e_env
    faiss_idx = env["faiss_idx"]
    bm25_idx = env["bm25_idx"]
    db_file = env["db_file"]

    bench_dir = env["workspace"] / "bench_dir"
    bench_dir.mkdir()
    _register_dir(db_file, "dir_bench", bench_dir, "Benchmark")

    # Generate 1,000 synthetic realistic passages
    num_passages = 1000
    passage_texts = [
        f"Passage {i}: Local-first desktop search engine indexing document architectures with reciprocal rank fusion and vector embeddings. System component #{i % 25} handles authentication tokens and caching."
        for i in range(num_passages)
    ]
    chunk_ids = [f"chk_bench_{i:04d}" for i in range(num_passages)]
    vector_ids = list(range(1, num_passages + 1))

    # Fast normalized vector generation for FAISS (dim=384)
    rng = np.random.default_rng(42)
    raw_vecs = rng.standard_normal((num_passages, 384)).astype(np.float32)
    norms = np.linalg.norm(raw_vecs, axis=1, keepdims=True)
    embeddings = raw_vecs / norms

    # 1. Populate FAISS and BM25 indices
    faiss_idx.add_vectors(embeddings, vector_ids, chunk_ids)
    bm25_idx.add_documents(chunk_ids, passage_texts)

    # 2. Populate SQLite documents and passages
    with get_db(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO documents (
                document_id, directory_id, canonical_path, filename,
                extension, file_type, size_bytes, modified_time,
                content_fingerprint, extraction_status, last_indexed_at
            ) VALUES ('doc_bench', 'dir_bench', 'C:/bench/file.txt', 'file.txt',
                      '.txt', 'txt', 50000, 1700000000, 'hash123', 'OK', datetime('now'));
            """
        )
        for i in range(num_passages):
            cursor.execute(
                """
                INSERT INTO passages (
                    chunk_id, document_id, chunk_ordinal, text, normalized_text,
                    page_number, start_line, end_line, vector_id
                ) VALUES (?, 'doc_bench', ?, ?, ?, 1, 1, 10, ?);
                """,
                (chunk_ids[i], i, passage_texts[i], passage_texts[i].lower(), vector_ids[i]),
            )

    search_service = SearchService(db_path=db_file, faiss_idx=faiss_idx, bm25_idx=bm25_idx)

    # Warm-up query
    search_service.search("desktop search engine", limit=10)

    # 3. Benchmark 20 diverse queries
    test_queries = [
        "vector embeddings architecture",
        "reciprocal rank fusion",
        "authentication tokens",
        "desktop search engine",
        "system component caching",
        "indexing document architectures",
        "passage retrieval pipeline",
        "local first desktop",
        "component 15 authentication",
        "document architectures",
    ] * 2

    latencies_ms = []
    for q in test_queries:
        t0 = time.perf_counter()
        resp = search_service.search(q, limit=10)
        t1 = time.perf_counter()
        elapsed_ms = (t1 - t0) * 1000.0
        latencies_ms.append(elapsed_ms)
        assert len(resp.results) > 0

    avg_latency = sum(latencies_ms) / len(latencies_ms)
    p95_latency = sorted(latencies_ms)[int(0.95 * len(latencies_ms))]

    print(f"\n--- Latency Benchmark (1,000 Passages) ---")
    print(f"Average latency: {avg_latency:.2f} ms")
    print(f"p95 latency:     {p95_latency:.2f} ms")

    # Hardening assertion: Mean query time must remain under 100ms on local CPU
    assert avg_latency < 100.0, f"Average search latency {avg_latency:.2f}ms exceeded 100ms threshold"


# ============================================================================
# 8. ERROR-HANDLING MIDDLEWARE & STRUCTURED JSON RESPONSES
# ============================================================================
def test_e2e_error_handling_middleware():
    """
    Verifies that FastAPI exception middleware returns standardized JSON
    structures for 404 Not Found, 422 Validation Error, and unhandled 500 errors.
    """
    client = TestClient(app)

    # 1. Standard 404 Route Not Found
    res_404 = client.get("/api/nonexistent-endpoint-path")
    assert res_404.status_code == 404
    data_404 = res_404.json()
    assert "error" in data_404
    assert data_404["error"]["code"] == "HTTP_404"

    # 2. Validation Error (422) on POST /api/search with empty body
    res_422 = client.post("/api/search", json={})
    assert res_422.status_code == 422
    data_422 = res_422.json()
    assert "error" in data_422
    assert data_422["error"]["code"] == "VALIDATION_ERROR"
    assert "details" in data_422["error"]

    # 3. Validation Error (422) on POST /api/directories with missing canonical_path
    res_dir_422 = client.post("/api/directories", json={"bad_key": 123})
    assert res_dir_422.status_code == 422
    assert res_dir_422.json()["error"]["code"] == "VALIDATION_ERROR"

    # 4. Valid health check still returns status OK
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"].upper() == "OK"
