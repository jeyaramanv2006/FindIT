"""
FindIT Passage Retrieval & Inspection API Router
Exposes individual passage details with surrounding context for Passage Inspector modal.
"""

from fastapi import APIRouter, HTTPException, status
from app.services.search_service import get_search_service, PassageDetailResponse

router = APIRouter(prefix="/passages", tags=["Passages"])


@router.get("/{chunk_id}", response_model=PassageDetailResponse)
async def get_passage(chunk_id: str):
    """
    GET /api/passages/{chunk_id}
    Retrieves complete unvarnished passage text, precise location metadata,
    and surrounding context (previous/next passage chunks in same document).
    """
    service = get_search_service()
    detail = service.get_passage_detail(chunk_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Passage chunk with ID '{chunk_id}' not found.",
        )
    return detail
