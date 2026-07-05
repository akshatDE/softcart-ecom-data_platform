"""FastAPI application exposing the SoftCart analytics layer.

Run locally with::

    uvicorn src.main.api.app:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.main.api.routes.analytics_routes import router as analytics_router
from src.main.api.routes.nlp_sql_routes import router as nlp_router
from src.main.utility.logger import get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """Application factory."""
    application = FastAPI(
        title="SoftCart Analytics API",
        description=(
            "Read-only analytics over the SoftCart DuckDB star schema, "
            "plus AI-assisted natural-language querying."
        ),
        version="1.0.0",
    )
    # The Streamlit dashboard is the only expected browser client; keep CORS
    # open for local development convenience.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    application.include_router(analytics_router)
    application.include_router(nlp_router)

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        """Liveness probe used by docker-compose health checks."""
        return {"status": "ok"}

    logger.info("FastAPI application created")
    return application


app = create_app()
