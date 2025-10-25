"""Health check endpoint for monitoring API status.

This module provides a simple health check endpoint that verifies:
- API is running
- Database connection is working
"""

from fastapi import APIRouter

from src.api.database import check_database_connection
from src.api.models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check() -> HealthResponse:
    """Check API and database health.

    This endpoint is used for monitoring and load balancer health checks.
    It verifies that the API is responsive and can connect to the database.

    Returns:
        HealthResponse: Health status information

    Example:
        GET /health
        Response:
        {
            "status": "healthy",
            "database": "connected",
            "timestamp": "2025-10-25T10:00:00Z"
        }
    """
    db_healthy = check_database_connection()

    return HealthResponse(
        status="healthy" if db_healthy else "unhealthy",
        database="connected" if db_healthy else "disconnected",
    )
