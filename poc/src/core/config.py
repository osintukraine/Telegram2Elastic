"""Configuration management for OSINT Semantic Archive.

This module provides centralized configuration management using pydantic-settings.
All configuration is loaded from environment variables or .env files with
comprehensive validation.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings are loaded from environment variables or .env files.
    Required fields will raise validation errors if not provided.
    Optional fields have sensible defaults.

    Attributes:
        # Telegram API Configuration (4 fields)
        telegram_api_id: Telegram API ID from https://my.telegram.org
        telegram_api_hash: Telegram API hash from https://my.telegram.org
        telegram_phone: Phone number for Telegram authentication
        telegram_session_name: Session name for Telethon client

        # Together.ai API Configuration (1 field)
        together_api_key: API key for Together.ai LLM service

        # Database Configuration (1 field)
        database_url: PostgreSQL connection URL

        # MinIO/S3 Configuration (5 fields)
        minio_endpoint: MinIO server endpoint (host:port)
        minio_access_key: MinIO access key
        minio_secret_key: MinIO secret key
        minio_bucket: Bucket name for media storage
        minio_secure: Whether to use HTTPS for MinIO connection

        # Redis Configuration (1 field)
        redis_url: Redis connection URL

        # Application Configuration (2 fields)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        environment: Environment name (development, production)

        # API Configuration (3 fields)
        api_host: Host to bind FastAPI server
        api_port: Port for FastAPI server
        api_reload: Enable auto-reload for development

        # Enrichment Configuration (5 fields)
        enable_spam_filter: Enable spam filtering
        enable_llm_classification: Enable LLM-based classification
        enable_entity_extraction: Enable named entity recognition
        enable_geo_extraction: Enable geolocation extraction
        enable_engagement_metrics: Enable engagement metrics calculation

        # LLM Configuration (3 fields)
        llm_model: Model name for Together.ai
        llm_temperature: Temperature for LLM generation (0-1)
        llm_max_tokens: Maximum tokens for LLM responses

        # Spam Filter Thresholds (2 fields)
        spam_confidence_threshold: Confidence threshold for spam detection (0-1)
        min_osint_score: Minimum OSINT score to keep messages (0-100)

        # Processing Configuration (2 fields)
        max_concurrent_enrichments: Max concurrent enrichment tasks
        enrichment_timeout_seconds: Timeout for enrichment operations
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram API Configuration (4 fields)
    telegram_api_id: int = Field(
        ...,
        description="Telegram API ID from https://my.telegram.org",
    )
    telegram_api_hash: str = Field(
        ...,
        description="Telegram API hash from https://my.telegram.org",
    )
    telegram_phone: str = Field(
        ...,
        description="Phone number for Telegram authentication",
    )
    telegram_session_name: str = Field(
        ...,
        description="Session name for Telethon client",
    )

    # Together.ai API Configuration (1 field)
    together_api_key: str = Field(
        ...,
        description="API key for Together.ai LLM service",
    )

    # Database Configuration (1 field)
    database_url: str = Field(
        ...,
        description="PostgreSQL connection URL",
    )

    # MinIO/S3 Configuration (5 fields)
    minio_endpoint: str = Field(
        ...,
        description="MinIO server endpoint (host:port)",
    )
    minio_access_key: str = Field(
        ...,
        description="MinIO access key",
    )
    minio_secret_key: str = Field(
        ...,
        description="MinIO secret key",
    )
    minio_bucket: str = Field(
        ...,
        description="Bucket name for media storage",
    )
    minio_secure: bool = Field(
        ...,
        description="Whether to use HTTPS for MinIO connection",
    )

    # Redis Configuration (1 field)
    redis_url: str = Field(
        ...,
        description="Redis connection URL",
    )

    # Application Configuration (2 fields)
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    environment: str = Field(
        default="development",
        description="Environment name (development, production)",
    )

    # API Configuration (3 fields)
    api_host: str = Field(
        default="0.0.0.0",
        description="Host to bind FastAPI server",
    )
    api_port: int = Field(
        default=8000,
        description="Port for FastAPI server",
    )
    api_reload: bool = Field(
        default=True,
        description="Enable auto-reload for development",
    )

    # Enrichment Configuration (5 fields)
    enable_spam_filter: bool = Field(
        default=True,
        description="Enable spam filtering",
    )
    enable_llm_classification: bool = Field(
        default=True,
        description="Enable LLM-based classification",
    )
    enable_entity_extraction: bool = Field(
        default=True,
        description="Enable named entity recognition",
    )
    enable_geo_extraction: bool = Field(
        default=True,
        description="Enable geolocation extraction",
    )
    enable_engagement_metrics: bool = Field(
        default=True,
        description="Enable engagement metrics calculation",
    )

    # LLM Configuration (3 fields)
    llm_model: str = Field(
        default="meta-llama/Llama-3.1-70B-Instruct-Turbo",
        description="Model name for Together.ai",
    )
    llm_temperature: float = Field(
        default=0.1,
        description="Temperature for LLM generation (0-1)",
        ge=0.0,
        le=1.0,
    )
    llm_max_tokens: int = Field(
        default=500,
        description="Maximum tokens for LLM responses",
        gt=0,
    )

    # Spam Filter Thresholds (2 fields)
    spam_confidence_threshold: float = Field(
        default=0.85,
        description="Confidence threshold for spam detection (0-1)",
        ge=0.0,
        le=1.0,
    )
    min_osint_score: int = Field(
        default=30,
        description="Minimum OSINT score to keep messages (0-100)",
        ge=0,
        le=100,
    )

    # Processing Configuration (2 fields)
    max_concurrent_enrichments: int = Field(
        default=5,
        description="Max concurrent enrichment tasks",
        gt=0,
    )
    enrichment_timeout_seconds: int = Field(
        default=30,
        description="Timeout for enrichment operations",
        gt=0,
    )

    @field_validator("telegram_api_id")
    @classmethod
    def validate_telegram_api_id(cls, v: int) -> int:
        """Validate that telegram_api_id is positive.

        Args:
            v: The telegram_api_id value

        Returns:
            The validated value

        Raises:
            ValueError: If telegram_api_id is not positive
        """
        if v <= 0:
            raise ValueError("telegram_api_id must be greater than 0")
        return v
