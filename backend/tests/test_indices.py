"""
FindIT Unit Tests:
Semantic Embeddings, FAISS Vector Index & BM25 Lexical Engine.
"""

import os
import tempfile
from pathlib import Path
import numpy as np
import pytest

from app.embeddings.embedder import EmbeddingEngine, DEFAULT_DIMENSION
from app.indexing.faiss_index import FaissIndex, VectorSearchResult
from app.indexing.bm25_index import BM25Index, tokenize_code_and_prose, LexicalSearchResult


class TestEmbeddingEngine:
    """Tests for Semantic Embedding Engine (Phase 6)."""

    def test_l2_normalize_unit_norm(self):
        """Validates that l2_normalize produces vectors with norm == 1.0."""
        random_vectors = np.random.randn(10, DEFAULT_DIMENSION).astype(np.float32)
        normalized = EmbeddingEngine.l2_normalize(random_vectors)

        assert normalized.shape == (10, DEFAULT_DIMENSION)
        norms = np.linalg.norm(normalized, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-5)

    def test_l2_normalize_zero_vector(self):
        """Zero vectors should remain zero without division-by-zero error."""
        zero_vec = np.zeros((DEFAULT_DIMENSION,), dtype=np.float32)
        norm_vec = EmbeddingEngine.l2_normalize(zero_vec)
        assert np.all(norm_vec == 0.0)

    def test_embed_texts_and_query(self):
        """Verifies SentenceTransformer inference produces 384D unit-norm vectors."""
        engine = EmbeddingEngine(device="cpu")
        texts = [
            "FindIT is an offline-first desktop search engine.",
            "Dense vector embeddings are computed locally using MiniLM.",
        ]

        embeddings = engine.embed_texts(texts, batch_size=2)
        assert embeddings.shape == (2, DEFAULT_DIMENSION)
        assert embeddings.dtype == np.float32

        # Check unit norm
        norms = np.linalg.norm(embeddings, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-5)

        # Single query embedding
        query_vec = engine.embed_query("desktop search engine")
        assert query_vec.shape == (DEFAULT_DIMENSION,)
        assert query_vec.dtype == np.float32
        assert abs(np.linalg.norm(query_vec) - 1.0) < 1e-5

    def test_embed_empty_input(self):
        """Empty texts or empty query should return appropriate empty/zero arrays."""
        engine = EmbeddingEngine(device="cpu")
        assert engine.embed_texts([]).shape == (0, DEFAULT_DIMENSION)

        empty_query_vec = engine.embed_query("")
        assert empty_query_vec.shape == (DEFAULT_DIMENSION,)
        assert np.all(empty_query_vec == 0.0)


class TestFaissIndex:
    """Tests for FAISS Dense Vector Index Layer (Phase 7)."""

    @pytest.fixture
    def temp_index_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield Path(tmp_dir)

    def test_add_and_search_exact_match(self, temp_index_dir):
        """Adding vectors and querying exact vector yields cosine similarity ≈ 1.0."""
        index_path = temp_index_dir / "test.faiss"
        index = FaissIndex(dimension=DEFAULT_DIMENSION, index_path=index_path)

        # Create 5 test vectors
        np.random.seed(42)
        raw_vecs = np.random.randn(5, DEFAULT_DIMENSION).astype(np.float32)
        vec_ids = [101, 102, 103, 104, 105]
        chunk_ids = [f"chunk_{i}" for i in vec_ids]

        index.add_vectors(raw_vecs, vec_ids, chunk_ids)
        assert index.total_vectors == 5

        # Query using the exact 2nd vector
        query_vec = raw_vecs[1]
        results = index.search(query_vec, top_k=3)

        assert len(results) == 3
        # Top result must be vector 102
        assert results[0].vector_id == 102
        assert results[0].chunk_id == "chunk_102"
        assert abs(results[0].score - 1.0) < 1e-4

    def test_100_sample_vectors_checkpoint(self, temp_index_dir):
        """
        Verification Checkpoint:
        Verify FAISS query on 100 sample vectors returns cosine similarities in [-1.0, 1.0].
        """
        index_path = temp_index_dir / "checkpoint.faiss"
        index = FaissIndex(dimension=DEFAULT_DIMENSION, index_path=index_path)

        np.random.seed(123)
        n = 100
        vectors = np.random.randn(n, DEFAULT_DIMENSION).astype(np.float32)
        ids = list(range(1, n + 1))
        chunks = [f"doc_chunk_{i}" for i in ids]

        index.add_vectors(vectors, ids, chunks)
        assert index.total_vectors == 100

        # Query with arbitrary vector
        q = np.random.randn(DEFAULT_DIMENSION).astype(np.float32)
        results = index.search(q, top_k=20)

        assert len(results) == 20
        for res in results:
            assert -1.0 <= res.score <= 1.0
            assert res.vector_id in ids
            assert res.chunk_id == f"doc_chunk_{res.vector_id}"

    def test_remove_vectors_and_chunks(self, temp_index_dir):
        """Removing vectors by vector_id or chunk_id updates total count and search."""
        index_path = temp_index_dir / "removal.faiss"
        index = FaissIndex(dimension=DEFAULT_DIMENSION, index_path=index_path)

        vecs = np.random.randn(3, DEFAULT_DIMENSION).astype(np.float32)
        index.add_vectors(vecs, [1, 2, 3], ["c1", "c2", "c3"])
        assert index.total_vectors == 3

        # Remove vector 2
        removed = index.remove_vectors([2])
        assert removed == 1
        assert index.total_vectors == 2

        # Search should not contain vector 2
        results = index.search(vecs[1], top_k=3)
        result_ids = [r.vector_id for r in results]
        assert 2 not in result_ids

        # Remove chunk "c1"
        index.remove_chunks(["c1"])
        assert index.total_vectors == 1

    def test_save_and_load_persistence(self, temp_index_dir):
        """Index and mapping must serialize and deserialize with full fidelity."""
        index_path = temp_index_dir / "persisted.faiss"
        index = FaissIndex(dimension=DEFAULT_DIMENSION, index_path=index_path)

        vecs = np.random.randn(4, DEFAULT_DIMENSION).astype(np.float32)
        index.add_vectors(vecs, [10, 20, 30, 40], ["docA", "docB", "docC", "docD"])
        index.save()

        assert index_path.exists()
        assert Path(str(index_path) + ".map.json").exists()

        # Load into new index instance
        loaded_index = FaissIndex(dimension=DEFAULT_DIMENSION, index_path=index_path)
        assert loaded_index.total_vectors == 4

        results = loaded_index.search(vecs[0], top_k=1)
        assert len(results) == 1
        assert results[0].vector_id == 10
        assert results[0].chunk_id == "docA"


