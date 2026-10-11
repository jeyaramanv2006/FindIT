from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core import config
from app.db.database import init_db
from app.api import health, directories

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

    # Register routers with /api prefix
    app.include_router(health.router, prefix="/api")
    app.include_router(directories.router, prefix="/api")

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=True)
