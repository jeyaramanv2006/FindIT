"""
FindIT Lexical Search Index Layer — BM25
Implements Rank-BM25 with an identifier-aware custom tokenizer that splits
code identifiers (camelCase, snake_case, paths, dotted names) while preserving
exact original tokens, and atomic persistence.
Synchronized with docs/TRD.md Section 5 and notes/EXECUTION_PLAN.md Batch 3.
"""

import logging
import math
import os
import pickle
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from rank_bm25 import BM25Okapi

from app.core import config

logger = logging.getLogger("findit.indexing.bm25")


@dataclass
class LexicalSearchResult:
    chunk_id: str
    score: float  # BM25 relevance score


class RobustBM25Okapi(BM25Okapi):
    """
    Rank-BM25 with Lucene-standard positive-smoothed IDF:
    IDF = ln(1 + (N - n + 0.5) / (n + 0.5))
    Guarantees strictly positive scores even for single/dual-document corpora,
    preventing 0.0 scores when a query term appears in 1 of 2 documents.
    """

    def _calc_idf(self, nd: Dict[str, int]) -> None:
        self.idf = {}
        for word, freq in nd.items():
            self.idf[word] = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))
        self.average_idf = sum(self.idf.values()) / max(len(self.idf), 1)


def tokenize_code_and_prose(text: str) -> List[str]:
    """
    Custom identifier-aware tokenizer designed for technical documents, code, and prose.
    - Extracts alphanumeric words and programming identifiers.
    - Preserves exact compound identifiers (e.g., 'auth_middleware', 'getDbConnection', 'app.core.config').
    - Preserves dotted/path sub-parts (e.g. 'DB_PATH' inside 'app.core.config.DB_PATH').
    - Splits compound tokens into sub-tokens (snake_case, camelCase, path separators, dots).
    - Lowercases all tokens for uniform casing matching.
    """
    if not text:
        return []

    tokens: List[str] = []
    candidates = re.findall(r"[a-zA-Z0-9_\-\.\/]+", text)

    for cand in candidates:
        cand_lower = cand.lower().strip(".-/")
        if not cand_lower:
            continue

        # 1. Always retain the exact unified token
        tokens.append(cand_lower)

        # 2. Split on dot / slash / path boundaries first
        path_parts = re.split(r"[/.]+", cand)
        for part in path_parts:
            part_lower = part.lower().strip("_-")
            if not part_lower:
                continue
            if part_lower != cand_lower:
                tokens.append(part_lower)

            # 3. Split on underscore / hyphen
            sub_parts = re.split(r"[_\-]+", part)
            for sp in sub_parts:
                sp_lower = sp.lower()
                if not sp_lower:
                    continue
                if sp_lower != part_lower and sp_lower != cand_lower:
                    tokens.append(sp_lower)

                # 4. Split camelCase / PascalCase sub-parts
                camel_parts = re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?=[A-Z][a-z0-9]|\b)", sp)
                if camel_parts and len(camel_parts) > 1:
                    for cp in camel_parts:
                        cp_lower = cp.lower()
                        if cp_lower != sp_lower and cp_lower != cand_lower:
                            tokens.append(cp_lower)

    return tokens


