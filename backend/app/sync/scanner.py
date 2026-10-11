"""
FindIT Incremental File Scanner & Change Detection Engine

Crawls registered directories, respects boundaries and ignore patterns,
computes file attributes and SHA-256 fingerprints, and classifies files into:
- new: Present on disk, not recorded in database.
- modified: Present in both, but size, mtime, or content hash changed.
- deleted: Recorded in database for directory, but missing on disk.
- unchanged: Present in both with matching size, mtime, and content hash.
"""

import hashlib
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import sqlite3

from app.core import config
from app.db.database import get_db

logger = logging.getLogger("findit.sync.scanner")

# Default directory ignore list
IGNORED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".pytest_cache",
    ".agents",
    ".mypy_cache",
    ".ruff_cache",
}


def compute_sha256(file_path: Path) -> str:
    """Computes SHA-256 hash of a file efficiently in 64KB chunks."""
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logger.warning(f"Failed to compute SHA-256 for '{file_path}': {e}")
        return ""


@dataclass
class ScannedFile:
    """Represents a discovered candidate file on disk."""
    canonical_path: str
    relative_path: str
    filename: str
    extension: str
    file_type: str
    size_bytes: int
    modified_time: int
    content_fingerprint: str


@dataclass
class ScanResult:
    """Result of an incremental directory scan and change detection."""
    directory_id: str
    directory_path: str
    new_files: List[ScannedFile] = field(default_factory=list)
    modified_files: List[ScannedFile] = field(default_factory=list)
    deleted_files: List[Dict[str, Any]] = field(default_factory=list)
    unchanged_files: List[ScannedFile] = field(default_factory=list)
    total_scanned: int = 0

    @property
    def has_changes(self) -> bool:
        """Returns True if any files were added, modified, or deleted."""
        return bool(self.new_files or self.modified_files or self.deleted_files)

    @property
    def candidate_count(self) -> int:
        """Total candidate files currently on disk."""
        return len(self.new_files) + len(self.modified_files) + len(self.unchanged_files)


