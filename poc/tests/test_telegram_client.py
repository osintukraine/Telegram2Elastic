"""Tests for Telegram client.

These tests use mocks to avoid requiring live Telegram connections.
They verify the core functionality of TelegramArchiveClient including:
- Client initialization
- Archive channel type validation
- Media download handling
- Message deduplication logic
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call

import pytest

from src.core.models import Archive, Message, MediaFile
from src.core.telegram_client import TelegramArchiveClient


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    settings = Mock()
    settings.telegram_api_id = 12345
    settings.telegram_api_hash = "test_hash"
    settings.telegram_phone = "+1234567890"
    settings.telegram_session_name = "test_session"
    settings.minio_endpoint = "localhost:9000"
    settings.minio_access_key = "minioadmin"
    settings.minio_secret_key = "minioadmin"
    settings.minio_bucket = "test-bucket"
    settings.minio_secure = False
    settings.database_url = "postgresql://test:test@localhost:5432/test"
    return settings


@pytest.fixture
def mock_telegram_message():
    """Mock Telegram message."""
    message = Mock()
    message.id = 123
    message.date = datetime.now(timezone.utc)
    message.message = "Test message"
    message.raw_text = "Test message"
    message.media = None
    message.forward = None
    message.views = 100
    message.forwards = 5
    message.reactions = None
    return message


@pytest.fixture
def mock_channel():
    """Mock Telegram channel."""
    from telethon.tl.types import Channel
    channel = Mock(spec=Channel)
    channel.id = 456789
    channel.username = "test_channel"
    channel.title = "Test Channel"
    channel.about = "Test channel description"
    return channel


@pytest.mark.asyncio
async def test_telegram_client_initialization(mock_settings):
    """Test TelegramArchiveClient initialization."""
    with patch("src.core.telegram_client.TelegramClient"), \
         patch("src.core.telegram_client.S3Client"), \
         patch("src.core.telegram_client.create_async_engine"):

        client = TelegramArchiveClient(mock_settings)

        # Verify client was initialized
        assert client.settings == mock_settings
        assert client.s3_client is not None
        assert client.client is not None
        assert client.db_engine is not None


@pytest.mark.asyncio
async def test_get_or_create_archive_validates_channel(mock_settings):
    """Test that get_or_create_archive validates the entity is a channel."""
    with patch("src.core.telegram_client.TelegramClient") as mock_client_class, \
         patch("src.core.telegram_client.S3Client"), \
         patch("src.core.telegram_client.create_async_engine"):

        # Setup mocks - return a non-channel entity (e.g., User)
        mock_client = AsyncMock()
        mock_user = Mock()
        mock_user.__class__.__name__ = "User"  # Not a Channel
        mock_client.get_entity = AsyncMock(return_value=mock_user)
        mock_client_class.return_value = mock_client

        # Create client
        client = TelegramArchiveClient(mock_settings)
        client.client = mock_client

        # Should raise ValueError for non-channel
        with pytest.raises(ValueError, match="is not a channel"):
            await client.get_or_create_archive("test_user")


@pytest.mark.asyncio
async def test_download_media_returns_none_for_no_media(mock_settings, mock_telegram_message):
    """Test download_media returns None when message has no media."""
    with patch("src.core.telegram_client.TelegramClient"), \
         patch("src.core.telegram_client.S3Client"), \
         patch("src.core.telegram_client.create_async_engine"):

        # Create client
        client = TelegramArchiveClient(mock_settings)

        # Download media (message has no media)
        media_file = await client.download_media(mock_telegram_message, 1)

        # Verify None returned
        assert media_file is None


@pytest.mark.asyncio
async def test_download_media_handles_photo(mock_settings, mock_telegram_message, tmp_path):
    """Test downloading photo media."""
    with patch("src.core.telegram_client.TelegramClient") as mock_client_class, \
         patch("src.core.telegram_client.S3Client") as mock_s3_class, \
         patch("src.core.telegram_client.create_async_engine"):

        # Setup mocks
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        mock_s3 = Mock()
        mock_s3.upload_file = Mock(return_value="media/ab/cd/abcd123.jpg")
        mock_s3_class.return_value = mock_s3

        # Mock photo media
        from telethon.tl.types import MessageMediaPhoto

        photo_size = Mock()
        photo_size.w = 1024
        photo_size.h = 768

        photo = Mock()
        photo.sizes = [photo_size]

        media = MessageMediaPhoto()
        media.photo = photo
        mock_telegram_message.media = media

        # Mock download - create a temporary file
        async def mock_download(message, file):
            Path(file).write_bytes(b"fake image data")

        mock_client.download_media = AsyncMock(side_effect=mock_download)

        # Create client
        client = TelegramArchiveClient(mock_settings)
        client.client = mock_client
        client.s3_client = mock_s3

        # Download media
        media_file = await client.download_media(mock_telegram_message, 1)

        # Verify media file was created
        assert media_file is not None
        assert media_file.media_type == "photo"
        assert media_file.storage_key == "media/ab/cd/abcd123.jpg"
        assert media_file.upload_status == "uploaded"
        assert media_file.width == 1024
        assert media_file.height == 768


@pytest.mark.asyncio
async def test_download_media_handles_unsupported_type(mock_settings, mock_telegram_message):
    """Test download_media handles unsupported media types gracefully."""
    with patch("src.core.telegram_client.TelegramClient"), \
         patch("src.core.telegram_client.S3Client"), \
         patch("src.core.telegram_client.create_async_engine"):

        # Mock unsupported media type
        mock_telegram_message.media = Mock()
        mock_telegram_message.media.__class__.__name__ = "MessageMediaUnsupported"

        # Create client
        client = TelegramArchiveClient(mock_settings)

        # Download media
        media_file = await client.download_media(mock_telegram_message, 1)

        # Should return None for unsupported types
        assert media_file is None


@pytest.mark.asyncio
async def test_message_exists_check(mock_settings):
    """Test message_exists performs database query."""
    with patch("src.core.telegram_client.TelegramClient"), \
         patch("src.core.telegram_client.S3Client"), \
         patch("src.core.telegram_client.create_async_engine"):

        # Mock database session
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)  # No message found (sync method)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock the context manager
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        # Create client
        client = TelegramArchiveClient(mock_settings)
        client.async_session = mock_session_maker

        # Check message exists
        exists = await client.message_exists(123, 456)

        # Verify session was used
        assert mock_session.execute.called
        # Should return False since scalar_one_or_none returned None
        assert exists is False


@pytest.mark.asyncio
async def test_authenticate_starts_client(mock_settings):
    """Test authenticate starts Telethon client."""
    with patch("src.core.telegram_client.TelegramClient") as mock_client_class, \
         patch("src.core.telegram_client.S3Client"), \
         patch("src.core.telegram_client.create_async_engine"):

        # Setup mocks
        mock_client = AsyncMock()
        mock_me = Mock()
        mock_me.first_name = "Test"
        mock_me.username = "testuser"
        mock_client.get_me = AsyncMock(return_value=mock_me)
        mock_client.start = AsyncMock()
        mock_client_class.return_value = mock_client

        # Create client
        client = TelegramArchiveClient(mock_settings)
        client.client = mock_client

        # Authenticate
        await client.authenticate()

        # Verify client.start was called
        mock_client.start.assert_called_once()
        mock_client.get_me.assert_called_once()


@pytest.mark.asyncio
async def test_disconnect_closes_connections(mock_settings):
    """Test disconnect closes Telegram and database connections."""
    with patch("src.core.telegram_client.TelegramClient") as mock_client_class, \
         patch("src.core.telegram_client.S3Client"), \
         patch("src.core.telegram_client.create_async_engine") as mock_engine_class:

        # Setup mocks
        mock_client = AsyncMock()
        mock_client.disconnect = AsyncMock()
        mock_client_class.return_value = mock_client

        mock_engine = AsyncMock()
        mock_engine.dispose = AsyncMock()
        mock_engine_class.return_value = mock_engine

        # Create client
        client = TelegramArchiveClient(mock_settings)
        client.client = mock_client
        client.db_engine = mock_engine

        # Disconnect
        await client.disconnect()

        # Verify both were called
        mock_client.disconnect.assert_called_once()
        mock_engine.dispose.assert_called_once()


def test_cli_imports():
    """Test that CLI module can be imported."""
    from src import __main__
    assert __main__.cli is not None
    assert __main__.listen is not None
    assert __main__.import_messages is not None


def test_cli_has_required_commands():
    """Test CLI has the required commands."""
    from src.__main__ import cli

    # Get command names
    command_names = [cmd.name for cmd in cli.commands.values()]

    # Verify required commands exist
    assert "listen" in command_names
    assert "import-messages" in command_names or "import_messages" in command_names
    assert "version" in command_names


def test_session_directory_created():
    """Test that session directory is created during client init."""
    with patch("src.core.telegram_client.TelegramClient"), \
         patch("src.core.telegram_client.S3Client"), \
         patch("src.core.telegram_client.create_async_engine"):

        mock_settings = Mock()
        mock_settings.telegram_api_id = 12345
        mock_settings.telegram_api_hash = "test"
        mock_settings.telegram_phone = "+1234567890"
        mock_settings.telegram_session_name = "test_session"
        mock_settings.minio_endpoint = "localhost:9000"
        mock_settings.minio_access_key = "test"
        mock_settings.minio_secret_key = "test"
        mock_settings.minio_bucket = "test"
        mock_settings.minio_secure = False
        mock_settings.database_url = "postgresql://test:test@localhost:5432/test"

        # Create client (should create data/sessions directory)
        client = TelegramArchiveClient(mock_settings)

        # Verify directory exists
        session_dir = Path("data/sessions")
        assert session_dir.exists()
        assert session_dir.is_dir()
