import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from app.core import config

logger = logging.getLogger("findit.db")

SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"

def get_db_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """
    Creates and returns a connection to the SQLite database with
    WAL mode, foreign keys, and dictionary-style row access enabled.
    """
    target_path = db_path or config.DATABASE_PATH
    # Ensure parent directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        str(target_path),
        check_same_thread=False,
        timeout=30.0,
    )
    conn.row_factory = sqlite3.Row

    # Performance and integrity pragmas
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")

    return conn


@contextmanager
def get_db(db_path: Path | None = None):
    """
    Context manager for safe database transactions.
    Automatically commits on success or rolls back on exceptions.
    """
    conn = get_db_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database transaction error: {e}")
        raise
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> None:
    """
    Initializes the database schema by executing schema.sql.
    Idempotent: safe to run repeatedly across application restarts.
    """
    target_path = db_path or config.DATABASE_PATH
    logger.info(f"Initializing SQLite database at: {target_path}")

    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(f"Schema definition file not found at: {SCHEMA_FILE}")

    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    with get_db(target_path) as conn:
        conn.executescript(schema_sql)

    logger.info("SQLite database schema initialized successfully.")
