import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core import config
from app.db.database import init_db
from app.api import health, directories, search, passages, os_actions, sync

logger = logging.getLogger("findit.api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database with WAL mode and schema tables
    init_db()
    yield

def create_app() -> FastAPI:
    app = FastAPI(
        title="FindIT API",
        description="Local-first hybrid semantic & lexical desktop search engine backend.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configure CORS for local development with frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global Exception Handlers
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            error_data = detail.get("error", detail)
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "detail": detail,
                    "error": error_data,
                },
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": detail,
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": str(detail),
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request parameters or payload structure.",
                    "details": exc.errors(),
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(
            f"Unhandled exception during {request.method} {request.url.path}: {exc}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected server error occurred.",
                    "detail": str(exc),
                }
            },
        )

    # Register routers with /api prefix
    app.include_router(health.router, prefix="/api")
    app.include_router(directories.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(passages.router, prefix="/api")
    app.include_router(os_actions.router, prefix="/api")
    app.include_router(sync.router, prefix="/api")

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=True)
