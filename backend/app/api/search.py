"""
FindIT Hybrid Search API Router
Exposes hybrid retrieval combining dense FAISS and sparse BM25 via Reciprocal Rank Fusion.
Synchronized with docs/API.md Section 4 and notes/EXECUTION_PLAN.md Batch 4.
"""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException, status
from pydantic import BaseModel, Field

from app.services.search_service import get_search_service, SearchResponse

router = APIRouter(tags=["Search"])


class SearchRequestBody(BaseModel):
    query: str = Field(..., min_length=1, description="Search query string")
    limit: int = Field(default=10, ge=1, le=100, description="Max passages to return")
    offset: int = Field(default=0, ge=0, description="Pagination offset")
    include_diagnostics: bool = Field(default=False, description="Include raw retriever diagnostics")


@router.post("/search", response_model=SearchResponse)
async def search_passages_post(body: SearchRequestBody):
    """
    POST /api/search
    Executes hybrid dense + lexical search using Reciprocal Rank Fusion (k=60).
    """
    service = get_search_service()
    try:
        response = service.search(
            query=body.query,
            limit=body.limit,
            offset=body.offset,
        )
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search execution failed: {str(e)}",
        )


@router.get("/search", response_model=SearchResponse)
async def search_passages_get(
    q: str = Query(..., min_length=1, description="Search query string"),
    limit: int = Query(default=10, ge=1, le=100, description="Max passages to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
):
    """
    GET /api/search?q=...&limit=10&offset=0
    Alternative GET endpoint for query-string-based hybrid search.
    """
    service = get_search_service()
    try:
        response = service.search(
            query=q,
            limit=limit,
            offset=offset,
        )
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search execution failed: {str(e)}",
        )
