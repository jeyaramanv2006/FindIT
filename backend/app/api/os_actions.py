"""
FindIT Operating System Integration API Router
Exposes native file explorer launcher and application launch endpoints.
"""

from typing import Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.os_service import OSService, SecurityBoundaryError

router = APIRouter(tags=["OS Integration"])


class OpenLocationRequestBody(BaseModel):
    path: Optional[str] = Field(default=None, description="Direct file path to open in file explorer")
    document_id: Optional[str] = Field(default=None, description="Document ID to open in file explorer")


class OSActionResponse(BaseModel):
    success: bool
    message: str
    path: Optional[str] = None


@router.post("/open-location", response_model=OSActionResponse)
async def open_location(body: OpenLocationRequestBody):
    """
    POST /api/open-location
    Commands the native operating system file manager to open and select
    the specified file path or document ID with directory confinement checks.
    """
    if not body.path and not body.document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either 'path' or 'document_id'.",
        )

    try:
        if body.document_id:
            target_path = OSService.get_document_path(body.document_id)
            revealed = OSService.open_containing_folder(target_path, validate_confinement=False)
        else:
            revealed = OSService.open_containing_folder(body.path, validate_confinement=True)

        return OSActionResponse(
            success=True,
            message="Opened containing folder in native file explorer.",
            path=revealed,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except SecurityBoundaryError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/documents/{document_id}/open-folder", response_model=OSActionResponse)
async def open_document_folder(document_id: str):
    """
    POST /api/documents/{document_id}/open-folder
    Opens the directory containing the document and selects/highlights it.
    """
    try:
        target_path = OSService.get_document_path(document_id)
        revealed = OSService.open_containing_folder(target_path, validate_confinement=False)
        return OSActionResponse(
            success=True,
            message="Opened containing folder in native explorer.",
            path=revealed,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except SecurityBoundaryError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/documents/{document_id}/open", response_model=OSActionResponse)
async def open_document_file(document_id: str):
    """
    POST /api/documents/{document_id}/open
    Opens the document in its default associated OS application.
    """
    try:
        opened = OSService.open_document(document_id)
        return OSActionResponse(
            success=True,
            message="Launched file in default application.",
            path=opened,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except SecurityBoundaryError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
