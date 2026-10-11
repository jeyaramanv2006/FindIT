from fastapi import APIRouter

router = APIRouter(tags=["Health"])

@router.get("/health")
def health_check():
    """
    Returns server operational status and version.
    """
    return {
        "status": "ok",
        "service": "FindIT Backend",
        "version": "1.0.0"
    }
