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

# Maximum single file size allowed for text extraction and indexing (default 50MB)
MAX_FILE_SIZE_BYTES = int(os.getenv("FINDIT_MAX_FILE_SIZE_BYTES", 50 * 1024 * 1024))

# Supported file extensions for document indexing
SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".doc",
    ".pptx",
    ".ppt",
    ".txt",
    ".md",
    ".markdown",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".html",
    ".css",
}

# Mapping extensions to canonical file types (pdf, pptx, docx, md, txt, code, config)
EXTENSION_TO_FILE_TYPE = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "docx",
    ".pptx": "pptx",
    ".ppt": "pptx",
    ".txt": "txt",
    ".md": "md",
    ".markdown": "md",
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".tsx": "code",
    ".jsx": "code",
    ".html": "code",
    ".css": "code",
    ".json": "config",
    ".yaml": "config",
    ".yml": "config",
    ".toml": "config",
}

def get_file_type(extension: str) -> str:
    """Returns canonical file_type category for a file extension."""
    return EXTENSION_TO_FILE_TYPE.get(extension.lower(), "txt")
