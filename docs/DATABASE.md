# Database Schema & Storage Architecture — FindIT

> **Document Status**: `APPROVED` | **Version**: 1.0  
> **Primary Storage Engine**: SQLite 3 (WAL Mode)  
> **Auxiliary Storage Engines**: FAISS (Dense Vectors), BM25 (Inverted Index)  

---

## 1. Storage Architecture Overview

FindIT utilizes a **hybrid persistence model** designed for local reliability, zero configuration, and transactional consistency:

1. **SQLite 3 (`findit.db`)**: Acts as the transactional single source of truth for all structured metadata, registered directories, document records, extracted passage texts, source locations, and background sync jobs. Configured with Write-Ahead Logging (`PRAGMA journal_mode=WAL`) and foreign key enforcement (`PRAGMA foreign_keys=ON`).
2. **FAISS (`vector_index.faiss`)**: Stores 384-dimensional dense vectors. Maps a continuous 64-bit integer `vector_id` directly to each indexed passage.
3. **BM25 (`bm25_index.bin`)**: Maintains the inverted term frequency index and document length statistics, keyed by `chunk_id`.

---

## 2. SQLite Relational Schema

### 2.1 Schema DDL

```sql
-- Enable foreign keys and WAL mode
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ============================================================================
-- 1. DIRECTORIES TABLE
-- Stores user-approved root directories registered for indexing.
-- ============================================================================
CREATE TABLE IF NOT EXISTS directories (
    directory_id            TEXT PRIMARY KEY,
    canonical_path          TEXT NOT NULL UNIQUE,
    display_name            TEXT NOT NULL,
    added_at                TEXT NOT NULL, -- ISO-8601 UTC
    last_sync_started_at    TEXT,
    last_sync_completed_at  TEXT,
    sync_status             TEXT NOT NULL DEFAULT 'IDLE', -- IDLE, SYNCING, ERROR
    last_error              TEXT
);

-- ============================================================================
-- 2. DOCUMENTS TABLE
-- Represents individual files discovered within registered directory roots.
-- ============================================================================
CREATE TABLE IF NOT EXISTS documents (
    document_id             TEXT PRIMARY KEY,
    directory_id            TEXT NOT NULL,
    canonical_path          TEXT NOT NULL UNIQUE,
    filename                TEXT NOT NULL,
    extension               TEXT NOT NULL,
    file_type               TEXT NOT NULL, -- pdf, pptx, docx, md, txt, code, config
    size_bytes              INTEGER NOT NULL,
    modified_time           INTEGER NOT NULL, -- Epoch ms or unix timestamp
    content_fingerprint     TEXT,             -- SHA-256 hash when computed
    extraction_status       TEXT NOT NULL,    -- OK, NO_TEXT, ERROR, UNSUPPORTED
    last_indexed_at         TEXT,             -- ISO-8601 UTC
    extractor_version       TEXT,
    embedding_model_version TEXT,
    FOREIGN KEY (directory_id) REFERENCES directories(directory_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_documents_directory ON documents(directory_id);
CREATE INDEX IF NOT EXISTS idx_documents_path ON documents(canonical_path);

-- ============================================================================
-- 3. PASSAGES TABLE
-- The core retrieval unit representing extracted and segmented text chunks.
-- ============================================================================
CREATE TABLE IF NOT EXISTS passages (
    chunk_id                TEXT PRIMARY KEY, -- e.g. doc123_001
    document_id             TEXT NOT NULL,
    chunk_ordinal           INTEGER NOT NULL,
    text                    TEXT NOT NULL,    -- Faithful raw extracted text
    normalized_text         TEXT,             -- Cleaned text used for indexing
    
    -- Format-specific location metadata
    page_number             INTEGER,          -- 1-indexed (PDF)
    start_page              INTEGER,
    end_page                INTEGER,
    slide_number            INTEGER,          -- 1-indexed (PPTX)
    start_line              INTEGER,          -- 1-indexed (TXT, Code, Markdown)
    end_line                INTEGER,
    section_heading         TEXT,             -- Markdown heading / DOCX section
    paragraph_index         INTEGER,          -- DOCX paragraph
    source_start_offset     INTEGER,          -- Character offset in original text
    source_end_offset       INTEGER,
    
    -- Vector linkage
    vector_id               INTEGER UNIQUE,   -- Maps 1:1 to FAISS row ID
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_passages_document ON passages(document_id);
CREATE INDEX IF NOT EXISTS idx_passages_vector_id ON passages(vector_id);

-- ============================================================================
-- 4. INDEX_JOBS TABLE
-- Tracks asynchronous indexing, background sync progress, and diagnostics.
-- ============================================================================
CREATE TABLE IF NOT EXISTS index_jobs (
    job_id                  TEXT PRIMARY KEY,
    directory_id            TEXT,             -- NULL if global sync-all
    job_type                TEXT NOT NULL,    -- INITIAL_INDEX, SYNC_DIRECTORY, SYNC_ALL
    status                  TEXT NOT NULL,    -- QUEUED, RUNNING, COMPLETED, FAILED
    stage                   TEXT NOT NULL,    -- VALIDATING, SCANNING, EXTRACTING, EMBEDDING, INDEXING
    files_discovered        INTEGER NOT NULL DEFAULT 0,
    files_processed         INTEGER NOT NULL DEFAULT 0,
    files_failed            INTEGER NOT NULL DEFAULT 0,
    passages_created        INTEGER NOT NULL DEFAULT 0,
    started_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,
    completed_at            TEXT,
    error_summary           TEXT,
    FOREIGN KEY (directory_id) REFERENCES directories(directory_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON index_jobs(status);
```

---

## 3. Vector & Lexical Index Architecture

### 3.1 FAISS Vector Store Integration
- **Index Architecture**: `faiss.IndexFlatIP(384)`.
- **Vector Mapping**:
  - FAISS relies on positional integer IDs ($0, 1, 2, \dots, N-1$).
  - SQLite `passages.vector_id` explicitly maintains this mapping.
  - When FAISS returns top-$K$ integer vector IDs, the backend queries SQLite:
    ```sql
    SELECT * FROM passages WHERE vector_id IN (:id1, :id2, ...);
    ```
- **Vector Serialization**: Saved to disk via `faiss.write_index(index, "vector_index.faiss")` upon completion of an indexing batch.

### 3.2 BM25 Lexical Store Integration
- **Index Data**: Inverted index mapping vocabulary terms to `(chunk_id, term_frequency)` tuples, along with document lengths.
- **Query Resolution**: BM25 query execution returns `chunk_id` strings directly, which are joined with FAISS candidate IDs during RRF fusion.

---

## 4. Index Lifecycle & Atomic Maintenance

### 4.1 Safe Deletion (Cascade Behavior)
When a directory is removed by the user:
1. `DELETE FROM directories WHERE directory_id = :id;` triggers automatic cascade deletion of all child `documents` and `passages` in SQLite.
2. The backend purges or rebuilds the FAISS index to eliminate orphaned vectors.
3. The BM25 term index is purged of all deleted `chunk_id` entries.

### 4.2 Crash Recovery & Rebuild Protocol
If `vector_index.faiss` or `bm25_index.bin` suffers corruption:
1. All documents and raw passage texts remain intact in SQLite.
2. The backend initiates an automated rebuild:
   - Reads all records from `passages`.
   - Batches passage text through `all-MiniLM-L6-v2` to regenerate embeddings.
   - Populates a new `IndexFlatIP` index and resets `vector_id`.
   - Rebuilds the BM25 inverted index.
3. Source files on disk are **never re-read** during index rebuilds, saving substantial disk I/O.
