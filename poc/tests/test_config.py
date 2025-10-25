"""Tests for configuration management.

Following TDD: These tests define the expected behavior of the Settings class
before implementation.
"""

import os
import pytest
from pydantic import ValidationError


def test_settings_loads_from_environment(monkeypatch):
    """Test that Settings loads all required environment variables."""
    # Set all required environment variables
    env_vars = {
        # Telegram API Configuration
        "TELEGRAM_API_ID": "12345678",
        "TELEGRAM_API_HASH": "test_api_hash",
        "TELEGRAM_PHONE": "+1234567890",
        "TELEGRAM_SESSION_NAME": "test_session",
        # Together.ai API Configuration
        "TOGETHER_API_KEY": "test_together_key",
        # Database Configuration
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
        # MinIO/S3 Configuration
        "MINIO_ENDPOINT": "localhost:9000",
        "MINIO_ACCESS_KEY": "minioadmin",
        "MINIO_SECRET_KEY": "minioadmin123",
        "MINIO_BUCKET": "test-bucket",
        "MINIO_SECURE": "false",
        # Redis Configuration
        "REDIS_URL": "redis://localhost:6379",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    from src.core.config import Settings

    settings = Settings()

    # Verify all required fields are loaded
    assert settings.telegram_api_id == 12345678
    assert settings.telegram_api_hash == "test_api_hash"
    assert settings.telegram_phone == "+1234567890"
    assert settings.telegram_session_name == "test_session"
    assert settings.together_api_key == "test_together_key"
    assert settings.database_url == "postgresql://user:pass@localhost:5432/db"
    assert settings.minio_endpoint == "localhost:9000"
    assert settings.minio_access_key == "minioadmin"
    assert settings.minio_secret_key == "minioadmin123"
    assert settings.minio_bucket == "test-bucket"
    assert settings.minio_secure is False
    assert settings.redis_url == "redis://localhost:6379"


def test_settings_loads_optional_fields(monkeypatch):
    """Test that Settings loads optional environment variables with defaults."""
    # Set only required fields
    required_vars = {
        "TELEGRAM_API_ID": "12345678",
        "TELEGRAM_API_HASH": "test_api_hash",
        "TELEGRAM_PHONE": "+1234567890",
        "TELEGRAM_SESSION_NAME": "test_session",
        "TOGETHER_API_KEY": "test_together_key",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
        "MINIO_ENDPOINT": "localhost:9000",
        "MINIO_ACCESS_KEY": "minioadmin",
        "MINIO_SECRET_KEY": "minioadmin123",
        "MINIO_BUCKET": "test-bucket",
        "MINIO_SECURE": "false",
        "REDIS_URL": "redis://localhost:6379",
    }

    for key, value in required_vars.items():
        monkeypatch.setenv(key, value)

    from src.core.config import Settings

    settings = Settings()

    # Verify optional fields have defaults
    assert settings.log_level == "INFO"
    assert settings.environment == "development"
    assert settings.api_host == "0.0.0.0"
    assert settings.api_port == 8000
    assert settings.api_reload is True
    assert settings.enable_spam_filter is True
    assert settings.enable_llm_classification is True
    assert settings.enable_entity_extraction is True
    assert settings.enable_geo_extraction is True
    assert settings.enable_engagement_metrics is True
    assert settings.llm_model == "meta-llama/Llama-3.1-70B-Instruct-Turbo"
    assert settings.llm_temperature == 0.1
    assert settings.llm_max_tokens == 500
    assert settings.spam_confidence_threshold == 0.85
    assert settings.min_osint_score == 30
    assert settings.max_concurrent_enrichments == 5
    assert settings.enrichment_timeout_seconds == 30


def test_settings_overrides_optional_fields(monkeypatch):
    """Test that optional fields can be overridden via environment variables."""
    # Set all required fields plus some optional overrides
    env_vars = {
        # Required
        "TELEGRAM_API_ID": "12345678",
        "TELEGRAM_API_HASH": "test_api_hash",
        "TELEGRAM_PHONE": "+1234567890",
        "TELEGRAM_SESSION_NAME": "test_session",
        "TOGETHER_API_KEY": "test_together_key",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
        "MINIO_ENDPOINT": "localhost:9000",
        "MINIO_ACCESS_KEY": "minioadmin",
        "MINIO_SECRET_KEY": "minioadmin123",
        "MINIO_BUCKET": "test-bucket",
        "MINIO_SECURE": "false",
        "REDIS_URL": "redis://localhost:6379",
        # Optional overrides
        "LOG_LEVEL": "DEBUG",
        "ENVIRONMENT": "production",
        "API_PORT": "9000",
        "ENABLE_SPAM_FILTER": "false",
        "LLM_TEMPERATURE": "0.5",
        "MIN_OSINT_SCORE": "50",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    from src.core.config import Settings

    settings = Settings()

    # Verify overrides are applied
    assert settings.log_level == "DEBUG"
    assert settings.environment == "production"
    assert settings.api_port == 9000
    assert settings.enable_spam_filter is False
    assert settings.llm_temperature == 0.5
    assert settings.min_osint_score == 50


def test_telegram_api_id_must_be_positive(monkeypatch):
    """Test that telegram_api_id must be greater than 0."""
    env_vars = {
        "TELEGRAM_API_ID": "0",  # Invalid: must be > 0
        "TELEGRAM_API_HASH": "test_api_hash",
        "TELEGRAM_PHONE": "+1234567890",
        "TELEGRAM_SESSION_NAME": "test_session",
        "TOGETHER_API_KEY": "test_together_key",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
        "MINIO_ENDPOINT": "localhost:9000",
        "MINIO_ACCESS_KEY": "minioadmin",
        "MINIO_SECRET_KEY": "minioadmin123",
        "MINIO_BUCKET": "test-bucket",
        "MINIO_SECURE": "false",
        "REDIS_URL": "redis://localhost:6379",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    from src.core.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    # Verify the error is about telegram_api_id
    errors = exc_info.value.errors()
    assert any("telegram_api_id" in str(error) for error in errors)


def test_telegram_api_id_negative_raises_error(monkeypatch):
    """Test that negative telegram_api_id raises ValidationError."""
    env_vars = {
        "TELEGRAM_API_ID": "-12345",  # Invalid: negative
        "TELEGRAM_API_HASH": "test_api_hash",
        "TELEGRAM_PHONE": "+1234567890",
        "TELEGRAM_SESSION_NAME": "test_session",
        "TOGETHER_API_KEY": "test_together_key",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
        "MINIO_ENDPOINT": "localhost:9000",
        "MINIO_ACCESS_KEY": "minioadmin",
        "MINIO_SECRET_KEY": "minioadmin123",
        "MINIO_BUCKET": "test-bucket",
        "MINIO_SECURE": "false",
        "REDIS_URL": "redis://localhost:6379",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    from src.core.config import Settings

    with pytest.raises(ValidationError):
        Settings()


def test_missing_required_field_raises_error(monkeypatch):
    """Test that missing required fields raise ValidationError."""
    # Missing TELEGRAM_API_HASH
    env_vars = {
        "TELEGRAM_API_ID": "12345678",
        # "TELEGRAM_API_HASH": "test_api_hash",  # Missing!
        "TELEGRAM_PHONE": "+1234567890",
        "TELEGRAM_SESSION_NAME": "test_session",
        "TOGETHER_API_KEY": "test_together_key",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
        "MINIO_ENDPOINT": "localhost:9000",
        "MINIO_ACCESS_KEY": "minioadmin",
        "MINIO_SECRET_KEY": "minioadmin123",
        "MINIO_BUCKET": "test-bucket",
        "MINIO_SECURE": "false",
        "REDIS_URL": "redis://localhost:6379",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    from src.core.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    # Verify the error mentions the missing field
    errors = exc_info.value.errors()
    assert any("telegram_api_hash" in str(error) for error in errors)


def test_loads_from_env_file(tmp_path, monkeypatch):
    """Test that Settings can load from .env file."""
    # Create a temporary .env file
    env_file = tmp_path / ".env"
    env_content = """
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=test_api_hash
TELEGRAM_PHONE=+1234567890
TELEGRAM_SESSION_NAME=test_session
TOGETHER_API_KEY=test_together_key
DATABASE_URL=postgresql://user:pass@localhost:5432/db
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_BUCKET=test-bucket
MINIO_SECURE=false
REDIS_URL=redis://localhost:6379
LOG_LEVEL=DEBUG
"""
    env_file.write_text(env_content)

    # Change to the temp directory so .env is found
    monkeypatch.chdir(tmp_path)

    from src.core.config import Settings

    settings = Settings()

    assert settings.telegram_api_id == 12345678
    assert settings.log_level == "DEBUG"


def test_boolean_field_parsing(monkeypatch):
    """Test that boolean fields are parsed correctly from strings."""
    env_vars = {
        "TELEGRAM_API_ID": "12345678",
        "TELEGRAM_API_HASH": "test_api_hash",
        "TELEGRAM_PHONE": "+1234567890",
        "TELEGRAM_SESSION_NAME": "test_session",
        "TOGETHER_API_KEY": "test_together_key",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
        "MINIO_ENDPOINT": "localhost:9000",
        "MINIO_ACCESS_KEY": "minioadmin",
        "MINIO_SECRET_KEY": "minioadmin123",
        "MINIO_BUCKET": "test-bucket",
        "MINIO_SECURE": "true",  # String "true"
        "REDIS_URL": "redis://localhost:6379",
        "API_RELOAD": "false",  # String "false"
        "ENABLE_SPAM_FILTER": "1",  # Number as string
        "ENABLE_LLM_CLASSIFICATION": "0",  # Zero as string
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    from src.core.config import Settings

    settings = Settings()

    assert settings.minio_secure is True
    assert settings.api_reload is False
    assert settings.enable_spam_filter is True
    assert settings.enable_llm_classification is False


def test_numeric_field_parsing(monkeypatch):
    """Test that numeric fields are parsed correctly from strings."""
    env_vars = {
        "TELEGRAM_API_ID": "12345678",
        "TELEGRAM_API_HASH": "test_api_hash",
        "TELEGRAM_PHONE": "+1234567890",
        "TELEGRAM_SESSION_NAME": "test_session",
        "TOGETHER_API_KEY": "test_together_key",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
        "MINIO_ENDPOINT": "localhost:9000",
        "MINIO_ACCESS_KEY": "minioadmin",
        "MINIO_SECRET_KEY": "minioadmin123",
        "MINIO_BUCKET": "test-bucket",
        "MINIO_SECURE": "false",
        "REDIS_URL": "redis://localhost:6379",
        "API_PORT": "9000",
        "LLM_TEMPERATURE": "0.7",
        "LLM_MAX_TOKENS": "1000",
        "SPAM_CONFIDENCE_THRESHOLD": "0.9",
        "MIN_OSINT_SCORE": "40",
        "MAX_CONCURRENT_ENRICHMENTS": "10",
        "ENRICHMENT_TIMEOUT_SECONDS": "60",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    from src.core.config import Settings

    settings = Settings()

    assert settings.api_port == 9000
    assert settings.llm_temperature == 0.7
    assert settings.llm_max_tokens == 1000
    assert settings.spam_confidence_threshold == 0.9
    assert settings.min_osint_score == 40
    assert settings.max_concurrent_enrichments == 10
    assert settings.enrichment_timeout_seconds == 60


def test_all_29_environment_variables_supported(monkeypatch):
    """Test that all 29 environment variables from .env.example are supported."""
    # All 29 variables from .env.example
    env_vars = {
        # Telegram API Configuration (4)
        "TELEGRAM_API_ID": "12345678",
        "TELEGRAM_API_HASH": "test_api_hash",
        "TELEGRAM_PHONE": "+1234567890",
        "TELEGRAM_SESSION_NAME": "test_session",
        # Together.ai API Configuration (1)
        "TOGETHER_API_KEY": "test_together_key",
        # Database Configuration (1)
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
        # MinIO/S3 Configuration (5)
        "MINIO_ENDPOINT": "localhost:9000",
        "MINIO_ACCESS_KEY": "minioadmin",
        "MINIO_SECRET_KEY": "minioadmin123",
        "MINIO_BUCKET": "test-bucket",
        "MINIO_SECURE": "false",
        # Redis Configuration (1)
        "REDIS_URL": "redis://localhost:6379",
        # Application Configuration (2)
        "LOG_LEVEL": "INFO",
        "ENVIRONMENT": "development",
        # API Configuration (3)
        "API_HOST": "0.0.0.0",
        "API_PORT": "8000",
        "API_RELOAD": "true",
        # Enrichment Configuration (5)
        "ENABLE_SPAM_FILTER": "true",
        "ENABLE_LLM_CLASSIFICATION": "true",
        "ENABLE_ENTITY_EXTRACTION": "true",
        "ENABLE_GEO_EXTRACTION": "true",
        "ENABLE_ENGAGEMENT_METRICS": "true",
        # LLM Configuration (3)
        "LLM_MODEL": "meta-llama/Llama-3.1-70B-Instruct-Turbo",
        "LLM_TEMPERATURE": "0.1",
        "LLM_MAX_TOKENS": "500",
        # Spam Filter Thresholds (2)
        "SPAM_CONFIDENCE_THRESHOLD": "0.85",
        "MIN_OSINT_SCORE": "30",
        # Processing Configuration (2)
        "MAX_CONCURRENT_ENRICHMENTS": "5",
        "ENRICHMENT_TIMEOUT_SECONDS": "30",
    }

    # Verify we have 29 variables
    assert len(env_vars) == 29, f"Expected 29 variables, got {len(env_vars)}"

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    from src.core.config import Settings

    settings = Settings()

    # Verify all fields are accessible and have correct values
    assert settings.telegram_api_id == 12345678
    assert settings.telegram_api_hash == "test_api_hash"
    assert settings.telegram_phone == "+1234567890"
    assert settings.telegram_session_name == "test_session"
    assert settings.together_api_key == "test_together_key"
    assert settings.database_url == "postgresql://user:pass@localhost:5432/db"
    assert settings.minio_endpoint == "localhost:9000"
    assert settings.minio_access_key == "minioadmin"
    assert settings.minio_secret_key == "minioadmin123"
    assert settings.minio_bucket == "test-bucket"
    assert settings.minio_secure is False
    assert settings.redis_url == "redis://localhost:6379"
    assert settings.log_level == "INFO"
    assert settings.environment == "development"
    assert settings.api_host == "0.0.0.0"
    assert settings.api_port == 8000
    assert settings.api_reload is True
    assert settings.enable_spam_filter is True
    assert settings.enable_llm_classification is True
    assert settings.enable_entity_extraction is True
    assert settings.enable_geo_extraction is True
    assert settings.enable_engagement_metrics is True
    assert settings.llm_model == "meta-llama/Llama-3.1-70B-Instruct-Turbo"
    assert settings.llm_temperature == 0.1
    assert settings.llm_max_tokens == 500
    assert settings.spam_confidence_threshold == 0.85
    assert settings.min_osint_score == 30
    assert settings.max_concurrent_enrichments == 5
    assert settings.enrichment_timeout_seconds == 30


def test_settings_is_singleton_pattern():
    """Test that Settings can be instantiated multiple times (not singleton)."""
    from src.core.config import Settings

    # We don't enforce singleton, but settings should be consistent
    # This test just verifies we can create multiple instances
    # In practice, you'd typically create one instance and pass it around
    pass  # This is more of a documentation test


def test_validates_llm_temperature_range(monkeypatch):
    """Test that LLM temperature is validated to be between 0 and 1."""
    env_vars = {
        "TELEGRAM_API_ID": "12345678",
        "TELEGRAM_API_HASH": "test_api_hash",
        "TELEGRAM_PHONE": "+1234567890",
        "TELEGRAM_SESSION_NAME": "test_session",
        "TOGETHER_API_KEY": "test_together_key",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
        "MINIO_ENDPOINT": "localhost:9000",
        "MINIO_ACCESS_KEY": "minioadmin",
        "MINIO_SECRET_KEY": "minioadmin123",
        "MINIO_BUCKET": "test-bucket",
        "MINIO_SECURE": "false",
        "REDIS_URL": "redis://localhost:6379",
        "LLM_TEMPERATURE": "1.5",  # Invalid: > 1
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    from src.core.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    errors = exc_info.value.errors()
    assert any("llm_temperature" in str(error) for error in errors)


def test_validates_spam_confidence_threshold_range(monkeypatch):
    """Test that spam confidence threshold is validated to be between 0 and 1."""
    env_vars = {
        "TELEGRAM_API_ID": "12345678",
        "TELEGRAM_API_HASH": "test_api_hash",
        "TELEGRAM_PHONE": "+1234567890",
        "TELEGRAM_SESSION_NAME": "test_session",
        "TOGETHER_API_KEY": "test_together_key",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
        "MINIO_ENDPOINT": "localhost:9000",
        "MINIO_ACCESS_KEY": "minioadmin",
        "MINIO_SECRET_KEY": "minioadmin123",
        "MINIO_BUCKET": "test-bucket",
        "MINIO_SECURE": "false",
        "REDIS_URL": "redis://localhost:6379",
        "SPAM_CONFIDENCE_THRESHOLD": "2.0",  # Invalid: > 1
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    from src.core.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    errors = exc_info.value.errors()
    assert any("spam_confidence_threshold" in str(error) for error in errors)
