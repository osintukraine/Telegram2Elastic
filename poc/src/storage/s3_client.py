"""S3-compatible storage client for content-addressed media storage.

This module provides an S3Client class that implements content-addressed
storage using SHA-256 hashes for object keys. It works with any S3-compatible
service including MinIO, AWS S3, and others.

Key features:
- Content-addressed storage with SHA-256 based keys
- Automatic bucket creation if it doesn't exist
- MIME type detection for uploaded files
- Support for custom metadata
- Deduplication (same content = same key)
"""

import hashlib
import mimetypes
from pathlib import Path
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError


class S3Client:
    """S3-compatible storage client with content-addressed storage.

    This client uses SHA-256 hashes to generate deterministic object keys,
    enabling automatic deduplication. Files are stored with the key format:
    media/ab/cd/abcdef123...789.ext where 'ab' are the first 2 characters
    of the hash, 'cd' are the next 2 characters, and the full hash is used
    in the filename.

    Attributes:
        bucket_name: Name of the S3 bucket for storage
        _s3: Boto3 S3 client instance
    """

    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        secure: bool = True,
    ) -> None:
        """Initialize S3Client and create bucket if it doesn't exist.

        Args:
            endpoint_url: S3 endpoint URL (e.g., http://localhost:9000 for MinIO)
            access_key: S3 access key ID
            secret_key: S3 secret access key
            bucket_name: Name of bucket to use for storage
            secure: Whether to use HTTPS (default: True)

        Raises:
            Exception: If unable to create or access the bucket
        """
        self.bucket_name = bucket_name

        # Initialize S3 client
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=boto3.session.Config(signature_version="s3v4"),
        )

        # Create bucket if it doesn't exist
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self) -> None:
        """Create bucket if it doesn't exist.

        This method checks if the bucket exists and creates it if necessary.
        It handles the case where the bucket already exists gracefully.

        Raises:
            Exception: If unable to create bucket
        """
        try:
            # Try to access bucket
            self._s3.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")

            if error_code == "404":
                # Bucket doesn't exist, create it
                try:
                    self._s3.create_bucket(Bucket=self.bucket_name)
                except ClientError as create_error:
                    # If error is not "BucketAlreadyOwnedByYou", raise it
                    create_error_code = create_error.response.get("Error", {}).get("Code", "")
                    if create_error_code != "BucketAlreadyOwnedByYou":
                        raise
            else:
                # Other error, re-raise
                raise

    def _generate_key(self, file_path: Path) -> str:
        """Generate content-addressed key from file using SHA-256.

        The key format is: media/ab/cd/abcdef123...789.ext
        where:
        - 'ab' are the first 2 characters of the SHA-256 hash
        - 'cd' are the next 2 characters
        - The full hash is used in the filename
        - The original file extension is preserved

        Args:
            file_path: Path to file

        Returns:
            S3 object key in content-addressed format

        Example:
            For a file with SHA-256 starting with "abcdef..." and extension ".jpg":
            Returns: "media/ab/cd/abcdef123...789.jpg"
        """
        # Calculate SHA-256 hash of file content
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        hash_hex = sha256_hash.hexdigest()

        # Get file extension (preserve it)
        extension = file_path.suffix

        # Build key: media/ab/cd/abcdef123...789.ext
        first_two = hash_hex[:2]
        second_two = hash_hex[2:4]
        filename = f"{hash_hex}{extension}"

        return f"media/{first_two}/{second_two}/{filename}"

    def upload_file(
        self,
        file_path: Path,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Upload file to S3 with content-addressed key.

        This method generates a SHA-256 based key and uploads the file.
        If the file already exists (same content), it will be overwritten
        with the same content, effectively making uploads idempotent.

        Args:
            file_path: Path to file to upload
            metadata: Optional metadata dict to attach to object

        Returns:
            S3 object key where file was uploaded

        Raises:
            FileNotFoundError: If file_path doesn't exist
            Exception: If upload fails
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Generate content-addressed key
        key = self._generate_key(file_path)

        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            mime_type = "application/octet-stream"

        # Prepare upload parameters
        extra_args: Dict[str, Any] = {
            "ContentType": mime_type,
        }

        # Add metadata if provided
        if metadata:
            extra_args["Metadata"] = metadata

        # Upload file
        with open(file_path, "rb") as f:
            self._s3.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=f,
                **extra_args,
            )

        return key

    def download_file(self, key: str, destination: Path) -> None:
        """Download file from S3 to local path.

        This method downloads a file and creates parent directories
        if they don't exist.

        Args:
            key: S3 object key
            destination: Local path where file should be saved

        Raises:
            Exception: If download fails or object doesn't exist
        """
        # Create parent directories if they don't exist
        destination.parent.mkdir(parents=True, exist_ok=True)

        # Download file
        with open(destination, "wb") as f:
            self._s3.download_fileobj(self.bucket_name, key, f)

    def delete_file(self, key: str) -> None:
        """Delete file from S3.

        This method deletes an object. If the object doesn't exist,
        it completes successfully (idempotent).

        Args:
            key: S3 object key to delete
        """
        try:
            self._s3.delete_object(Bucket=self.bucket_name, Key=key)
        except ClientError:
            # Ignore errors (e.g., object doesn't exist)
            # Deletion is idempotent
            pass

    def file_exists(self, key: str) -> bool:
        """Check if file exists in S3.

        Args:
            key: S3 object key to check

        Returns:
            True if file exists, False otherwise
        """
        try:
            self._s3.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404":
                return False
            # Other errors should be raised
            raise
