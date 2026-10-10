# Changelog — FindIT

All notable changes to the FindIT project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
