"""
FindIT Synchronization & Background Job API Endpoints

Exposes:
- POST /api/sync : Trigger incremental synchronization across all registered directories.
- POST /api/sync/{directory_id} : Trigger sync for a specific directory.
- GET /api/sync/status : Query active/recent indexing jobs and progress metrics.
- GET /api/jobs/{job_id} : Inspect detailed execution status and stage for a specific job.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.sync.worker import get_sync_worker
from app.db.database import get_db

router = APIRouter(tags=["Synchronization & Background Jobs"])


class SyncResponse(BaseModel):
    job_id: str
    directory_id: str
    status: str


class SyncAllResponse(BaseModel):
    status: str
    jobs: list


@router.post(
    "/sync",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Global Sync Across All Registered Directories",
)
def trigger_sync_all():
    """
    Enqueues background incremental sync jobs for all user-approved directories.
    """
    worker = get_sync_worker()
    jobs = worker.start_sync_all(background=True)
    return {
        "status": "QUEUED",
        "jobs": jobs,
    }


@router.post(
    "/sync/{directory_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Directory Incremental Sync",
)
def trigger_sync_directory(directory_id: str):
    """
    Enqueues an incremental synchronization job for a single registered directory.
    Detects new, modified, and deleted files, extracts text, generates embeddings,
    and updates FAISS and BM25 indices.
    """
    # Verify directory exists in SQLite
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT directory_id FROM directories WHERE directory_id = ?;", (directory_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "DIRECTORY_NOT_FOUND",
                        "message": f"Directory ID '{directory_id}' does not exist.",
                    }
                },
            )

    worker = get_sync_worker()
    job_id = worker.start_sync(directory_id, background=True)
    return {
        "job_id": job_id,
        "directory_id": directory_id,
        "status": "QUEUED",
    }


@router.get(
    "/sync/status",
    summary="Query Sync Status & Progress Metrics",
)
def get_sync_status(
    job_id: Optional[str] = Query(None, description="Filter by specific job ID"),
    directory_id: Optional[str] = Query(None, description="Filter by directory ID"),
):
    """
    Returns live progress, current stage, and file metrics for running or recent sync jobs.
    """
    worker = get_sync_worker()
    if job_id:
        job = worker.get_job_status(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "JOB_NOT_FOUND",
                        "message": f"Job ID '{job_id}' does not exist.",
                    }
                },
            )
        return {"jobs": [job]}

    jobs = worker.list_jobs(directory_id=directory_id, limit=20)
    return {"jobs": jobs}


@router.get(
    "/jobs/{job_id}",
    summary="Get Detailed Index Job Status",
)
def get_job_by_id(job_id: str):
    """
    Retrieves full progress status, stage, and file counts for an active or completed indexing job.
    Synchronized with docs/API.md Section 3.1.
    """
    worker = get_sync_worker()
    job = worker.get_job_status(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": f"Job ID '{job_id}' not found.",
                }
            },
        )
    return job
