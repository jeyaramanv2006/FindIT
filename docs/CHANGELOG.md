# Changelog — FindIT

All notable changes to the FindIT project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0-m5] - 2026-10-11

### Completed
- **Milestone 5 & Batch 4 (Phases 9, 10, 11) — Hybrid Search (RRF), Passage Inspector API & Native OS Launcher**:
  - Implemented `SearchService` in `backend/app/services/search_service.py`:
    - Dispatches queries to FAISS (top-50 semantic) and BM25 (top-50 lexical).
    - Fuses results via Reciprocal Rank Fusion ($k=60$): $RRF(d) = \sum_{r \in \mathcal{R}} \frac{1}{60 + \text{rank}_r(d)}$.
    - Hydrates ranked candidate chunks with SQLite metadata (`documents` and `passages` tables).
    - Formats trustworthy location coordinate labels (`Page X`, `Slide Y`, `Lines X–Y`, `Section: Z`), passage preview snippets, and shortened display paths (`~/...`).
    - Implemented passage detail inspection with previous and next surrounding passage chunks in the same document.
  - Implemented `OSService` in `backend/app/services/os_service.py`:
    - Safe invocation of Windows Explorer (`explorer.exe /select,"<path>"`) with path traversal prevention and directory confinement against approved roots in SQLite.
    - Added document launch in default associated application.
  - Implemented API router endpoints:
    - `POST /api/search` and `GET /api/search`: hybrid search with pagination (`limit`, `offset`, `next_offset`).
    - `GET /api/passages/{chunk_id}`: full passage detail for Passage Inspector modal with surrounding context.
    - `POST /api/open-location`: reveals file in native explorer.
    - `POST /api/documents/{document_id}/open-folder`: opens document's containing folder.
    - `POST /api/documents/{document_id}/open`: launches document in default viewer.
  - Added test suite `backend/tests/test_search.py` with 12 tests covering RRF mathematics, search service, pagination, passage context, OS confinement security, and FastAPI endpoints.
  - Full backend test suite passing with **51/51 tests passing**.

## [0.1.0-m4] - 2026-10-11

### Completed
- **Milestone 4 & Batch 3 (Phases 6, 7, 8) — Semantic Embeddings, FAISS Vector Index & BM25 Lexical Engine**:
  - Implemented `EmbeddingEngine` and `get_embedder()` in `backend/app/embeddings/embedder.py`:
    - Wraps `sentence-transformers/all-MiniLM-L6-v2` with lazy loading on demand and CPU thread safety.
    - Produces exactly 384-dimensional dense vectors with strict L2-normalization ($\|\mathbf{v}\|_2 = 1.0$).
    - Supports batch document embedding (`embed_texts`) and single query vector inference (`embed_query`).
  - Implemented `FaissIndex` and `VectorSearchResult` in `backend/app/indexing/faiss_index.py`:
    - Wraps `faiss.IndexFlatIP(384)` inside `faiss.IndexIDMap2` for exact cosine similarity search and explicit 64-bit vector ID mapping.
    - Implemented vector insertion (`add_vectors`), ID-based removal (`remove_vectors`), and chunk removal (`remove_chunks`).
    - Implemented atomic serialization to disk (`backend/data/index.faiss`) and bidirectional `vector_id` $\leftrightarrow$ `chunk_id` metadata mapping (`index.faiss.map.json`).
  - Implemented `BM25Index`, `RobustBM25Okapi`, and `tokenize_code_and_prose` in `backend/app/indexing/bm25_index.py`:
    - Custom identifier-aware tokenizer extracting natural prose while preserving compound programming symbols (`snake_case`, `camelCase`, `PascalCase`, dotted module names, and file paths) alongside their individual sub-components.
    - Implemented `RobustBM25Okapi` with positive-smoothed Lucene IDF ($\ln(1 + \frac{N - n + 0.5}{n + 0.5})$) guaranteeing non-zero scores on small corpora.
    - Implemented dynamic document addition, deletion, and atomic pickle serialization (`backend/data/bm25.pkl`).
  - Created comprehensive unit test suite in `backend/tests/test_indices.py` covering:
    - 384D vector dimensions and unit norms.
    - FAISS exact inner-product search and 100 sample vector verification checkpoint with cosine similarities $\in [-1.0, 1.0]$.
    - BM25 verification checkpoint ranking exact `auth_middleware` matches over prose.
    - Rare identifier retrieval and atomic index save/reload fidelity.
  - Full backend test suite passing with **39/39 tests passing**.

## [0.1.0-m3] - 2026-10-11

### Completed
- **Milestone 3 & Batch 2 (Phases 3, 4, 5) — Multi-Format Extraction & Structure-Aware Chunking**:
  - Implemented `BaseExtractor`, `ExtractedBlock`, and `ExtractedDocument` contracts in `backend/app/extractors/base.py`.
  - Implemented `TextExtractor` in `backend/app/extractors/text_extractor.py` parsing `.txt`, `.md`, `.markdown`, source code (`.py`, `.ts`, `.js`, etc.), and config (`.json`, `.yaml`, `.toml`) with exact 1-indexed line numbers, markdown heading hierarchy stacks, and code symbol boundaries.
  - Implemented `PDFExtractor` in `backend/app/extractors/pdf_extractor.py` using PyMuPDF (`pymupdf`) extracting text per page with 1-indexed page coordinates (`Page X of Y`), paragraph grouping, and scanned non-text PDF fallback detection (`NO_TEXT`).
  - Implemented `DocxExtractor` in `backend/app/extractors/docx_extractor.py` using `python-docx` extracting headings, paragraphs, and tables with section hierarchy retention.
  - Implemented `PptxExtractor` in `backend/app/extractors/pptx_extractor.py` using `python-pptx` extracting slide titles, body shapes, and speaker notes with strict slide coordinate isolation (`Slide X`).
  - Implemented extractor factory in `backend/app/extractors/factory.py` resolving appropriate extractors by file extension.
  - Implemented `StructureAwareChunker` in `backend/app/chunking/chunker.py` using a 350-token window with 50-token overlap, ensuring zero text bleeding across PPTX slides, preserving PDF page numbers, and attaching exact 1-indexed line ranges and parent headings.
  - Added unit test suites `backend/tests/test_extractors.py` (9 tests) and `backend/tests/test_chunker.py` (5 tests). Entire backend test suite passes with **26/26 tests passing**.

