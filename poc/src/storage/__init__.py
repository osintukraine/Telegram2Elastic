"""Storage package for S3-compatible object storage.

This package provides clients for interacting with S3-compatible storage
services like MinIO, with support for content-addressed storage.
"""

from src.storage.s3_client import S3Client

__all__ = ["S3Client"]