class BM25Index:
    """
    Thread-safe BM25 inverted term index with:
    - Identifier-aware tokenization
    - Dynamic document addition and deletion
    - Atomic persistence (bm25.pkl)
    """

    def __init__(
        self,
        index_path: Optional[Path] = None,
        k1: float = 1.5,
        b: float = 0.75,
    ):
        self.index_path = index_path or config.BM25_INDEX_PATH
        self.k1 = k1
        self.b = b
        self._lock = threading.Lock()

        # In-memory document storage: chunk_id -> tokenized list of strings
        self._corpus_tokens: Dict[str, List[str]] = {}
        self._chunk_ids: List[str] = []
        self._bm25: Optional[RobustBM25Okapi] = None

        self._init_index()

    def _init_index(self) -> None:
        """Loads index from disk if present, otherwise starts empty."""
        if self.index_path.exists():
            try:
                self.load(self.index_path)
                return
            except Exception as e:
                logger.warning(
                    f"Failed to load existing BM25 index from {self.index_path}: {e}. Initializing fresh index."
                )

        self._corpus_tokens.clear()
        self._chunk_ids.clear()
        self._bm25 = None

    @property
    def total_documents(self) -> int:
        """Returns total number of indexed passages/documents."""
        with self._lock:
            return len(self._corpus_tokens)

    def _rebuild_bm25(self) -> None:
        """Reconstructs the RobustBM25Okapi engine from stored tokenized documents."""
        self._chunk_ids = list(self._corpus_tokens.keys())
        tokenized_corpus = [self._corpus_tokens[cid] for cid in self._chunk_ids]

        if tokenized_corpus:
            self._bm25 = RobustBM25Okapi(tokenized_corpus, k1=self.k1, b=self.b)
        else:
            self._bm25 = None

    def add_documents(
        self,
        chunk_ids: List[str],
        texts: List[str],
    ) -> None:
        """
        Tokenizes and indexes a batch of document texts associated with chunk_ids.

        Args:
            chunk_ids: List of unique chunk IDs.
            texts: List of corresponding document texts.
        """
        if not chunk_ids or not texts:
            return

        if len(chunk_ids) != len(texts):
            raise ValueError(
                f"Mismatch between chunk_ids count ({len(chunk_ids)}) and texts count ({len(texts)})"
            )

        with self._lock:
            for cid, text in zip(chunk_ids, texts):
                self._corpus_tokens[cid] = tokenize_code_and_prose(text)

            self._rebuild_bm25()

        logger.debug(f"Added {len(chunk_ids)} documents to BM25 index. Total: {self.total_documents}")

    def remove_documents(self, chunk_ids: List[str]) -> int:
        """
        Removes documents by chunk_ids and rebuilds the BM25 index.

        Returns:
            Number of documents actually removed.
        """
        if not chunk_ids:
            return 0

        with self._lock:
            removed = 0
            for cid in chunk_ids:
                if cid in self._corpus_tokens:
                    del self._corpus_tokens[cid]
                    removed += 1

            if removed > 0:
                self._rebuild_bm25()

        logger.debug(f"Removed {removed} documents from BM25 index. Total: {self.total_documents}")
        return removed

    def search(
        self,
        query: str,
        top_k: int = 50,
    ) -> List[LexicalSearchResult]:
        """
        Executes BM25 lexical ranking for a query string.

        Args:
            query: The search query string.
            top_k: Maximum candidate passages to return.

        Returns:
            List of LexicalSearchResult objects sorted descending by BM25 score.
        """
        if not query or not query.strip() or self.total_documents == 0 or top_k <= 0:
            return []

        query_tokens = tokenize_code_and_prose(query)
        if not query_tokens:
            return []

        with self._lock:
            if self._bm25 is None or not self._chunk_ids:
                return []

            scores = self._bm25.get_scores(query_tokens)

            # Collect candidates with positive relevance score
            candidates: List[LexicalSearchResult] = []
            for cid, score in zip(self._chunk_ids, scores):
                if score > 0.0:
                    candidates.append(LexicalSearchResult(chunk_id=cid, score=float(score)))

            # Sort descending by score
            candidates.sort(key=lambda x: x.score, reverse=True)
            return candidates[:top_k]

    def save(self, target_path: Optional[Path] = None) -> None:
        """
        Atomically persists the tokenized corpus to disk as a pickle file.
        """
        target = target_path or self.index_path
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = Path(str(target) + ".tmp")

        with self._lock:
            data = {
                "corpus_tokens": self._corpus_tokens,
                "k1": self.k1,
                "b": self.b,
            }
            with open(tmp_path, "wb") as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            if tmp_path.exists():
                # On Windows, retry briefly if another reader holds a transient lock
                import time
                for attempt in range(5):
                    try:
                        os.replace(str(tmp_path), str(target))
                        break
                    except OSError as e:
                        if attempt == 4:
                            logger.warning(f"Failed to persist BM25 index after 5 retries: {e}")
                        else:
                            time.sleep(0.05 * (attempt + 1))

        logger.info(f"BM25 index saved atomically to {target} ({self.total_documents} documents).")

    def load(self, source_path: Optional[Path] = None) -> None:
        """
        Loads the tokenized corpus from disk and reconstructs RobustBM25Okapi.
        """
        source = source_path or self.index_path
        if not source.exists():
            raise FileNotFoundError(f"BM25 index file does not exist at {source}")

        with self._lock:
            with open(source, "rb") as f:
                data = pickle.load(f)

            self._corpus_tokens = data.get("corpus_tokens", {})
            self.k1 = data.get("k1", 1.5)
            self.b = data.get("b", 0.75)
            self._rebuild_bm25()

        logger.info(f"Loaded BM25 index from {source} with {self.total_documents} documents.")

    def clear(self) -> None:
        """Clears all documents from memory."""
        with self._lock:
            self._corpus_tokens.clear()
            self._chunk_ids.clear()
            self._bm25 = None


# Global singleton instance
_BM25_INSTANCE: Optional[BM25Index] = None
_BM25_LOCK = threading.Lock()


def get_bm25_index() -> BM25Index:
    """Returns singleton BM25Index instance."""
    global _BM25_INSTANCE
    if _BM25_INSTANCE is None:
        with _BM25_LOCK:
            if _BM25_INSTANCE is None:
                _BM25_INSTANCE = BM25Index()
    return _BM25_INSTANCE
