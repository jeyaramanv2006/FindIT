"""
FindIT SQLite Database & Domain Models
Synchronized with docs/DATABASE.md and schema.sql
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field


SyncStatus = Literal["IDLE", "SYNCING", "ERROR"]
ExtractionStatus = Literal["OK", "NO_TEXT", "ERROR", "UNSUPPORTED"]
JobStatus = Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED"]
JobStage = Literal["VALIDATING", "SCANNING", "EXTRACTING", "EMBEDDING", "INDEXING"]
JobType = Literal["INITIAL_INDEX", "SYNC_DIRECTORY", "SYNC_ALL"]


class DirectoryModel(BaseModel):
    directory_id: str
    canonical_path: str
    display_name: str
    added_at: str
    last_sync_started_at: Optional[str] = None
    last_sync_completed_at: Optional[str] = None
    sync_status: SyncStatus = "IDLE"
    last_error: Optional[str] = None


class DirectorySummary(BaseModel):
    directory_id: str
    canonical_path: str
    display_name: str
    file_count: int = 0
    passage_count: int = 0
    sync_status: SyncStatus = "IDLE"
    last_sync_completed_at: Optional[str] = None
    last_error: Optional[str] = None


class DocumentModel(BaseModel):
    document_id: str
    directory_id: str
    canonical_path: str
    filename: str
    extension: str
    file_type: str
    size_bytes: int
    modified_time: int
    content_fingerprint: Optional[str] = None
    extraction_status: ExtractionStatus = "OK"
    last_indexed_at: Optional[str] = None
    extractor_version: Optional[str] = None
    embedding_model_version: Optional[str] = None


class PassageModel(BaseModel):
    chunk_id: str
    document_id: str
    chunk_ordinal: int
    text: str
    normalized_text: Optional[str] = None
    page_number: Optional[int] = None
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    slide_number: Optional[int] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    section_heading: Optional[str] = None
    paragraph_index: Optional[int] = None
    source_start_offset: Optional[int] = None
    source_end_offset: Optional[int] = None
    vector_id: Optional[int] = None


class IndexJobModel(BaseModel):
    job_id: str
    directory_id: Optional[str] = None
    job_type: JobType
    status: JobStatus
    stage: JobStage
    files_discovered: int = 0
    files_processed: int = 0
    files_failed: int = 0
    passages_created: int = 0
    started_at: str
    updated_at: str
    completed_at: Optional[str] = None
    error_summary: Optional[str] = None
