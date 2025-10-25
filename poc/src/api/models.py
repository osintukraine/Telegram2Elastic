"""Pydantic models for API request/response validation.

These models define the schema for API responses and ensure
type safety and validation for client applications.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """Response model for a single message."""

    id: int = Field(..., description="Message database ID")
    message_id: int = Field(..., description="Telegram message ID")
    archive_id: int = Field(..., description="Archive (channel) ID")
    text: Optional[str] = Field(None, description="Message text content")
    date: datetime = Field(..., description="Message timestamp")

    # Enrichment fields
    osint_value: Optional[float] = Field(None, description="OSINT value score (0-100)")
    topics: Optional[List[str]] = Field(None, description="Classified topics")
    entities: Optional[Dict[str, Any]] = Field(None, description="Extracted entities")
    geolocations: Optional[Dict[str, Any]] = Field(None, description="Extracted geolocations")
    sentiment: Optional[str] = Field(None, description="Sentiment analysis")

    # Engagement metrics
    views_count: Optional[int] = Field(None, description="Number of views")
    forwards_count: Optional[int] = Field(None, description="Number of forwards")
    replies_count: Optional[int] = Field(None, description="Number of replies")
    reactions_count: Optional[int] = Field(None, description="Total reactions")

    # Media
    has_media: bool = Field(False, description="Whether message has media")
    media_type: Optional[str] = Field(None, description="Type of media")

    # Flags
    is_spam: bool = Field(False, description="Spam detection flag")
    is_forwarded: bool = Field(False, description="Whether message is forwarded")

    class Config:
        """Pydantic config."""
        from_attributes = True


class SearchResponse(BaseModel):
    """Response model for search endpoint."""

    total: int = Field(..., description="Total number of matching messages")
    results: List[MessageResponse] = Field(..., description="List of matching messages")
    query: Optional[str] = Field(None, description="Search query used")
    filters_applied: Dict[str, Any] = Field(default_factory=dict, description="Filters applied to search")


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    status: str = Field(..., description="Health status (healthy/unhealthy)")
    database: str = Field(..., description="Database connection status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")


class APIInfoResponse(BaseModel):
    """Response model for API info endpoint."""

    name: str = Field(..., description="API name")
    version: str = Field(..., description="API version")
    description: str = Field(..., description="API description")
