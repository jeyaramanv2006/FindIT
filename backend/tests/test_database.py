import tempfile
from pathlib import Path
from app.db.database import get_db, init_db

def test_database_initialization_and_wal():
    with tempfile.TemporaryDirectory() as temp_dir:
        test_db_path = Path(temp_dir) / "test_findit.db"
        init_db(test_db_path)

        with get_db(test_db_path) as conn:
            # Check WAL journal mode
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0]
            assert journal_mode.lower() == "wal"

            # Check foreign keys pragma
            cursor.execute("PRAGMA foreign_keys;")
            fk = cursor.fetchone()[0]
            assert fk == 1

            # Check all required tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row[0] for row in cursor.fetchall()}
            assert "directories" in tables
            assert "documents" in tables
            assert "passages" in tables
            assert "index_jobs" in tables


def test_cascade_deletion():
    with tempfile.TemporaryDirectory() as temp_dir:
        test_db_path = Path(temp_dir) / "test_findit.db"
        init_db(test_db_path)

        with get_db(test_db_path) as conn:
            cursor = conn.cursor()
            # Insert directory
            cursor.execute(
                """
                INSERT INTO directories (directory_id, canonical_path, display_name, added_at, sync_status)
                VALUES (?, ?, ?, datetime('now'), 'IDLE')
                """,
                ("dir_1", "/test/dir", "Test Dir")
            )
            # Insert document
            cursor.execute(
                """
                INSERT INTO documents (
                    document_id, directory_id, canonical_path, filename, extension,
                    file_type, size_bytes, modified_time, extraction_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("doc_1", "dir_1", "/test/dir/test.txt", "test.txt", ".txt", "txt", 100, 1000, "OK")
            )
            # Insert passage
            cursor.execute(
                """
                INSERT INTO passages (
                    chunk_id, document_id, chunk_ordinal, text, vector_id
                ) VALUES (?, ?, ?, ?, ?)
                """,
                ("chunk_1", "doc_1", 0, "Test passage", 1)
            )

        # Verify insertion
        with get_db(test_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM passages;")
            assert cursor.fetchone()[0] == 1

            # Delete directory and verify cascade
            cursor.execute("DELETE FROM directories WHERE directory_id = ?", ("dir_1",))

        # Check cascading deletion
        with get_db(test_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM documents;")
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT COUNT(*) FROM passages;")
            assert cursor.fetchone()[0] == 0