class ScannerService:
    """
    Crawls local folders, validates containment, checks timestamps/hashes,
    and categorizes file changes relative to SQLite document records.
    """

    @classmethod
    def scan_directory(
        cls,
        directory_path: Path | str,
        directory_id: str,
        db_path: Optional[Path] = None,
        force_rehash: bool = False,
    ) -> ScanResult:
        """
        Performs an incremental scan of the given directory.

        Args:
            directory_path: Path to the root directory on disk.
            directory_id: Unique identifier of the registered directory.
            db_path: Optional path to SQLite database (defaults to config.DATABASE_PATH).
            force_rehash: If True, computes SHA-256 for all files even if mtime & size match.

        Returns:
            ScanResult containing classified new, modified, deleted, and unchanged files.
        """
        dir_path = Path(directory_path).resolve()
        canonical_dir_str = str(dir_path).replace("\\", "/")

        if not dir_path.exists() or not dir_path.is_dir():
            raise ValueError(f"Directory path does not exist or is not a directory: '{dir_path}'")

        # 1. Fetch currently indexed documents for this directory from SQLite
        existing_docs: Dict[str, Dict[str, Any]] = {}
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT d.document_id, d.canonical_path, d.filename, d.size_bytes, d.modified_time, d.content_fingerprint,
                       d.extraction_status,
                       (SELECT COUNT(1) FROM passages p WHERE p.document_id = d.document_id) AS passage_count
                FROM documents d
                WHERE d.directory_id = ?;
                """,
                (directory_id,),
            )
            rows = cursor.fetchall()
            for r in rows:
                norm_path = r["canonical_path"].replace("\\", "/").lower()
                existing_docs[norm_path] = {
                    "document_id": r["document_id"],
                    "canonical_path": r["canonical_path"],
                    "filename": r["filename"],
                    "size_bytes": r["size_bytes"],
                    "modified_time": r["modified_time"],
                    "content_fingerprint": r["content_fingerprint"],
                    "extraction_status": r["extraction_status"],
                    "passage_count": r["passage_count"],
                }

        new_files: List[ScannedFile] = []
        modified_files: List[ScannedFile] = []
        unchanged_files: List[ScannedFile] = []
        visited_doc_paths: Set[str] = set()
        total_scanned = 0

        # 2. Walk directory on disk
        for root, dirs, files in os.walk(dir_path, followlinks=False):
            # Prune ignored and hidden directories in-place
            dirs[:] = [
                d for d in dirs
                if d not in IGNORED_DIR_NAMES and not d.startswith(".")
            ]

            for file_name in files:
                file_path = Path(root) / file_name

                # Symlink defense: ensure link does not escape registered directory boundary
                if file_path.is_symlink():
                    try:
                        resolved_link = file_path.resolve()
                        resolved_link.relative_to(dir_path)
                    except ValueError:
                        logger.warning(
                            f"Skipping symlink escaping directory boundary: {file_path} -> {resolved_link}"
                        )
                        continue

                # Ignore hidden files, system dotfiles, and Office lock files (~$*)
                if file_name.startswith("~$") or file_name.startswith("."):
                    continue

                ext = file_path.suffix.lower()
                if ext not in config.SUPPORTED_EXTENSIONS:
                    continue

                total_scanned += 1
                try:
                    stat = file_path.stat()
                    size_bytes = stat.st_size
                    mtime = int(stat.st_mtime)
                    file_type = config.get_file_type(ext)
                    canonical_file_path = str(file_path.resolve()).replace("\\", "/")
                    norm_path = canonical_file_path.lower()
                    visited_doc_paths.add(norm_path)

                    try:
                        rel_path = str(file_path.resolve().relative_to(dir_path)).replace("\\", "/")
                    except ValueError:
                        rel_path = file_name

                    if norm_path not in existing_docs:
                        # New document: calculate hash
                        sha256 = compute_sha256(file_path)
                        new_files.append(
                            ScannedFile(
                                canonical_path=canonical_file_path,
                                relative_path=rel_path,
                                filename=file_name,
                                extension=ext,
                                file_type=file_type,
                                size_bytes=size_bytes,
                                modified_time=mtime,
                                content_fingerprint=sha256,
                            )
                        )
                    else:
                        existing = existing_docs[norm_path]
                        is_already_indexed = existing.get("extraction_status") != "PENDING"

                        # Check fast path: size and mtime matching and already indexed
                        if (
                            not force_rehash
                            and is_already_indexed
                            and existing["size_bytes"] == size_bytes
                            and existing["modified_time"] == mtime
                        ):
                            unchanged_files.append(
                                ScannedFile(
                                    canonical_path=canonical_file_path,
                                    relative_path=rel_path,
                                    filename=file_name,
                                    extension=ext,
                                    file_type=file_type,
                                    size_bytes=size_bytes,
                                    modified_time=mtime,
                                    content_fingerprint=existing["content_fingerprint"] or "",
                                )
                            )
                        else:
                            # Size, mtime changed or pending extraction: compute SHA-256 fingerprint to verify content
                            sha256 = compute_sha256(file_path)
                            if (
                                is_already_indexed
                                and existing["content_fingerprint"]
                                and sha256 == existing["content_fingerprint"]
                                and existing["size_bytes"] == size_bytes
                            ):
                                # Content is identical (e.g. timestamp touched without file changes)
                                unchanged_files.append(
                                    ScannedFile(
                                        canonical_path=canonical_file_path,
                                        relative_path=rel_path,
                                        filename=file_name,
                                        extension=ext,
                                        file_type=file_type,
                                        size_bytes=size_bytes,
                                        modified_time=mtime,
                                        content_fingerprint=sha256,
                                    )
                                )
                            else:
                                # Content or size genuinely changed: mark for re-indexing
                                modified_files.append(
                                    ScannedFile(
                                        canonical_path=canonical_file_path,
                                        relative_path=rel_path,
                                        filename=file_name,
                                        extension=ext,
                                        file_type=file_type,
                                        size_bytes=size_bytes,
                                        modified_time=mtime,
                                        content_fingerprint=sha256,
                                    )
                                )
                except Exception as e:
                    logger.error(f"Error reading file '{file_path}': {e}")
                    continue

        # 3. Detect deleted documents: recorded in SQLite but not visited during disk walk
        deleted_files: List[Dict[str, Any]] = []
        for norm_path, doc_info in existing_docs.items():
            if norm_path not in visited_doc_paths:
                deleted_files.append({
                    "document_id": doc_info["document_id"],
                    "canonical_path": doc_info["canonical_path"],
                    "filename": doc_info["filename"],
                })

        return ScanResult(
            directory_id=directory_id,
            directory_path=canonical_dir_str,
            new_files=new_files,
            modified_files=modified_files,
            deleted_files=deleted_files,
            unchanged_files=unchanged_files,
            total_scanned=total_scanned,
        )
