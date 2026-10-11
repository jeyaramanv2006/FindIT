"""
FindIT Unit & Integration Tests:
Incremental Sync Scanner, Background Worker & Index Pruning.
"""

import os
import tempfile
import time
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import init_db, get_db
from app.indexing.faiss_index import FaissIndex
from app.indexing.bm25_index import BM25Index
from app.sync.scanner import ScannerService, ScanResult, ScannedFile, compute_sha256
from app.services.pruning_service import PruningService
from app.sync.worker import SyncWorker, get_sync_worker


@pytest.fixture
def mock_sync_env():
    """
    Creates an isolated temporary test environment with:
    - Dedicated SQLite database
    - Dedicated FAISS index
    - Dedicated BM25 index
    - Isolated directory on disk with sample documents
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_file = tmp_path / "findit_test.db"
        faiss_file = tmp_path / "index_test.faiss"
        bm25_file = tmp_path / "bm25_test.pkl"
        folder_path = tmp_path / "sample_workspace"
        folder_path.mkdir(parents=True, exist_ok=True)

        # Initialize SQLite database
        init_db(db_file)

        # Create isolated index instances
        faiss_idx = FaissIndex(index_path=faiss_file)
        bm25_idx = BM25Index(index_path=bm25_file)

        # Create isolated SyncWorker
        worker = SyncWorker(db_path=db_file, max_workers=2, faiss_idx=faiss_idx, bm25_idx=bm25_idx)

        yield {
            "tmp_path": tmp_path,
            "db_file": db_file,
            "faiss_file": faiss_file,
            "bm25_file": bm25_file,
            "folder_path": folder_path,
            "faiss_idx": faiss_idx,
            "bm25_idx": bm25_idx,
            "worker": worker,
        }


def test_scanner_change_detection_flow(mock_sync_env):
    """
    Tests ScannerService detecting new, modified, deleted, and unchanged files.
    """
    env = mock_sync_env
    folder = env["folder_path"]
    db_file = env["db_file"]

    # 1. Create initial files on disk
    file1 = folder / "doc1.txt"
    file1.write_text("Alpha document content for testing.", encoding="utf-8")
    file2 = folder / "doc2.md"
    file2.write_text("# Beta Spec\n\nDetailed specifications.", encoding="utf-8")
    ignored_file = folder / "temp.xyz"
    ignored_file.write_text("Ignore me", encoding="utf-8")  # Unsupported extension

    # Create ignored folder
    git_dir = folder / ".git"
    git_dir.mkdir()
    (git_dir / "config.txt").write_text("Git repo data", encoding="utf-8")

    # Initial scan: both supported files should be 'new'
    result1 = ScannerService.scan_directory(folder, "dir_test", db_path=db_file)
    assert len(result1.new_files) == 2
    assert len(result1.modified_files) == 0
    assert len(result1.deleted_files) == 0
    assert len(result1.unchanged_files) == 0
    assert result1.total_scanned == 2

    # Simulate inserting them into SQLite documents table
    with get_db(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO directories (directory_id, canonical_path, display_name, added_at, sync_status)
            VALUES ('dir_test', ?, 'Test Dir', datetime('now'), 'IDLE');
            """,
            (str(folder.resolve()).replace("\\", "/"),),
        )
        for nf in result1.new_files:
            cursor.execute(
                """
                INSERT INTO documents (
                    document_id, directory_id, canonical_path, filename,
                    extension, file_type, size_bytes, modified_time,
                    content_fingerprint, extraction_status
                ) VALUES (?, 'dir_test', ?, ?, ?, ?, ?, ?, ?, 'OK');
                """,
                (
                    "doc_" + nf.filename,
                    nf.canonical_path,
                    nf.filename,
                    nf.extension,
                    nf.file_type,
                    nf.size_bytes,
                    nf.modified_time,
                    nf.content_fingerprint,
                ),
            )

    # 2. Second scan: should detect 2 unchanged files
    result2 = ScannerService.scan_directory(folder, "dir_test", db_path=db_file)
    assert len(result2.new_files) == 0
    assert len(result2.modified_files) == 0
    assert len(result2.deleted_files) == 0
    assert len(result2.unchanged_files) == 2

    # 3. Modify doc1.txt and add doc3.py
    time.sleep(1.05)  # Ensure mtime changes
    file1.write_text("Alpha document content MODIFIED with new paragraphs.", encoding="utf-8")
    file3 = folder / "doc3.py"
    file3.write_text("def verify_token(): pass", encoding="utf-8")

    result3 = ScannerService.scan_directory(folder, "dir_test", db_path=db_file)
    assert len(result3.new_files) == 1
    assert result3.new_files[0].filename == "doc3.py"
    assert len(result3.modified_files) == 1
    assert result3.modified_files[0].filename == "doc1.txt"
    assert len(result3.unchanged_files) == 1
    assert result3.unchanged_files[0].filename == "doc2.md"
    assert len(result3.deleted_files) == 0

    # 4. Delete doc2.md from disk
    file2.unlink()
    result4 = ScannerService.scan_directory(folder, "dir_test", db_path=db_file)
    assert len(result4.deleted_files) == 1
    assert result4.deleted_files[0]["filename"] == "doc2.md"


