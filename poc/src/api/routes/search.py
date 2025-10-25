"""Search endpoint for querying archived messages.

This module provides the main search functionality for the OSINT Semantic Archive.
It supports filtering by text query, OSINT score, topics, and pagination.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import any_, func, or_
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.models import MessageResponse, SearchResponse
from src.core.models import Message

router = APIRouter()


@router.get("/api/search", response_model=SearchResponse, tags=["Search"])
def search_messages(
    q: Optional[str] = Query(None, description="Search query text"),
    min_osint_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum OSINT value score"),
    topics: Optional[List[str]] = Query(None, description="Filter by topics (can specify multiple)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """Search archived messages with filters.

    This endpoint allows searching through archived Telegram messages with various filters:
    - Text search (case-insensitive, searches in message text)
    - OSINT score filtering (minimum value)
    - Topic filtering (matches any of the specified topics)
    - Pagination support

    Args:
        q: Search query text (searches in message text field)
        min_osint_score: Minimum OSINT value score (0-100)
        topics: List of topics to filter by
        limit: Maximum number of results (default 100, max 1000)
        offset: Offset for pagination (default 0)
        db: Database session (injected)

    Returns:
        SearchResponse: Search results with total count and matching messages

    Example:
        GET /api/search?q=Bakhmut&min_osint_score=70&limit=10
        Response:
        {
            "total": 15,
            "results": [
                {
                    "id": 123,
                    "text": "Report from Bakhmut...",
                    "osint_value": 85,
                    "topics": ["combat", "military"],
                    "date": "2025-10-25T10:00:00Z"
                }
            ],
            "query": "Bakhmut",
            "filters_applied": {
                "min_osint_score": 70,
                "limit": 10
            }
        }
    """
    # Build query
    query = db.query(Message)

    # Track filters for response
    filters_applied = {"limit": limit, "offset": offset}

    # Filter by text search (case-insensitive LIKE)
    if q:
        search_pattern = f"%{q}%"
        query = query.filter(
            or_(
                Message.text.ilike(search_pattern),
                Message.raw_text.ilike(search_pattern),
            )
        )
        filters_applied["query"] = q

    # Filter by minimum OSINT score
    if min_osint_score is not None:
        query = query.filter(Message.osint_value_score >= min_osint_score)
        filters_applied["min_osint_score"] = min_osint_score

    # Filter by topics (match any of the specified topics)
    if topics:
        # Check if message topics array contains any of the specified topics
        # Use any_ with contains for simpler logic that works with array types
        topic_conditions = []
        for topic in topics:
            # Check if the topic is in the array
            topic_conditions.append(Message.topics.any(topic))
        query = query.filter(or_(*topic_conditions))
        filters_applied["topics"] = topics

    # Filter out spam by default
    query = query.filter(Message.is_spam == False)

    # Order by OSINT score (highest first), then by date (newest first)
    query = query.order_by(
        Message.osint_value_score.desc().nulls_last(),
        Message.telegram_date.desc(),
    )

    # Get total count before pagination
    total = query.count()

    # Apply pagination
    results = query.offset(offset).limit(limit).all()

    # Convert to response models
    message_responses = [
        MessageResponse(
            id=msg.id,
            message_id=msg.message_id,
            archive_id=msg.archive_id,
            text=msg.text,
            date=msg.telegram_date,
            osint_value=msg.osint_value_score,
            topics=msg.topics,
            entities=msg.entities,
            geolocations=msg.geolocations,
            sentiment=msg.sentiment,
            views_count=msg.views_count,
            forwards_count=msg.forwards_count,
            replies_count=msg.replies_count,
            reactions_count=msg.reactions_count,
            has_media=msg.has_media,
            media_type=msg.media_type,
            is_spam=msg.is_spam,
            is_forwarded=msg.is_forwarded,
        )
        for msg in results
    ]

    return SearchResponse(
        total=total,
        results=message_responses,
        query=q,
        filters_applied=filters_applied,
    )
