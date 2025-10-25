"""FastAPI application for OSINT Semantic Archive API.

This is the main entry point for the REST API server. It provides:
- Message search with semantic enrichment filters
- Health check endpoint
- API documentation (automatic via FastAPI)

For PoC purposes, this is simplified with:
- No authentication (public API)
- No rate limiting
- Synchronous database queries
- Basic error handling
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.models import APIInfoResponse
from src.api.routes import health, search

# Create FastAPI application
app = FastAPI(
    title="OSINT Semantic Archive API",
    description="REST API for searching archived Telegram messages with AI-powered semantic enrichment",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware (allow all origins for PoC)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(search.router)


@app.get("/", response_model=APIInfoResponse, tags=["Root"])
def root() -> APIInfoResponse:
    """API root endpoint.

    Returns basic information about the API.

    Returns:
        APIInfoResponse: API name, version, and description

    Example:
        GET /
        Response:
        {
            "name": "OSINT Semantic Archive API",
            "version": "0.1.0",
            "description": "REST API for OSINT message search"
        }
    """
    return APIInfoResponse(
        name="OSINT Semantic Archive API",
        version="0.1.0",
        description="REST API for searching archived Telegram messages with semantic enrichment",
    )


# For running with uvicorn directly
if __name__ == "__main__":
    import uvicorn

    from src.core.config import Settings

    settings = Settings()
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )
