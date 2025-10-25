"""Tests for FastAPI REST API endpoints.

This module tests all API endpoints including:
- Root endpoint
- Health check
- Search with various filters
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.core.models import Message


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def client(mock_db_session):
    """Create test client for FastAPI app with mocked database."""
    from src.api.database import get_db

    # Override the get_db dependency to return our mock
    def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    test_client = TestClient(app)

    yield test_client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def sample_messages():
    """Create sample messages for testing."""
    return [
        Message(
            id=1,
            archive_id=100,
            message_id=1001,
            telegram_date=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
            text="Report from Bakhmut: heavy combat ongoing",
            raw_text="Report from Bakhmut: heavy combat ongoing",
            has_media=False,
            is_spam=False,
            is_forwarded=False,
            osint_value_score=85.0,
            topics=["combat", "military"],
            entities={"locations": ["Bakhmut"], "persons": []},
            geolocations=None,
            sentiment="negative",
            views_count=1500,
            forwards_count=45,
            replies_count=12,
            reactions_count=230,
        ),
        Message(
            id=2,
            archive_id=100,
            message_id=1002,
            telegram_date=datetime(2025, 10, 25, 11, 0, 0, tzinfo=timezone.utc),
            text="Drone footage from the eastern front",
            raw_text="Drone footage from the eastern front",
            has_media=True,
            media_type="video",
            is_spam=False,
            is_forwarded=True,
            osint_value_score=92.0,
            topics=["combat", "surveillance"],
            entities={"locations": [], "persons": []},
            geolocations={"coordinates": [{"lat": 48.5, "lon": 37.8}]},
            sentiment="neutral",
            views_count=3500,
            forwards_count=120,
            replies_count=35,
            reactions_count=580,
        ),
        Message(
            id=3,
            archive_id=100,
            message_id=1003,
            telegram_date=datetime(2025, 10, 25, 12, 0, 0, tzinfo=timezone.utc),
            text="General update on humanitarian situation",
            raw_text="General update on humanitarian situation",
            has_media=False,
            is_spam=False,
            is_forwarded=False,
            osint_value_score=45.0,
            topics=["humanitarian"],
            entities={"locations": [], "persons": []},
            geolocations=None,
            sentiment="neutral",
            views_count=800,
            forwards_count=15,
            replies_count=5,
            reactions_count=90,
        ),
    ]


class TestRootEndpoint:
    """Tests for root endpoint (/)."""

    def test_root_returns_api_info(self, client):
        """Test that root endpoint returns API information."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "OSINT Semantic Archive API"
        assert data["version"] == "0.1.0"
        assert "description" in data


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    @patch("src.api.routes.health.check_database_connection")
    def test_health_check_healthy(self, mock_db_check, client):
        """Test health check returns healthy status when DB is connected."""
        mock_db_check.return_value = True

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert "timestamp" in data

    @patch("src.api.routes.health.check_database_connection")
    def test_health_check_unhealthy(self, mock_db_check, client):
        """Test health check returns unhealthy status when DB is down."""
        mock_db_check.return_value = False

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"


class TestSearchEndpoint:
    """Tests for search endpoint."""

    def test_search_without_filters(self, client, mock_db_session, sample_messages):
        """Test search without any filters returns all messages."""
        # Setup mock
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query

        # Chain the query methods
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 3
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = sample_messages

        response = client.get("/api/search")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 3
        assert len(data["results"]) == 3
        assert data["query"] is None
        assert "limit" in data["filters_applied"]

    def test_search_with_text_query(self, client, mock_db_session, sample_messages):
        """Test search with text query filter."""
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query

        # Filter to return only messages matching "Bakhmut"
        filtered_messages = [msg for msg in sample_messages if "Bakhmut" in msg.text]

        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = len(filtered_messages)
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = filtered_messages

        response = client.get("/api/search?q=Bakhmut")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert len(data["results"]) == 1
        assert data["query"] == "Bakhmut"
        assert "Bakhmut" in data["results"][0]["text"]

    def test_search_with_min_osint_score(self, client, mock_db_session, sample_messages):
        """Test search with minimum OSINT score filter."""
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query

        # Filter to return only messages with score >= 70
        filtered_messages = [msg for msg in sample_messages if msg.osint_value_score >= 70]

        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = len(filtered_messages)
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = filtered_messages

        response = client.get("/api/search?min_osint_score=70")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 2
        assert len(data["results"]) == 2
        assert data["filters_applied"]["min_osint_score"] == 70
        # Verify all results meet the score threshold
        for result in data["results"]:
            assert result["osint_value"] >= 70

    def test_search_with_topics_filter(self, client, mock_db_session, sample_messages):
        """Test search with topics filter."""
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query

        # Filter to return only messages with "combat" topic
        filtered_messages = [msg for msg in sample_messages if msg.topics and "combat" in msg.topics]

        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = len(filtered_messages)
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = filtered_messages

        response = client.get("/api/search?topics=combat")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 2
        assert len(data["results"]) == 2
        assert data["filters_applied"]["topics"] == ["combat"]

    def test_search_with_combined_filters(self, client, mock_db_session, sample_messages):
        """Test search with multiple filters combined."""
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query

        # Filter with multiple conditions
        filtered_messages = [
            msg for msg in sample_messages
            if msg.osint_value_score >= 80 and msg.topics and "combat" in msg.topics
        ]

        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = len(filtered_messages)
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = filtered_messages

        response = client.get("/api/search?min_osint_score=80&topics=combat&limit=10")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 2
        assert data["filters_applied"]["min_osint_score"] == 80
        assert data["filters_applied"]["topics"] == ["combat"]
        assert data["filters_applied"]["limit"] == 10

    def test_search_with_pagination(self, client, mock_db_session, sample_messages):
        """Test search with pagination parameters."""
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query

        # Return subset for pagination
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 3
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = sample_messages[1:3]  # Skip first, return next 2

        response = client.get("/api/search?limit=2&offset=1")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 3
        assert len(data["results"]) == 2
        assert data["filters_applied"]["limit"] == 2
        assert data["filters_applied"]["offset"] == 1

    def test_search_invalid_osint_score(self, client):
        """Test search with invalid OSINT score returns validation error."""
        response = client.get("/api/search?min_osint_score=150")

        assert response.status_code == 422  # Unprocessable Entity

    def test_search_invalid_limit(self, client):
        """Test search with invalid limit returns validation error."""
        response = client.get("/api/search?limit=0")

        assert response.status_code == 422  # Unprocessable Entity

    def test_search_response_structure(self, client, mock_db_session, sample_messages):
        """Test that search response has correct structure."""
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query

        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [sample_messages[0]]

        response = client.get("/api/search?q=Bakhmut")

        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        assert "total" in data
        assert "results" in data
        assert "query" in data
        assert "filters_applied" in data

        # Check message structure
        message = data["results"][0]
        assert "id" in message
        assert "message_id" in message
        assert "archive_id" in message
        assert "text" in message
        assert "date" in message
        assert "osint_value" in message
        assert "topics" in message
        assert "entities" in message
        assert "has_media" in message
        assert "is_spam" in message
