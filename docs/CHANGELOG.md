# Changelog — FindIT

All notable changes to the FindIT project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
