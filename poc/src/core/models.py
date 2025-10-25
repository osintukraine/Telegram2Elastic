"""
SQLAlchemy models for OSINT Semantic Archive.

This module defines the database schema optimized for OSINT analysis with:
- Semantic enrichment fields (entities, geolocations, topics, sentiment)
- Content-addressed media storage
- Engagement metrics tracking
- Full-text search capabilities
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Archive(Base):
    """
    Represents a Telegram channel being archived.

    An Archive tracks metadata about a monitored Telegram channel including
    channel details, monitoring status, and basic statistics.
    """

    __tablename__ = "archives"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    channel_username: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    channel_title: Mapped[str] = mapped_column(String(500), nullable=False)
    channel_description: Mapped[Optional[str]] = mapped_column(Text)

    # Monitoring status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_message_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_sync_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Statistics
    total_messages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_media_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_high_value_messages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="archive", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Archive(id={self.id}, channel_username={self.channel_username})>"


class Message(Base):
    """
    Represents a Telegram message with semantic enrichment.

    Messages contain the original Telegram data plus AI-powered analysis including:
    - Named entities (persons, locations, organizations, military units)
    - Geolocation coordinates extracted from text
    - Topic classification
    - OSINT value scoring
    - Engagement metrics (views, forwards, reactions)
    - Sentiment analysis
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    archive_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("archives.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Original message content
    text: Mapped[Optional[str]] = mapped_column(Text)
    raw_text: Mapped[Optional[str]] = mapped_column(Text)

    # Message metadata
    has_media: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    media_type: Mapped[Optional[str]] = mapped_column(String(50))
    is_forwarded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    forward_from_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    forward_from_message_id: Mapped[Optional[int]] = mapped_column(BigInteger)

    # AI Classification
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    spam_confidence: Mapped[Optional[float]] = mapped_column(Float)
    osint_value_score: Mapped[Optional[float]] = mapped_column(Float, index=True)

    # Semantic Enrichment (JSONB for flexible schema)
    entities: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, comment="Named entities: {persons: [...], locations: [...], orgs: [...], military_units: [...]}"
    )
    geolocations: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, comment="Extracted coordinates: [{lat: ..., lon: ..., confidence: ..., text: ...}]"
    )
    topics: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String), comment="Topic classifications"
    )
    sentiment: Mapped[Optional[str]] = mapped_column(
        String(50), comment="Sentiment: positive, negative, neutral"
    )

    # Engagement Metrics (from Telepathy)
    views_count: Mapped[Optional[int]] = mapped_column(Integer)
    forwards_count: Mapped[Optional[int]] = mapped_column(Integer)
    replies_count: Mapped[Optional[int]] = mapped_column(Integer)
    reactions_count: Mapped[Optional[int]] = mapped_column(Integer)

    # Engagement Rates (calculated)
    reply_reach_er: Mapped[Optional[float]] = mapped_column(Float, comment="Reply reach engagement rate")
    reply_impressions_er: Mapped[Optional[float]] = mapped_column(Float, comment="Reply impressions engagement rate")
    forwards_reach_er: Mapped[Optional[float]] = mapped_column(Float, comment="Forwards reach engagement rate")
    forwards_impressions_er: Mapped[Optional[float]] = mapped_column(Float, comment="Forwards impressions engagement rate")
    reactions_reach_er: Mapped[Optional[float]] = mapped_column(Float, comment="Reactions reach engagement rate")
    reactions_impressions_er: Mapped[Optional[float]] = mapped_column(Float, comment="Reactions impressions engagement rate")

    # Reaction details (JSONB for 17 emoji types)
    reactions: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, comment="Reaction counts by emoji type"
    )

    # Full enrichment metadata
    enrichment_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, comment="Additional enrichment data, processing timestamps, model versions, etc."
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    archive: Mapped["Archive"] = relationship("Archive", back_populates="messages")
    media_files: Mapped[List["MediaFile"]] = relationship(
        "MediaFile", back_populates="message", cascade="all, delete-orphan"
    )
    extracted_entities: Mapped[List["Entity"]] = relationship(
        "Entity", back_populates="message", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        # Unique constraint for data integrity (message_id is only unique within a channel)
        UniqueConstraint("archive_id", "message_id", name="uq_messages_archive_message"),
        # Compound index for efficient archive queries
        Index("ix_messages_archive_date", "archive_id", "telegram_date"),
        # OSINT filtering index
        Index("ix_messages_osint_filter", "archive_id", "osint_value_score", "is_spam"),
        # GIN indexes for JSONB fields (semantic search)
        Index("ix_messages_entities_gin", "entities", postgresql_using="gin"),
        Index("ix_messages_geolocations_gin", "geolocations", postgresql_using="gin"),
        Index("ix_messages_reactions_gin", "reactions", postgresql_using="gin"),
        Index("ix_messages_enrichment_gin", "enrichment_metadata", postgresql_using="gin"),
        # Full-text search index on text content
        Index("ix_messages_text_search", "text", postgresql_using="gin", postgresql_ops={"text": "gin_trgm_ops"}),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, message_id={self.message_id}, osint_score={self.osint_value_score})>"


