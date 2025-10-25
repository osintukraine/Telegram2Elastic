"""Telegram client for archiving messages with semantic enrichment.

This module provides TelegramArchiveClient for connecting to Telegram,
listening for new messages, and importing historical messages. It integrates
with S3 storage and PostgreSQL database to archive messages with media.

Key features:
- Session-based authentication with Telethon
- Real-time message listening
- Historical message import
- Media download and upload to S3
- Message deduplication
- Sender and forward info extraction
"""

import asyncio
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from telethon import TelegramClient, events
from telethon.tl.types import (
    Message as TelegramMessage,
    MessageMediaPhoto,
    MessageMediaDocument,
    PeerChannel,
    User,
    Channel,
)

from src.core.config import Settings
from src.core.models import Archive, Message, MediaFile
from src.storage.s3_client import S3Client

logger = logging.getLogger(__name__)


class TelegramArchiveClient:
    """Telegram client for archiving messages with media.

    This client uses Telethon to connect to Telegram and archive messages
    from specified channels. It supports both real-time listening and
    historical import modes.

    Attributes:
        settings: Application settings
        s3_client: S3 client for media storage
        client: Telethon client instance
        db_engine: SQLAlchemy async engine
        async_session: SQLAlchemy session maker
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize Telegram archive client.

        Args:
            settings: Application settings
        """
        self.settings = settings

        # Initialize S3 client for media storage
        endpoint_url = f"{'https' if settings.minio_secure else 'http'}://{settings.minio_endpoint}"
        self.s3_client = S3Client(
            endpoint_url=endpoint_url,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket_name=settings.minio_bucket,
            secure=settings.minio_secure,
        )

        # Initialize Telethon client
        # Session file will be stored in data/sessions/ directory
        session_dir = Path("data/sessions")
        session_dir.mkdir(parents=True, exist_ok=True)
        session_path = session_dir / settings.telegram_session_name

        self.client = TelegramClient(
            str(session_path),
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )

        # Initialize database connection
        # Convert postgres:// to postgresql+asyncpg:// for async
        db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql+asyncpg://")

        self.db_engine = create_async_engine(db_url, echo=False)
        self.async_session = sessionmaker(
            self.db_engine, class_=AsyncSession, expire_on_commit=False
        )

    async def authenticate(self) -> None:
        """Authenticate with Telegram.

        This method starts the Telethon client and handles authentication.
        If the session file exists, it will reuse it. Otherwise, it will
        prompt for phone code and password (if 2FA is enabled).

        Raises:
            Exception: If authentication fails
        """
        logger.info("Authenticating with Telegram...")

        await self.client.start(phone=self.settings.telegram_phone)

        # Verify we're connected
        me = await self.client.get_me()
        logger.info(f"Authenticated as {me.first_name} (@{me.username})")

    async def get_or_create_archive(self, channel_username: str) -> Archive:
        """Get or create archive for a channel.

        Args:
            channel_username: Channel username (without @)

        Returns:
            Archive instance

        Raises:
            ValueError: If channel not found
        """
        # Get channel entity from Telegram
        try:
            entity = await self.client.get_entity(channel_username)
        except Exception as e:
            raise ValueError(f"Channel not found: {channel_username}") from e

        if not isinstance(entity, Channel):
            raise ValueError(f"{channel_username} is not a channel")

        # Get or create archive in database
        async with self.async_session() as session:
            # Check if archive exists
            stmt = select(Archive).where(Archive.channel_id == entity.id)
            result = await session.execute(stmt)
            archive = result.scalar_one_or_none()

            if archive is None:
                # Create new archive
                archive = Archive(
                    channel_id=entity.id,
                    channel_username=entity.username,
                    channel_title=entity.title,
                    channel_description=getattr(entity, "about", None),
                )
                session.add(archive)
                await session.commit()
                await session.refresh(archive)
                logger.info(f"Created new archive for {entity.title} (ID: {entity.id})")
            else:
                logger.info(f"Using existing archive for {entity.title} (ID: {entity.id})")

            return archive

    async def message_exists(self, archive_id: int, message_id: int) -> bool:
        """Check if message already exists in database.

        Args:
            archive_id: Archive ID
            message_id: Telegram message ID

        Returns:
            True if message exists, False otherwise
        """
        async with self.async_session() as session:
            stmt = select(Message).where(
                Message.archive_id == archive_id,
                Message.message_id == message_id,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def download_media(
        self, telegram_message: TelegramMessage, message_id: int
    ) -> Optional[MediaFile]:
        """Download media from message and upload to S3.

        Args:
            telegram_message: Telethon message object
            message_id: Database message ID

        Returns:
            MediaFile instance if media was downloaded, None otherwise
        """
        if not telegram_message.media:
            return None

        # Determine media type
        media_type = None
        if isinstance(telegram_message.media, MessageMediaPhoto):
            media_type = "photo"
        elif isinstance(telegram_message.media, MessageMediaDocument):
            doc = telegram_message.media.document
            mime_type = doc.mime_type
            if mime_type.startswith("video/"):
                media_type = "video"
            elif mime_type.startswith("audio/"):
                media_type = "audio"
            elif mime_type.startswith("image/"):
                media_type = "image"
            else:
                media_type = "document"
        else:
            # Unsupported media type
            logger.warning(f"Unsupported media type: {type(telegram_message.media)}")
            return None

        try:
            # Download to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{telegram_message.id}") as tmp_file:
                tmp_path = Path(tmp_file.name)

            # Download media
            await self.client.download_media(telegram_message, file=str(tmp_path))

            # Upload to S3 (generates SHA-256 based key)
            storage_key = self.s3_client.upload_file(tmp_path)

            # Calculate SHA-256 for MediaFile record
            import hashlib
            sha256_hash = hashlib.sha256()
            with open(tmp_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256_hash.update(chunk)
            sha256 = sha256_hash.hexdigest()

            # Get file metadata
            file_size = tmp_path.stat().st_size

            # Get MIME type
            import mimetypes
            mime_type, _ = mimetypes.guess_type(str(tmp_path))
            if mime_type is None:
                mime_type = "application/octet-stream"

            # Get dimensions for photos/videos
            width = None
            height = None
            duration = None

            if isinstance(telegram_message.media, MessageMediaPhoto):
                # Get largest photo size
                photo = telegram_message.media.photo
                if photo.sizes:
                    largest = max(photo.sizes, key=lambda s: s.w * s.h if hasattr(s, 'w') else 0)
                    if hasattr(largest, 'w'):
                        width = largest.w
                        height = largest.h
            elif isinstance(telegram_message.media, MessageMediaDocument):
                doc = telegram_message.media.document
                for attr in doc.attributes:
                    if hasattr(attr, 'w') and hasattr(attr, 'h'):
                        width = attr.w
                        height = attr.h
                    if hasattr(attr, 'duration'):
                        duration = attr.duration

            # Create MediaFile record
            media_file = MediaFile(
                message_id=message_id,
                sha256=sha256,
                storage_key=storage_key,
                mime_type=mime_type,
                file_size=file_size,
                media_type=media_type,
                width=width,
                height=height,
                duration=duration,
                bucket_name=self.settings.minio_bucket,
                upload_status="uploaded",
            )

            # Clean up temporary file
            tmp_path.unlink()

            logger.info(f"Downloaded and uploaded media: {media_type}, size={file_size}, key={storage_key}")
            return media_file

        except Exception as e:
            logger.error(f"Failed to download media: {e}", exc_info=True)
            # Clean up temporary file if it exists
            if tmp_path.exists():
                tmp_path.unlink()
            return None

    async def process_message(
        self, telegram_message: TelegramMessage, archive: Archive
    ) -> Optional[Message]:
        """Process a Telegram message and store in database.

        Args:
            telegram_message: Telethon message object
            archive: Archive instance

        Returns:
            Message instance if processed, None if skipped (duplicate)
        """
        # Check for duplicates
        if await self.message_exists(archive.id, telegram_message.id):
            logger.debug(f"Message {telegram_message.id} already exists, skipping")
            return None

        # Extract message text
        text = telegram_message.message or ""
        raw_text = telegram_message.raw_text or ""

        # Check if message has media
        has_media = telegram_message.media is not None

        # Check if message is forwarded
        is_forwarded = telegram_message.forward is not None
        forward_from_channel_id = None
        forward_from_message_id = None

        if is_forwarded and telegram_message.forward:
            fwd = telegram_message.forward
            if hasattr(fwd, 'from_id') and isinstance(fwd.from_id, PeerChannel):
                forward_from_channel_id = fwd.from_id.channel_id
            if hasattr(fwd, 'channel_post'):
                forward_from_message_id = fwd.channel_post

        # Get engagement metrics
        views_count = getattr(telegram_message, 'views', None)
        forwards_count = getattr(telegram_message, 'forwards', None)
        replies_count = None
        reactions_count = None

        # Get reactions if available
        reactions_data = None
        if hasattr(telegram_message, 'reactions') and telegram_message.reactions:
            reactions_count = telegram_message.reactions.results
            # Extract reaction details (17 emoji types from Telepathy)
            reactions_data = {}
            for result in telegram_message.reactions.results:
                # reaction is an emoji or emoticon
                emoji = str(result.reaction)
                count = result.count
                reactions_data[emoji] = count
                if reactions_count is None:
                    reactions_count = count
                else:
                    reactions_count += count

        # Create Message record
        async with self.async_session() as session:
            message = Message(
                archive_id=archive.id,
                message_id=telegram_message.id,
                telegram_date=telegram_message.date,
                text=text,
                raw_text=raw_text,
                has_media=has_media,
                media_type=None,  # Will be set if media is downloaded
                is_forwarded=is_forwarded,
                forward_from_channel_id=forward_from_channel_id,
                forward_from_message_id=forward_from_message_id,
                # Engagement metrics
                views_count=views_count,
                forwards_count=forwards_count,
                replies_count=replies_count,
                reactions_count=reactions_count,
                reactions=reactions_data,
                # These will be filled by enrichment pipeline later
                is_spam=False,
                spam_confidence=None,
                osint_value_score=None,
                entities=None,
                geolocations=None,
                topics=None,
                sentiment=None,
            )

            session.add(message)
            await session.commit()
            await session.refresh(message)

            # Download and upload media if present
            if has_media:
                media_file = await self.download_media(telegram_message, message.id)
                if media_file:
                    message.media_type = media_file.media_type
                    session.add(media_file)
                    await session.commit()

            # Update archive statistics
            archive.total_messages += 1
            if has_media:
                archive.total_media_files += 1
            archive.last_message_date = telegram_message.date
            await session.commit()

            logger.info(
                f"Processed message {telegram_message.id} from {archive.channel_title} "
                f"(has_media={has_media}, is_forwarded={is_forwarded})"
            )

            return message

    async def listen(self, channel_username: str) -> None:
        """Listen for new messages in real-time.

        This method connects to Telegram and listens for new messages
        in the specified channel. It runs indefinitely until interrupted.

        Args:
            channel_username: Channel username (without @)
        """
        # Get or create archive
        archive = await self.get_or_create_archive(channel_username)

        # Get channel entity
        entity = await self.client.get_entity(channel_username)

        logger.info(f"Listening for new messages in {archive.channel_title}...")
        logger.info("Press Ctrl+C to stop")

        # Register event handler for new messages
        @self.client.on(events.NewMessage(chats=entity))
        async def handler(event: events.NewMessage.Event) -> None:
            """Handle new message event."""
            try:
                await self.process_message(event.message, archive)
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)

        # Run until interrupted
        await self.client.run_until_disconnected()

    async def import_messages(
        self, channel_username: str, limit: Optional[int] = None
    ) -> int:
        """Import historical messages from a channel.

        Args:
            channel_username: Channel username (without @)
            limit: Maximum number of messages to import (None = all)

        Returns:
            Number of messages imported
        """
        # Get or create archive
        archive = await self.get_or_create_archive(channel_username)

        # Get channel entity
        entity = await self.client.get_entity(channel_username)

        logger.info(f"Importing messages from {archive.channel_title}...")
        if limit:
            logger.info(f"Limit: {limit} messages")
        else:
            logger.info("Limit: all messages")

        # Import messages
        imported_count = 0
        async for telegram_message in self.client.iter_messages(entity, limit=limit):
            try:
                message = await self.process_message(telegram_message, archive)
                if message:
                    imported_count += 1
                    if imported_count % 10 == 0:
                        logger.info(f"Imported {imported_count} messages...")
            except Exception as e:
                logger.error(f"Error importing message {telegram_message.id}: {e}", exc_info=True)

        logger.info(f"Import complete: {imported_count} new messages imported")
        return imported_count

    async def disconnect(self) -> None:
        """Disconnect from Telegram and close database connections."""
        await self.client.disconnect()
        await self.db_engine.dispose()
        logger.info("Disconnected from Telegram")
