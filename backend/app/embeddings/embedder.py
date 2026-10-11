"""
FindIT Semantic Embedding Engine
Wraps sentence-transformers/all-MiniLM-L6-v2 to produce 384-dimensional
dense vectors with strict L2-normalization.
"""

import logging
import threading
from typing import Optional, List
import numpy as np

logger = logging.getLogger("findit.embeddings")

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_DIMENSION = 384


class EmbeddingEngine:
    """
    Manages local dense embedding generation using SentenceTransformer.
    Ensures all vectors are 384-dimensional float32 arrays with unit L2 norm.
    Supports CUDA hardware acceleration with graceful CPU fallback.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        device: Optional[str] = None,
        dimension: int = DEFAULT_DIMENSION,
        lazy_load: bool = True,
    ):
        from app.core import config
        self.model_name = model_name
        self.device = device or config.EMBEDDING_DEVICE
        self.dimension = dimension
        self._model = None
        self._lock = threading.Lock()

        if not lazy_load:
            self._ensure_loaded()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _ensure_loaded(self) -> None:
        """Loads the SentenceTransformer model if not already in memory."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    logger.info(f"Loading embedding model '{self.model_name}' on device '{self.device}'...")
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(self.model_name, device=self.device)
                    logger.info(f"Embedding model '{self.model_name}' loaded successfully.")

    @staticmethod
    def l2_normalize(vectors: np.ndarray) -> np.ndarray:
        """
        Applies strict L2-normalization to vectors along axis -1.
        Preserves float32 precision. Zero vectors remain zero.
        """
        if vectors.size == 0:
            return vectors.astype(np.float32)

        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.ndim == 1:
            norm = np.linalg.norm(vectors)
            if norm > 1e-12:
                return (vectors / norm).astype(np.float32)
            return vectors
        else:
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            # Avoid division by zero
            norms = np.where(norms > 1e-12, norms, 1.0)
            return (vectors / norms).astype(np.float32)

    def embed_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Generates 384D L2-normalized dense embeddings for a list of text strings.

        Args:
            texts: List of document/passage text strings.
            batch_size: Batch size for model inference.

        Returns:
            np.ndarray of shape (len(texts), 384) with dtype float32 and unit norm.
        """
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)

        self._ensure_loaded()

        # Generate embeddings with SentenceTransformer
        raw_embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,  # SentenceTransformers built-in L2 norm
        )

        # Enforce float32 and verify normalization
        embeddings = np.asarray(raw_embeddings, dtype=np.float32)
        if embeddings.shape[1] != self.dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.dimension}, got {embeddings.shape[1]}"
            )

        return self.l2_normalize(embeddings)

    def embed_passages(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Alias for embed_texts."""
        return self.embed_texts(texts, batch_size=batch_size)

    def embed_query(self, query: str) -> np.ndarray:
        """
        Generates a 384D L2-normalized dense embedding for a single search query string.

        Args:
            query: The user query string.

        Returns:
            1D np.ndarray of shape (384,) with dtype float32 and unit norm.
        """
        if not query or not query.strip():
            # Return zero vector if query is empty
            return np.zeros((self.dimension,), dtype=np.float32)

        embeddings = self.embed_texts([query.strip()], batch_size=1)
        return embeddings[0]


# Singleton instance container
_EMBEDDER_INSTANCE: Optional[EmbeddingEngine] = None
_EMBEDDER_LOCK = threading.Lock()


def get_embedder() -> EmbeddingEngine:
    """
    Returns the shared singleton EmbeddingEngine instance.
    Lazy loads the model on demand.
    """
    global _EMBEDDER_INSTANCE
    if _EMBEDDER_INSTANCE is None:
        with _EMBEDDER_LOCK:
            if _EMBEDDER_INSTANCE is None:
                _EMBEDDER_INSTANCE = EmbeddingEngine()
    return _EMBEDDER_INSTANCE
