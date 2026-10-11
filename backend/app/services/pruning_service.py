"""
FindIT Index Pruning & Directory Removal Service

Provides atomic removal of vectors from FAISS, postings from BM25,
and cascading deletion of records in SQLite, guaranteeing that original
source files on disk remain untouched.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import sqlite3

from app.core import config
from app.db.database import get_db
from app.indexing.faiss_index import FaissIndex, get_faiss_index
from app.indexing.bm25_index import BM25Index, get_bm25_index

logger = logging.getLogger("findit.services.pruning")


class PruningService:
    """
    Manages search index pruning and database lifecycle cleanup:
    - Cascades deletions from FAISS and BM25 upon file deletion or update.
    - Purges directory index metadata while preserving source documents on disk.
    """

    @classmethod
    def prune_directory(
        cls,
        directory_id: str,
        db_path: Optional[Path] = None,
        faiss_idx: Optional[FaissIndex] = None,
        bm25_idx: Optional[BM25Index] = None,
    ) -> Dict[str, Any]:
        """
        Unlinks a directory from FindIT:
        1. Queries all associated document and passage IDs.
        2. Removes vectors from FAISS and saves index.
        3. Removes postings from BM25 and saves index.
        4. Cascades deletion in SQLite (directories -> documents -> passages).
        5. NEVER deletes source files on disk.

        Args:
            directory_id: Directory ID to prune and unlink.
            db_path: Optional SQLite database path.
            faiss_idx: Optional FaissIndex instance.
            bm25_idx: Optional BM25Index instance.

        Returns:
            Dict containing counts of pruned documents, passages, and vectors.
        """
        faiss_index = faiss_idx or get_faiss_index()
        bm25_index = bm25_idx or get_bm25_index()

        with get_db(db_path) as conn:
            cursor = conn.cursor()

            # Verify directory exists
            cursor.execute(
                "SELECT canonical_path, display_name FROM directories WHERE directory_id = ?;",
                (directory_id,),
            )
            dir_row = cursor.fetchone()
            if not dir_row:
                raise ValueError(f"Directory with ID '{directory_id}' not found.")

            canonical_path = dir_row["canonical_path"]

            # 1. Collect all documents in directory
            cursor.execute(
                "SELECT document_id FROM documents WHERE directory_id = ?;",
                (directory_id,),
            )
            doc_rows = cursor.fetchall()
            doc_ids = [r["document_id"] for r in doc_rows]

            # 2. Collect all passages for these documents
            chunk_ids: List[str] = []
            vector_ids: List[int] = []

            if doc_ids:
                placeholders = ",".join("?" for _ in doc_ids)
                cursor.execute(
                    f"""
                    SELECT chunk_id, vector_id
                    FROM passages
                    WHERE document_id IN ({placeholders});
                    """,
                    doc_ids,
                )
                passage_rows = cursor.fetchall()
                for r in passage_rows:
                    chunk_ids.append(r["chunk_id"])
                    if r["vector_id"] is not None:
                        vector_ids.append(int(r["vector_id"]))

            # 3. Prune vectors from FAISS
            pruned_vectors = 0
            if vector_ids:
                pruned_vectors = faiss_index.remove_vectors(vector_ids)
                try:
                    faiss_index.save()
                except Exception as e:
                    logger.warning(f"Error persisting FAISS index after pruning: {e}")

            # 4. Prune postings from BM25
            pruned_bm25 = 0
            if chunk_ids:
                pruned_bm25 = bm25_index.remove_documents(chunk_ids)
                try:
                    bm25_index.save()
                except Exception as e:
                    logger.warning(f"Error persisting BM25 index after pruning: {e}")

            # 5. Delete directory record from SQLite (cascades via foreign keys)
            cursor.execute("DELETE FROM directories WHERE directory_id = ?;", (directory_id,))

        logger.info(
            f"Successfully pruned directory '{canonical_path}' (ID: {directory_id}): "
            f"{len(doc_ids)} docs, {len(chunk_ids)} passages, {pruned_vectors} vectors."
        )

        return {
            "directory_id": directory_id,
            "canonical_path": canonical_path,
            "pruned_documents": len(doc_ids),
            "pruned_passages": len(chunk_ids),
            "pruned_vectors": pruned_vectors,
            "pruned_bm25": pruned_bm25,
            "files_untouched_on_disk": True,
        }

    @classmethod
    def prune_documents(
        cls,
        document_ids: List[str],
        db_path: Optional[Path] = None,
        faiss_idx: Optional[FaissIndex] = None,
        bm25_idx: Optional[BM25Index] = None,
        persist_indices: bool = True,
    ) -> Dict[str, Any]:
        """
        Prunes a specific batch of documents (e.g. deleted or modified during incremental sync):
        1. Gathers all passage chunks and vector IDs for the document IDs.
        2. Removes them from FAISS and BM25.
        3. Deletes document rows from SQLite (cascading to passages).

        Args:
            document_ids: List of document IDs to prune.
            db_path: Optional SQLite database path.
            faiss_idx: Optional FaissIndex instance.
            bm25_idx: Optional BM25Index instance.
            persist_indices: Whether to save index files immediately.

        Returns:
            Dict containing counts of pruned documents, passages, and vectors.
        """
        if not document_ids:
            return {
                "pruned_documents": 0,
                "pruned_passages": 0,
                "pruned_vectors": 0,
                "pruned_bm25": 0,
            }

        faiss_index = faiss_idx or get_faiss_index()
        bm25_index = bm25_idx or get_bm25_index()

        chunk_ids: List[str] = []
        vector_ids: List[int] = []

        with get_db(db_path) as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in document_ids)

            # 1. Collect passages
            cursor.execute(
                f"""
                SELECT chunk_id, vector_id
                FROM passages
                WHERE document_id IN ({placeholders});
                """,
                document_ids,
            )
            rows = cursor.fetchall()
            for r in rows:
                chunk_ids.append(r["chunk_id"])
                if r["vector_id"] is not None:
                    vector_ids.append(int(r["vector_id"]))

            # 2. Prune FAISS
            pruned_vectors = 0
            if vector_ids:
                pruned_vectors = faiss_index.remove_vectors(vector_ids)

            # 3. Prune BM25
            pruned_bm25 = 0
            if chunk_ids:
                pruned_bm25 = bm25_index.remove_documents(chunk_ids)

            # 4. Delete documents from SQLite (cascades to passages)
            cursor.execute(
                f"DELETE FROM documents WHERE document_id IN ({placeholders});",
                document_ids,
            )

            if persist_indices:
                if pruned_vectors > 0:
                    try:
                        faiss_index.save()
                    except Exception as e:
                        logger.warning(f"Error persisting FAISS index: {e}")
                if pruned_bm25 > 0:
                    try:
                        bm25_index.save()
                    except Exception as e:
                        logger.warning(f"Error persisting BM25 index: {e}")

        return {
            "pruned_documents": len(document_ids),
            "pruned_passages": len(chunk_ids),
            "pruned_vectors": pruned_vectors,
            "pruned_bm25": pruned_bm25,
        }

    @classmethod
    def rebuild_bm25_from_sqlite(
        cls,
        db_path: Optional[Path] = None,
        bm25_idx: Optional[BM25Index] = None,
    ) -> int:
        """
        Reconstructs the BM25 index completely from stored SQLite passages.
        Mandated by docs/TRD.md Section 6.2 for recovery and verification.
        """
        bm25_index = bm25_idx or get_bm25_index()

        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT chunk_id, text FROM passages ORDER BY chunk_id;")
            rows = cursor.fetchall()

            chunk_ids = [r["chunk_id"] for r in rows]
            texts = [r["text"] for r in rows]

            bm25_index.clear()
            if chunk_ids:
                bm25_index.add_documents(chunk_ids, texts)
            bm25_index.save()

        logger.info(f"Rebuilt BM25 index from SQLite with {len(chunk_ids)} passages.")
        return len(chunk_ids)
