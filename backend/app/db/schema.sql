-- FindIT SQLite Database Schema
-- Synchronized with docs/DATABASE.md specification

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

CREATE INDEX IF NOT EXISTS idx_directories_canonical_path ON directories(canonical_path);

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
