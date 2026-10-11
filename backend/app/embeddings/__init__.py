"""
FindIT Semantic Embeddings Module
Provides local 384D unit-normalized dense embeddings via sentence-transformers/all-MiniLM-L6-v2.
"""

from app.embeddings.embedder import EmbeddingEngine, get_embedder

__all__ = ["EmbeddingEngine", "get_embedder"]