class MediaFile(Base):
    """
    Represents media files (photos, videos, documents) with content-addressed storage.

    Files are stored in MinIO with SHA-256 based keys for deduplication.
    The storage_key follows the format: media/ab/cd/abcd... (first 2 chars, next 2 chars, full hash)
    """

    __tablename__ = "media_files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Content addressing
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, comment="S3/MinIO object key"
    )

    # File metadata
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_name: Mapped[Optional[str]] = mapped_column(String(500))

    # Media type details
    media_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="photo, video, document, voice, audio, etc."
    )
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    duration: Mapped[Optional[int]] = mapped_column(Integer, comment="Duration in seconds for video/audio")

    # Storage metadata
    bucket_name: Mapped[str] = mapped_column(String(255), default="osint-media", nullable=False)
    upload_status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False, comment="pending, uploaded, failed"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    message: Mapped["Message"] = relationship("Message", back_populates="media_files")

    def __repr__(self) -> str:
        return f"<MediaFile(id={self.id}, sha256={self.sha256[:8]}..., type={self.media_type})>"


class Entity(Base):
    """
    Represents a deduplicated named entity extracted from messages.

    Entities are extracted using spaCy NER and custom patterns for military units.
    This table allows efficient querying of all messages mentioning a specific entity.
    """

    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Entity identification
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="PERSON, ORG, GPE, LOC, MILITARY_UNIT, etc.", index=True
    )
    entity_text: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    normalized_text: Mapped[str] = mapped_column(
        String(500), nullable=False, index=True, comment="Lowercase, stripped version for matching"
    )

    # Entity metadata
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    context: Mapped[Optional[str]] = mapped_column(
        Text, comment="Surrounding text for context"
    )
    position_start: Mapped[Optional[int]] = mapped_column(Integer)
    position_end: Mapped[Optional[int]] = mapped_column(Integer)

    # Additional data
    entity_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, comment="Additional entity metadata (source, wiki_url, etc.)"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    message: Mapped["Message"] = relationship("Message", back_populates="extracted_entities")

    # Indexes
    __table_args__ = (
        # Compound index for entity search
        Index("ix_entities_type_text", "entity_type", "normalized_text"),
        # GIN index for metadata
        Index("ix_entities_metadata_gin", "entity_metadata", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<Entity(id={self.id}, type={self.entity_type}, text={self.entity_text})>"


class EventCluster(Base):
    """
    Represents a cluster of related messages about the same event.

    This is an optional feature for grouping messages that discuss the same OSINT event
    (e.g., multiple reports about the same military operation or incident).
    """

    __tablename__ = "event_clusters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Cluster metadata
    cluster_name: Mapped[str] = mapped_column(String(500), nullable=False)
    cluster_type: Mapped[Optional[str]] = mapped_column(
        String(100), comment="military_operation, incident, announcement, etc."
    )
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Temporal range
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Cluster statistics
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_osint_score: Mapped[Optional[float]] = mapped_column(Float)

    # Related messages (array of message IDs)
    message_ids: Mapped[List[int]] = mapped_column(
        ARRAY(BigInteger), comment="Array of message IDs in this cluster"
    )

    # Cluster metadata
    keywords: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String), comment="Key terms associated with this cluster"
    )
    locations: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String), comment="Locations mentioned in cluster"
    )
    entities: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, comment="Aggregated entities from cluster messages"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Indexes
    __table_args__ = (
        Index("ix_event_clusters_dates", "start_date", "end_date"),
        Index("ix_event_clusters_entities_gin", "entities", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<EventCluster(id={self.id}, name={self.cluster_name}, messages={self.message_count})>"
