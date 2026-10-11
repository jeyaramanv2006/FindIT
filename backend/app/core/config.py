import os
from pathlib import Path

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database & Index file paths
DATABASE_PATH = DATA_DIR / "findit.db"
FAISS_INDEX_PATH = DATA_DIR / "index.faiss"
BM25_INDEX_PATH = DATA_DIR / "bm25.pkl"

# Server configuration
HOST = os.getenv("FINDIT_HOST", "127.0.0.1")
PORT = int(os.getenv("FINDIT_PORT", "8000"))

# CORS settings (allowed local frontend dev servers)
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Supported file extensions for document indexing
SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".txt",
    ".md",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".yaml",
    ".yml",
    ".html",
    ".css",
}
