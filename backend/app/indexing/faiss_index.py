"""
FindIT FAISS Dense Vector Index Layer
Wraps FAISS IndexFlatIP inside IndexIDMap2 for exact cosine similarity search,
vector insertion, ID-based deletion, and atomic persistence.
"""

import json
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import faiss

from app.core import config
from app.embeddings.embedder import EmbeddingEngine

logger = logging.getLogger("findit.indexing.faiss")

DEFAULT_DIMENSION = 384


@dataclass
class VectorSearchResult:
    vector_id: int
    score: float  # Cosine similarity in [-1.0, 1.0]
    chunk_id: Optional[str] = None


class FaissIndex:
    """
    Thread-safe FAISS vector index wrapper providing:
    - 384D IndexFlatIP wrapped in IndexIDMap2 for explicit 64-bit vector_ids
    - L2 normalization enforcement
    - ID-based vector deletion
    - Atomic persistence (index.faiss) and vector_id <-> chunk_id metadata mapping
    """

    def __init__(
        self,
        dimension: int = DEFAULT_DIMENSION,
        index_path: Optional[Path] = None,
    ):
        self.dimension = dimension
        self.index_path = index_path or config.FAISS_INDEX_PATH
        self.mapping_path = Path(str(self.index_path) + ".map.json")
        self._lock = threading.Lock()

        # In-memory mapping: vector_id (int) <-> chunk_id (str)
        self._vector_to_chunk: Dict[int, str] = {}
        self._chunk_to_vector: Dict[str, int] = {}

        # Initialize or load index
        self._init_index()

    def _init_index(self) -> None:
        """Initializes empty IndexIDMap2(IndexFlatIP) or loads from disk if exists."""
        if self.index_path.exists():
            try:
                self.load(self.index_path)
                return
            except Exception as e:
                logger.warning(
                    f"Failed to load existing FAISS index from {self.index_path}: {e}. Initializing fresh index."
                )

        sub_index = faiss.IndexFlatIP(self.dimension)
        self._index = faiss.IndexIDMap2(sub_index)
        self._vector_to_chunk.clear()
        self._chunk_to_vector.clear()

    @property
    def total_vectors(self) -> int:
        """Returns total number of indexed vectors."""
        with self._lock:
            return self._index.ntotal

    def add_vectors(
        self,
        vectors: np.ndarray,
        vector_ids: List[int] | np.ndarray,
        chunk_ids: Optional[List[str]] = None,
    ) -> None:
        """
        Inserts L2-normalized vectors with corresponding 64-bit integer IDs.

        Args:
            vectors: 2D array of shape (N, dimension)
            vector_ids: List or 1D array of length N integer IDs
            chunk_ids: Optional list of corresponding chunk_ids (str)
        """
        if vectors.size == 0:
            return

        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)

        if vectors.shape[1] != self.dimension:
            raise ValueError(
                f"Vector dimension mismatch: expected {self.dimension}, got {vectors.shape[1]}"
            )

        n_vectors = vectors.shape[0]
        ids_np = np.asarray(vector_ids, dtype=np.int64)
        if ids_np.shape[0] != n_vectors:
            raise ValueError(
                f"Mismatch between vector count ({n_vectors}) and vector_ids count ({ids_np.shape[0]})"
            )

        if chunk_ids is not None and len(chunk_ids) != n_vectors:
            raise ValueError(
                f"Mismatch between vector count ({n_vectors}) and chunk_ids count ({len(chunk_ids)})"
            )

        # Enforce strict L2 normalization for inner-product cosine similarity
        normalized_vectors = EmbeddingEngine.l2_normalize(vectors)

        with self._lock:
            # Check if any IDs already exist; if so, remove them first to update
            try:
                self._index.remove_ids(ids_np)
            except Exception:
                pass

            self._index.add_with_ids(normalized_vectors, ids_np)

            # Update ID mappings
            if chunk_ids:
                for v_id, c_id in zip(ids_np.tolist(), chunk_ids):
                    self._vector_to_chunk[v_id] = c_id
                    self._chunk_to_vector[c_id] = v_id

        logger.debug(f"Added {n_vectors} vectors to FAISS index. Total now: {self._index.ntotal}")

    def remove_vectors(self, vector_ids: List[int] | np.ndarray) -> int:
        """
        Removes vectors from index by their 64-bit integer vector_ids.

        Returns:
            Number of removed vectors.
        """
        if not vector_ids:
            return 0

        ids_np = np.asarray(vector_ids, dtype=np.int64)

        with self._lock:
            removed_count = self._index.remove_ids(ids_np)
            for v_id in ids_np.tolist():
                c_id = self._vector_to_chunk.pop(v_id, None)
                if c_id:
                    self._chunk_to_vector.pop(c_id, None)

        logger.debug(f"Removed {removed_count} vectors from FAISS index. Total now: {self._index.ntotal}")
        return removed_count

    def remove_chunks(self, chunk_ids: List[str]) -> int:
        """Removes vectors corresponding to chunk_ids."""
        with self._lock:
            vector_ids = [self._chunk_to_vector[c_id] for c_id in chunk_ids if c_id in self._chunk_to_vector]
        return self.remove_vectors(vector_ids)

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 50,
    ) -> List[VectorSearchResult]:
        """
        Executes exact inner-product (cosine similarity) search on indexed vectors.

        Args:
            query_vector: 1D array of shape (dimension,) or 2D of shape (1, dimension)
            top_k: Maximum candidate vectors to retrieve

        Returns:
            List of VectorSearchResult objects sorted descending by score.
        """
        if query_vector.size == 0 or self.total_vectors == 0 or top_k <= 0:
            return []

        q_vec = np.asarray(query_vector, dtype=np.float32)
        if q_vec.ndim == 1:
            q_vec = q_vec.reshape(1, -1)

        if q_vec.shape[1] != self.dimension:
            raise ValueError(
                f"Query vector dimension mismatch: expected {self.dimension}, got {q_vec.shape[1]}"
            )

        # Enforce L2 normalization on query vector
        norm_q = EmbeddingEngine.l2_normalize(q_vec)

        with self._lock:
            k = min(top_k, self._index.ntotal)
            if k == 0:
                return []

            scores_matrix, ids_matrix = self._index.search(norm_q, k)

            results: List[VectorSearchResult] = []
            for score, raw_id in zip(scores_matrix[0], ids_matrix[0]):
                v_id = int(raw_id)
                # Ignore invalid / sentinel FAISS IDs
                if v_id < 0:
                    continue

                # Cosine similarity clamp [-1.0, 1.0]
                clamped_score = float(max(-1.0, min(1.0, score)))
                chunk_id = self._vector_to_chunk.get(v_id)

                results.append(
                    VectorSearchResult(
                        vector_id=v_id,
                        score=clamped_score,
                        chunk_id=chunk_id,
                    )
                )

        return results

    def save(self, target_path: Optional[Path] = None) -> None:
        """
        Atomically persists the FAISS index binary and ID map JSON to disk.
        """
        target = target_path or self.index_path
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_index_path = Path(str(target) + ".tmp")
        tmp_map_path = Path(str(target) + ".map.json.tmp")
        final_map_path = Path(str(target) + ".map.json")

        with self._lock:
            # 1. Write FAISS index to tmp file
            faiss.write_index(self._index, str(tmp_index_path))

            # 2. Write metadata mapping to tmp file
            mapping_data = {
                "vector_to_chunk": {str(k): v for k, v in self._vector_to_chunk.items()},
            }
            with open(tmp_map_path, "w", encoding="utf-8") as f:
                json.dump(mapping_data, f, indent=2)

            # 3. Atomic replacement
            import time
            for attempt in range(5):
                try:
                    if tmp_index_path.exists():
                        os.replace(str(tmp_index_path), str(target))
                    if tmp_map_path.exists():
                        os.replace(str(tmp_map_path), str(final_map_path))
                    break
                except OSError as e:
                    if attempt == 4:
                        logger.warning(f"Failed to persist FAISS index after 5 retries: {e}")
                    else:
                        time.sleep(0.05 * (attempt + 1))

        logger.info(f"FAISS index and mapping saved atomically to {target} ({self.total_vectors} vectors).")

    def load(self, source_path: Optional[Path] = None) -> None:
        """
        Loads the FAISS index binary and ID map from disk.
        """
        source = source_path or self.index_path
        map_path = Path(str(source) + ".map.json")

        if not source.exists():
            raise FileNotFoundError(f"FAISS index file does not exist at {source}")

        with self._lock:
            loaded_index = faiss.read_index(str(source))
            # Wrap in IndexIDMap2 if not already
            if isinstance(loaded_index, faiss.IndexIDMap2):
                self._index = loaded_index
            elif isinstance(loaded_index, faiss.IndexIDMap):
                self._index = faiss.IndexIDMap2(loaded_index.index)
            else:
                self._index = faiss.IndexIDMap2(loaded_index)

            self._vector_to_chunk.clear()
            self._chunk_to_vector.clear()

            if map_path.exists():
                with open(map_path, "r", encoding="utf-8") as f:
                    map_data = json.load(f)
                    v_to_c = map_data.get("vector_to_chunk", {})
                    for k_str, c_id in v_to_c.items():
                        v_id = int(k_str)
                        self._vector_to_chunk[v_id] = c_id
                        self._chunk_to_vector[c_id] = v_id

        logger.info(f"Loaded FAISS index from {source} with {self._index.ntotal} vectors.")

    def clear(self) -> None:
        """Clears all vectors and mappings from memory."""
        with self._lock:
            sub = faiss.IndexFlatIP(self.dimension)
            self._index = faiss.IndexIDMap2(sub)
            self._vector_to_chunk.clear()
            self._chunk_to_vector.clear()


# Global singleton instance
_FAISS_INSTANCE: Optional[FaissIndex] = None
_FAISS_LOCK = threading.Lock()


def get_faiss_index() -> FaissIndex:
    """Returns singleton FaissIndex instance."""
    global _FAISS_INSTANCE
    if _FAISS_INSTANCE is None:
        with _FAISS_LOCK:
            if _FAISS_INSTANCE is None:
                _FAISS_INSTANCE = FaissIndex()
    return _FAISS_INSTANCE