## [0.1.0-m2] - 2026-10-11

### Completed
- **Milestone 2 & Phase 2 — Directory Management & Discovery Engine**:
  - Implemented `DirectoryService` in `backend/app/services/directory_service.py` supporting directory path canonicalization, system root drive rejection (`C:\`, `/`), overlap conflict detection, and file discovery.
  - Implemented recursive directory scanner (`scan_files`) with SHA-256 fingerprinting, symlink confinement checks, and support for all target document extensions (`.pdf`, `.docx`, `.pptx`, `.md`, `.txt`, `.py`, `.ts`, `.json`, etc.).
  - Added SQLite schema domain models in `backend/app/db/models.py` (`DirectoryModel`, `DirectorySummary`, `DocumentModel`, `PassageModel`, `IndexJobModel`).
  - Implemented REST API route controllers in `backend/app/api/directories.py`:
    - `GET /api/directories`: lists registered directories with live document and passage counts.
    - `POST /api/directories`: validates and registers new directory root with initial scan and job creation.
    - `DELETE /api/directories/{id}`: unlinks directory from database while preserving physical files on disk.
    - `POST /api/directories/{id}/sync`: triggers incremental scan of single registered directory.
    - `POST /api/directories/sync-all`: triggers batch sync across all registered directories.
    - `POST /api/directories/pick`: native OS folder picker dialog bridge.
  - Added comprehensive test suite in `backend/tests/test_directories.py` with 12 passing tests across database, health, directory CRUD, conflicts, root drive rejection, and mocked native picker.
  - Wired live directory CRUD, sync, and native picker client functions into React frontend (`src/services/api.ts`, `src/components/DirectoriesModal.tsx`, `src/App.tsx`).

## [0.1.0-m1] - 2026-10-11

### Completed
- **Milestone 1 — Project Skeleton & Local Runtime**:
  - Implemented and verified SQLite database initialization in WAL mode (`findit.db`) enforcing foreign keys and full schema DDL matching `docs/DATABASE.md` (`directories`, `documents`, `passages`, `index_jobs`).
  - Added unit test suite `tests/test_database.py` validating WAL pragmas, schema tables, and cascade deletion.
  - Implemented `/api/health` diagnostic endpoint matching `docs/API.md` response contract, verified via unit test (`tests/test_health.py`) and live HTTP curl.
  - Configured FastAPI application with strict loopback binding (`127.0.0.1:8000`), CORS allowlisting (`5173`, `3000`), and startup lifespan database initialization.
  - Integrated `checkBackendHealth` in frontend `src/services/api.ts` and added runtime status indicators across both Hero and Results views in `src/App.tsx`.
  - Verified frontend build (`tsc -b && vite build`) and running dev server (`http://localhost:5173/`).

## [0.1.0-spec] - 2026-10-11

### Added
- **Product & System Specification**:
  - `docs/PRD.md`: Full Product Requirements Document detailing product vision, personas, core promise, visual language (ivory canvas, terracotta contours), in-place transition choreography, and non-goals.
  - `docs/REQUIREMENTS.md`: Comprehensive requirement catalog with classification tracking (Confirmed, Proposed, Constraints, Ambiguities).
  - `docs/TRD.md`: Technical Requirements Document covering extractors, chunking, 384D `all-MiniLM-L6-v2` embeddings, FAISS `IndexFlatIP`, BM25, RRF algorithm ($k=60$), and benchmark test query suite.
  - `docs/ARCHITECTURE.md`: Complete system topology, component boundaries, sequence diagrams for indexing and search pipelines, and frontend state machine.
  - `docs/API.md`: Strict loopback-bound REST API contracts for directory management, search, passage retrieval, and native OS folder navigation.
  - `docs/DATABASE.md`: SQLite schema DDL (`directories`, `documents`, `passages`, `index_jobs`), vector mapping, and atomic rebuild strategy.
  - `docs/SECURITY.md`: Comprehensive threat model, path traversal defenses, approved-root boundary confinement, and source file immutability guarantees.
  - `docs/ROADMAP.md`: 8-milestone delivery schedule with explicit exit criteria and acceptance checklist.
  - `docs/DECISIONS.md`: Approved Architectural Decision Records (ADR-001 through ADR-009).
  - `docs/RISKS.md`: Risk assessment register with concrete mitigation strategies.
- **Agent Governance & Environment**:
  - `AGENTS.md`: AI execution guidelines establishing user final authority, strict prohibition against AI committing/pushing, and documentation synchronization rules.
  - `.gitignore`: Configured workspace ignore rules for `notes/`, `Stitch/`, and `.agents/`.
