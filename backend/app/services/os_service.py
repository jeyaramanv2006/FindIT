"""
FindIT Native OS File Manager & System Actions Service
Safely executes OS-level file revelation (e.g. explorer.exe /select)
with strict path traversal and directory boundary validation.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, List
from app.db.database import get_db

logger = logging.getLogger("findit.os_service")


class SecurityBoundaryError(PermissionError):
    """Raised when an operation attempts to target files outside registered directory roots."""
    pass


class OSService:
    """
    Executes operating-system level navigation commands safely:
    - Path canonicalization & existence check
    - Approved directory boundary confinement enforcement
    - Native OS file manager launcher (explorer.exe /select on Windows)
    - Default application launcher (os.startfile on Windows)
    """

    @staticmethod
    def validate_path_confinement(target_path: Path, db_path: Optional[Path] = None) -> Path:
        """
        Resolves the target path and verifies that it exists and is confined
        within at least one registered directory root in SQLite.

        Raises:
            FileNotFoundError: If the target does not exist.
            SecurityBoundaryError: If the target is outside all registered directories.
        """
        target_path_obj = Path(target_path)
        canonical_target = target_path_obj.expanduser().resolve()

        if not canonical_target.exists():
            raise FileNotFoundError(f"Target path does not exist: '{canonical_target}'")

        # Check confinement against approved directories in SQLite
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT canonical_path FROM directories;")
            registered_rows = cursor.fetchall()

        if not registered_rows:
            # If no directories registered yet, disallow opening for security
            raise SecurityBoundaryError(
                f"Access denied: No registered directory roots found to validate '{canonical_target}'."
            )

        is_confined = False
        for row in registered_rows:
            root = Path(row["canonical_path"]).resolve()
            try:
                canonical_target.relative_to(root)
                is_confined = True
                break
            except ValueError:
                continue

        if not is_confined:
            raise SecurityBoundaryError(
                f"Access denied: Path '{canonical_target}' resides outside all registered directory roots."
            )

        return canonical_target

    @classmethod
    def get_document_path(cls, document_id: str, db_path: Optional[Path] = None) -> Path:
        """Retrieves and verifies the canonical path of a document by its document_id."""
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT canonical_path FROM documents WHERE document_id = ?;", (document_id,))
            row = cursor.fetchone()

        if not row:
            raise FileNotFoundError(f"Document with ID '{document_id}' not found in database.")

        target = Path(row["canonical_path"])
        return cls.validate_path_confinement(target, db_path=db_path)

    @classmethod
    def open_containing_folder(
        cls,
        path: Path | str,
        validate_confinement: bool = True,
        db_path: Optional[Path] = None,
        dry_run: bool = False,
    ) -> str:
        """
        Reveals the target file in the native file explorer and selects/highlights it.

        Args:
            path: Target file path or document path.
            validate_confinement: Whether to enforce directory boundary checks.
            db_path: Optional SQLite database path.
            dry_run: If True, skips actual subprocess execution (useful for testing).

        Returns:
            The normalized canonical path that was revealed.
        """
        target = Path(path).expanduser().resolve()
        if validate_confinement:
            target = cls.validate_path_confinement(target, db_path=db_path)
        elif not target.exists():
            raise FileNotFoundError(f"Target path does not exist: '{target}'")

        normalized = str(target)

        if dry_run:
            logger.info(f"[Dry Run] Open containing folder for: {normalized}")
            return normalized

        try:
            if sys.platform == "win32":
                # In Windows Explorer, /select,"path" requires /select, to be unquoted.
                # Passing a single command string avoids Python enclosing the entire argument in quotes.
                win_path = os.path.normpath(normalized)
                if target.is_file():
                    cmd = f'explorer.exe /select,"{win_path}"'
                else:
                    cmd = f'explorer.exe "{win_path}"'
                logger.info(f"Launching Windows Explorer: {cmd}")
                subprocess.Popen(cmd)
            elif sys.platform == "darwin":
                # macOS open -R "path"
                logger.info(f"Launching macOS Finder: open -R {normalized}")
                subprocess.Popen(["open", "-R", normalized])
            else:
                # Linux xdg-open containing folder
                folder = str(target.parent)
                logger.info(f"Launching Linux file manager: xdg-open {folder}")
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            logger.error(f"Failed to launch OS file manager for '{normalized}': {e}")
            raise RuntimeError(f"Failed to open native file explorer: {e}")

        return normalized

    @classmethod
    def open_document(
        cls,
        document_id: str,
        db_path: Optional[Path] = None,
        dry_run: bool = False,
    ) -> str:
        """
        Opens the document in its default associated system application.
        """
        target = cls.get_document_path(document_id, db_path=db_path)
        normalized = str(target)

        if dry_run:
            logger.info(f"[Dry Run] Open document with default app: {normalized}")
            return normalized

        try:
            if sys.platform == "win32":
                os.startfile(normalized)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", normalized])
            else:
                subprocess.Popen(["xdg-open", normalized])
        except Exception as e:
            logger.error(f"Failed to open document '{normalized}': {e}")
            raise RuntimeError(f"Failed to launch document: {e}")

        return normalized