def test_pruning_service_directory_and_documents(mock_sync_env):
    """
    Tests PruningService:
    - Removes vectors from FAISS
    - Removes postings from BM25
    - Cascades deletes in SQLite
    - Leaves disk files completely intact
    """
    env = mock_sync_env
    db_file = env["db_file"]
    faiss_idx = env["faiss_idx"]
    bm25_idx = env["bm25_idx"]
    folder = env["folder_path"]

    # Create physical file on disk
    sample_file = folder / "test_doc.txt"
    sample_file.write_text("Important user document on disk", encoding="utf-8")

    # Populate database with directory, document, passages
    with get_db(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO directories (directory_id, canonical_path, display_name, added_at, sync_status)
            VALUES ('dir_prune', ?, 'Prune Dir', datetime('now'), 'IDLE');
            """,
            (str(folder.resolve()).replace("\\", "/"),),
        )
        cursor.execute(
            """
            INSERT INTO documents (
                document_id, directory_id, canonical_path, filename,
                extension, file_type, size_bytes, modified_time,
                content_fingerprint, extraction_status
            ) VALUES ('doc_p1', 'dir_prune', ?, 'test_doc.txt', '.txt', 'txt', 100, 1000, 'hash1', 'OK');
            """,
            (str(sample_file.resolve()).replace("\\", "/"),),
        )
        cursor.execute(
            """
            INSERT INTO passages (chunk_id, document_id, chunk_ordinal, text, vector_id)
            VALUES ('chunk_p1_0', 'doc_p1', 0, 'First test passage text', 101);
            """
        )
        cursor.execute(
            """
            INSERT INTO passages (chunk_id, document_id, chunk_ordinal, text, vector_id)
            VALUES ('chunk_p1_1', 'doc_p1', 1, 'Second test passage text', 102);
            """
        )

    # Add to FAISS and BM25 indices
    vecs = np.random.randn(2, 384).astype(np.float32)
    faiss_idx.add_vectors(vecs, [101, 102], ["chunk_p1_0", "chunk_p1_1"])
    bm25_idx.add_documents(["chunk_p1_0", "chunk_p1_1"], ["First test passage text", "Second test passage text"])
    assert faiss_idx.total_vectors == 2
    assert bm25_idx.total_documents == 2

    # Prune directory
    prune_result = PruningService.prune_directory(
        "dir_prune",
        db_path=db_file,
        faiss_idx=faiss_idx,
        bm25_idx=bm25_idx,
    )
    assert prune_result["pruned_documents"] == 1
    assert prune_result["pruned_passages"] == 2
    assert prune_result["pruned_vectors"] == 2
    assert prune_result["files_untouched_on_disk"] is True

    # Verify indices are cleared
    assert faiss_idx.total_vectors == 0
    assert bm25_idx.total_documents == 0

    # Verify SQLite records are purged
    with get_db(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM directories WHERE directory_id = 'dir_prune';")
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT COUNT(*) FROM documents WHERE document_id = 'doc_p1';")
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT COUNT(*) FROM passages WHERE document_id = 'doc_p1';")
        assert cursor.fetchone()[0] == 0

    # Crucial check: physical file on disk MUST still exist!
    assert sample_file.exists()
    assert sample_file.read_text(encoding="utf-8") == "Important user document on disk"


def test_sync_worker_full_pipeline_execution(mock_sync_env):
    """
    Tests the complete background sync pipeline:
    Scanning -> Extracting -> Chunking -> Embedding -> FAISS & BM25 Indexing -> Status tracking.
    """
    env = mock_sync_env
    folder = env["folder_path"]
    db_file = env["db_file"]
    worker = env["worker"]

    # 1. Create realistic source documents
    p1 = folder / "architecture.md"
    p1.write_text("# FindIT Architecture\n\nThe dual retrieval engine uses FAISS and Rank-BM25.", encoding="utf-8")
    p2 = folder / "tokens.py"
    p2.write_text("def verify_bearer_jwt(token: str):\n    return True\n", encoding="utf-8")

    # Register directory in SQLite
    with get_db(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO directories (directory_id, canonical_path, display_name, added_at, sync_status)
            VALUES ('dir_worker_1', ?, 'Sample Workspace', datetime('now'), 'IDLE');
            """,
            (str(folder.resolve()).replace("\\", "/"),),
        )

    # Run sync synchronously via worker
    job_id = worker.start_sync("dir_worker_1", background=False)
    assert job_id.startswith("job_")

    # Inspect job status
    job_status = worker.get_job_status(job_id)
    assert job_status is not None
    assert job_status["status"] == "COMPLETED"
    assert job_status["files_discovered"] == 2
    assert job_status["files_processed"] == 2
    assert job_status["passages_created"] >= 2
    assert job_status["progress"] == 1.0

    # Verify SQLite database has documents and passages
    with get_db(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM documents WHERE directory_id = 'dir_worker_1';")
        assert cursor.fetchone()[0] == 2

        cursor.execute("SELECT COUNT(*) FROM passages;")
        passage_count = cursor.fetchone()[0]
        assert passage_count >= 2

        cursor.execute("SELECT sync_status FROM directories WHERE directory_id = 'dir_worker_1';")
        assert cursor.fetchone()[0] == "IDLE"

    # Verify BM25 rebuild utility
    rebuilt_count = PruningService.rebuild_bm25_from_sqlite(db_path=db_file)
    assert rebuilt_count == passage_count


def test_sync_worker_incremental_update_and_deletion(mock_sync_env):
    """
    Tests that a second sync run only processes modified files and prunes deleted files.
    """
    env = mock_sync_env
    folder = env["folder_path"]
    db_file = env["db_file"]
    worker = env["worker"]

    f1 = folder / "report.txt"
    f1.write_text("Initial report draft.", encoding="utf-8")
    f2 = folder / "notes.md"
    f2.write_text("# Meeting Notes\nDiscussion about project timeline.", encoding="utf-8")

    with get_db(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO directories (directory_id, canonical_path, display_name, added_at, sync_status)
            VALUES ('dir_inc', ?, 'Incremental Dir', datetime('now'), 'IDLE');
            """,
            (str(folder.resolve()).replace("\\", "/"),),
        )

    # Initial sync
    job1 = worker.start_sync("dir_inc", background=False)
    s1 = worker.get_job_status(job1)
    assert s1["status"] == "COMPLETED"
    assert s1["files_discovered"] == 2

    # Second sync without any changes
    job2 = worker.start_sync("dir_inc", background=False)
    s2 = worker.get_job_status(job2)
    assert s2["status"] == "COMPLETED"
    assert s2["files_discovered"] == 2
    assert s2["files_processed"] == 2  # Unchanged files counted as processed

    # Modify report.txt and delete notes.md
    time.sleep(1.05)
    f1.write_text("Updated report draft with final conclusions.", encoding="utf-8")
    f2.unlink()

    # Third sync
    job3 = worker.start_sync("dir_inc", background=False)
    s3 = worker.get_job_status(job3)
    assert s3["status"] == "COMPLETED"
    assert s3["files_discovered"] == 1  # notes.md is gone from disk, report.txt remains

    # Check SQLite: only report.txt remains
    with get_db(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT filename FROM documents WHERE directory_id = 'dir_inc';")
        docs = [r[0] for r in cursor.fetchall()]
        assert "report.txt" in docs
        assert "notes.md" not in docs


def test_sync_api_endpoints():
    """
    Tests REST API endpoints:
    - POST /api/sync
    - POST /api/sync/{directory_id}
    - GET /api/sync/status
    - GET /api/jobs/{job_id}
    """
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as temp_dir:
        dir_path = Path(temp_dir)
        (dir_path / "sample.txt").write_text("Sample file for API sync test.", encoding="utf-8")

        # 1. Register directory
        reg_resp = client.post("/api/directories", json={"canonical_path": str(dir_path)})
        assert reg_resp.status_code == 201
        dir_id = reg_resp.json()["directory"]["directory_id"]

        try:
            # 2. Trigger sync for directory
            sync_resp = client.post(f"/api/sync/{dir_id}")
            assert sync_resp.status_code == 202
            sync_data = sync_resp.json()
            assert "job_id" in sync_data
            assert sync_data["directory_id"] == dir_id
            job_id = sync_data["job_id"]

            # 3. Query job status by ID
            job_resp = client.get(f"/api/jobs/{job_id}")
            assert job_resp.status_code == 200
            assert job_resp.json()["job_id"] == job_id

            # 4. Query global sync status
            status_resp = client.get("/api/sync/status")
            assert status_resp.status_code == 200
            jobs = status_resp.json()["jobs"]
            assert any(j["job_id"] == job_id for j in jobs)

            # 5. Trigger sync all
            sync_all_resp = client.post("/api/sync")
            assert sync_all_resp.status_code == 202
            assert sync_all_resp.json()["status"] == "QUEUED"

            # 6. Test 404 on nonexistent directory or job
            bad_dir = client.post("/api/sync/dir_does_not_exist_999")
            assert bad_dir.status_code == 404

            bad_job = client.get("/api/jobs/job_does_not_exist_999")
            assert bad_job.status_code == 404

        finally:
            client.delete(f"/api/directories/{dir_id}")
