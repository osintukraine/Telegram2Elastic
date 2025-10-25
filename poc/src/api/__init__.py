"""FastAPI REST API for OSINT Semantic Archive.

This package provides a RESTful API for searching and accessing
archived Telegram messages with semantic enrichment.
"""

from .main import app

__all__ = ["app"]
