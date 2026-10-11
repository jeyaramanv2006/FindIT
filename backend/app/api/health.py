from fastapi import APIRouter
from app.db.database import get_db

router = APIRouter(tags=["Health"])

@router.get("/health")
def health_check():
    """
    Returns server operational status, version, and index statistics.
    Follows the docs/API.md health check specification.
    """
    registered_directories = 0
    total_passages_indexed = 0

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM directories;")
            row = cursor.fetchone()
            if row:
                registered_directories = row[0]

            cursor.execute("SELECT COUNT(*) FROM passages;")
            row = cursor.fetchone()
            if row:
                total_passages_indexed = row[0]
    except Exception:
        # Fall back gracefully if database is currently being initialized
        pass

    return {
        "status": "OK",
        "version": "0.1.0",
        "model_loaded": False,
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "registered_directories": registered_directories,
        "total_passages_indexed": total_passages_indexed,
    }