class TestBM25Index:
    """Tests for BM25 Lexical Search Index Layer (Phase 8)."""

    @pytest.fixture
    def temp_bm25_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield Path(tmp_dir)

    def test_tokenizer_identifiers_and_prose(self):
        """Validates custom tokenizer handles code identifiers, paths, and natural prose."""
        text = "def auth_middleware(req: Request) -> getUserProfile(): return app.core.config.DB_PATH"
        tokens = tokenize_code_and_prose(text)

        # Must contain exact compound identifiers
        assert "auth_middleware" in tokens
        assert "getuserprofile" in tokens
        assert "db_path" in tokens

        # Must contain split components
        assert "auth" in tokens
        assert "middleware" in tokens
        assert "get" in tokens
        assert "user" in tokens
        assert "profile" in tokens
        assert "config" in tokens

    def test_bm25_auth_middleware_checkpoint(self, temp_bm25_dir):
        """
        Verification Checkpoint:
        Verify BM25 query for `auth_middleware` ranks exact matches first over general prose.
        """
        index_path = temp_bm25_dir / "bm25_test.pkl"
        index = BM25Index(index_path=index_path)

        chunk_ids = ["chunk_prose", "chunk_exact", "chunk_unrelated"]
        texts = [
            "This document outlines generic authentication and authorization middleware principles.",
            "def auth_middleware(request): return verify_jwt_token(request.headers['Authorization'])",
            "Database connection pool configuration settings for SQLite WAL mode.",
        ]

        index.add_documents(chunk_ids, texts)
        assert index.total_documents == 3

        results = index.search("auth_middleware", top_k=3)

        assert len(results) >= 2
        # Exact match chunk must rank #1
        assert results[0].chunk_id == "chunk_exact"
        # Score for exact match must exceed prose score
        assert results[0].score > results[1].score

    def test_bm25_rare_identifier(self, temp_bm25_dir):
        """Querying rare technical identifier ranks matching chunk highest."""
        index_path = temp_bm25_dir / "bm25_rare.pkl"
        index = BM25Index(index_path=index_path)

        chunk_ids = ["doc1", "doc2"]
        texts = [
            "Handling standard cryptographic tokens and certificates.",
            "Calling function verify_jwt_token_signature to validate public RSA key.",
        ]

        index.add_documents(chunk_ids, texts)
        results = index.search("verify_jwt_token_signature", top_k=2)

        assert len(results) == 1
        assert results[0].chunk_id == "doc2"

    def test_bm25_remove_documents(self, temp_bm25_dir):
        """Removing documents updates index and removes them from results."""
        index_path = temp_bm25_dir / "bm25_remove.pkl"
        index = BM25Index(index_path=index_path)

        index.add_documents(["c1", "c2"], ["alpha beta", "gamma delta"])
        assert index.total_documents == 2

        results = index.search("alpha", top_k=2)
        assert len(results) == 1
        assert results[0].chunk_id == "c1"

        index.remove_documents(["c1"])
        assert index.total_documents == 1

        results_after = index.search("alpha", top_k=2)
        assert len(results_after) == 0

    def test_bm25_save_and_load(self, temp_bm25_dir):
        """BM25 index serializes and deserializes accurately."""
        index_path = temp_bm25_dir / "persisted_bm25.pkl"
        index = BM25Index(index_path=index_path)

        index.add_documents(["id1", "id2"], ["SentenceTransformers all-MiniLM-L6-v2", "FAISS IndexFlatIP"])
        index.save()

        assert index_path.exists()

        loaded_index = BM25Index(index_path=index_path)
        assert loaded_index.total_documents == 2

        results = loaded_index.search("all-MiniLM-L6-v2", top_k=1)
        assert len(results) == 1
        assert results[0].chunk_id == "id1"
