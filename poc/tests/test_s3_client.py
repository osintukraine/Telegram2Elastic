"""Tests for S3-compatible storage client.

This module tests the S3Client class with real MinIO instance running
in Docker. Tests cover upload, download, delete, deduplication, and
content-addressed storage functionality.
"""

import hashlib
import io
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from src.storage.s3_client import S3Client


@pytest.fixture
def s3_client() -> Generator[S3Client, None, None]:
    """Create S3Client instance for testing with MinIO.

    This fixture creates a client connected to the local MinIO instance
    running in Docker (localhost:9000).

    Yields:
        S3Client instance configured for MinIO
    """
    client = S3Client(
        endpoint_url="http://localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin123",
        bucket_name="osint-media",
        secure=False,
    )
    yield client


@pytest.fixture
def test_file() -> Generator[Path, None, None]:
    """Create a temporary test file with known content.

    Creates a temporary file with specific content that can be used
    for upload/download testing.

    Yields:
        Path to temporary test file
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("This is a test file for S3Client testing.\n")
        f.write("It contains multiple lines.\n")
        f.write("SHA-256: This will be used for content-addressed storage.\n")
        test_path = Path(f.name)

    yield test_path

    # Cleanup
    if test_path.exists():
        test_path.unlink()


@pytest.fixture
def test_image_file() -> Generator[Path, None, None]:
    """Create a temporary test image file (PNG).

    Creates a simple 1x1 pixel PNG file for MIME type testing.

    Yields:
        Path to temporary PNG file
    """
    # Minimal 1x1 transparent PNG
    png_data = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(png_data)
        test_path = Path(f.name)

    yield test_path

    # Cleanup
    if test_path.exists():
        test_path.unlink()


class TestS3ClientInitialization:
    """Test S3Client initialization and bucket creation."""

    def test_client_initialization(self, s3_client: S3Client) -> None:
        """Test that S3Client initializes correctly.

        Args:
            s3_client: S3Client fixture
        """
        assert s3_client is not None
        assert s3_client.bucket_name == "osint-media"

    def test_bucket_creation(self, s3_client: S3Client) -> None:
        """Test that bucket is created automatically if it doesn't exist.

        Args:
            s3_client: S3Client fixture
        """
        # The bucket should be created during client initialization
        # We can verify this by checking if we can list objects
        # (this would fail if bucket didn't exist)
        try:
            # This should not raise an error
            s3_client._s3.list_objects_v2(
                Bucket=s3_client.bucket_name,
                MaxKeys=1
            )
        except Exception as e:
            pytest.fail(f"Bucket not created or not accessible: {e}")


class TestContentAddressedStorage:
    """Test content-addressed storage with SHA-256 based keys."""

    def test_generate_key_from_file(self, s3_client: S3Client, test_file: Path) -> None:
        """Test that key generation creates correct SHA-256 based path.

        The key format should be: media/ab/cd/abcdef123...789.ext
        where 'ab' are the first 2 chars, 'cd' are the next 2 chars,
        and the full SHA-256 hash is used in the filename.

        Args:
            s3_client: S3Client fixture
            test_file: Temporary test file
        """
        # Calculate expected SHA-256
        with open(test_file, "rb") as f:
            content = f.read()
            expected_sha256 = hashlib.sha256(content).hexdigest()

        # Generate key
        key = s3_client._generate_key(test_file)

        # Verify key format: media/ab/cd/abcdef123...789.txt
        parts = key.split("/")
        assert len(parts) == 4, f"Expected 4 parts in key, got {len(parts)}: {key}"
        assert parts[0] == "media", f"Expected 'media' prefix, got: {parts[0]}"
        assert len(parts[1]) == 2, f"Expected 2 chars for first dir, got: {parts[1]}"
        assert len(parts[2]) == 2, f"Expected 2 chars for second dir, got: {parts[2]}"

        # Verify the directories match the hash
        assert parts[1] == expected_sha256[:2]
        assert parts[2] == expected_sha256[2:4]

        # Verify the filename contains the full hash
        filename = parts[3]
        assert expected_sha256 in filename
        assert filename.endswith(".txt")

    def test_generate_key_preserves_extension(
        self, s3_client: S3Client, test_image_file: Path
    ) -> None:
        """Test that file extension is preserved in generated key.

        Args:
            s3_client: S3Client fixture
            test_image_file: Temporary PNG file
        """
        key = s3_client._generate_key(test_image_file)
        assert key.endswith(".png"), f"Expected .png extension, got: {key}"

    def test_generate_key_deterministic(self, s3_client: S3Client, test_file: Path) -> None:
        """Test that same file generates same key (deterministic).

        Args:
            s3_client: S3Client fixture
            test_file: Temporary test file
        """
        key1 = s3_client._generate_key(test_file)
        key2 = s3_client._generate_key(test_file)
        assert key1 == key2, "Same file should generate same key"


class TestFileUpload:
    """Test file upload functionality."""

    def test_upload_file_success(self, s3_client: S3Client, test_file: Path) -> None:
        """Test successful file upload.

        Args:
            s3_client: S3Client fixture
            test_file: Temporary test file
        """
        # Upload file
        key = s3_client.upload_file(test_file)

        # Verify key format
        assert key.startswith("media/")
        assert "/" in key

        # Verify file exists in S3
        assert s3_client.file_exists(key), f"File not found in S3: {key}"

        # Cleanup
        s3_client.delete_file(key)

    def test_upload_file_returns_key(self, s3_client: S3Client, test_file: Path) -> None:
        """Test that upload_file returns the S3 key.

        Args:
            s3_client: S3Client fixture
            test_file: Temporary test file
        """
        key = s3_client.upload_file(test_file)
        assert isinstance(key, str)
        assert len(key) > 0

        # Cleanup
        s3_client.delete_file(key)

    def test_upload_file_detects_mime_type(
        self, s3_client: S3Client, test_image_file: Path
    ) -> None:
        """Test that MIME type is detected automatically.

        Args:
            s3_client: S3Client fixture
            test_image_file: Temporary PNG file
        """
        key = s3_client.upload_file(test_image_file)

        # Get object metadata
        response = s3_client._s3.head_object(
            Bucket=s3_client.bucket_name,
            Key=key
        )

        # Verify Content-Type
        content_type = response.get("ContentType", "")
        assert content_type == "image/png", f"Expected image/png, got: {content_type}"

        # Cleanup
        s3_client.delete_file(key)

    def test_upload_file_with_custom_metadata(
        self, s3_client: S3Client, test_file: Path
    ) -> None:
        """Test upload with custom metadata.

        Args:
            s3_client: S3Client fixture
            test_file: Temporary test file
        """
        metadata = {
            "source": "telegram",
            "channel": "test_channel",
            "message_id": "12345"
        }

        key = s3_client.upload_file(test_file, metadata=metadata)

        # Get object metadata
        response = s3_client._s3.head_object(
            Bucket=s3_client.bucket_name,
            Key=key
        )

        # Verify metadata (S3 lowercases metadata keys and adds x-amz-meta- prefix)
        obj_metadata = response.get("Metadata", {})
        assert obj_metadata.get("source") == "telegram"
        assert obj_metadata.get("channel") == "test_channel"
        assert obj_metadata.get("message_id") == "12345"

        # Cleanup
        s3_client.delete_file(key)


class TestFileDownload:
    """Test file download functionality."""

    def test_download_file_success(self, s3_client: S3Client, test_file: Path) -> None:
        """Test successful file download.

        Args:
            s3_client: S3Client fixture
            test_file: Temporary test file
        """
        # Upload file first
        key = s3_client.upload_file(test_file)

        # Download to temporary location
        with tempfile.NamedTemporaryFile(delete=False) as f:
            download_path = Path(f.name)

        try:
            s3_client.download_file(key, download_path)

            # Verify file was downloaded
            assert download_path.exists()

            # Verify content matches
            with open(test_file, "rb") as f1, open(download_path, "rb") as f2:
                assert f1.read() == f2.read()

        finally:
            # Cleanup
            if download_path.exists():
                download_path.unlink()
            s3_client.delete_file(key)

    def test_download_file_creates_directory(
        self, s3_client: S3Client, test_file: Path
    ) -> None:
        """Test that download creates parent directories if needed.

        Args:
            s3_client: S3Client fixture
            test_file: Temporary test file
        """
        # Upload file first
        key = s3_client.upload_file(test_file)

        # Download to path with non-existent directories
        with tempfile.TemporaryDirectory() as tmpdir:
            download_path = Path(tmpdir) / "subdir" / "nested" / "file.txt"

            s3_client.download_file(key, download_path)

            # Verify file was downloaded
            assert download_path.exists()

        # Cleanup
        s3_client.delete_file(key)

    def test_download_nonexistent_file_raises_error(
        self, s3_client: S3Client
    ) -> None:
        """Test that downloading non-existent file raises error.

        Args:
            s3_client: S3Client fixture
        """
        with tempfile.NamedTemporaryFile(delete=False) as f:
            download_path = Path(f.name)

        try:
            with pytest.raises(Exception):
                s3_client.download_file("media/00/00/nonexistent.txt", download_path)
        finally:
            if download_path.exists():
                download_path.unlink()


class TestFileDelete:
    """Test file deletion functionality."""

    def test_delete_file_success(self, s3_client: S3Client, test_file: Path) -> None:
        """Test successful file deletion.

        Args:
            s3_client: S3Client fixture
            test_file: Temporary test file
        """
        # Upload file first
        key = s3_client.upload_file(test_file)
        assert s3_client.file_exists(key)

        # Delete file
        s3_client.delete_file(key)

        # Verify file no longer exists
        assert not s3_client.file_exists(key)

    def test_delete_nonexistent_file_no_error(self, s3_client: S3Client) -> None:
        """Test that deleting non-existent file doesn't raise error.

        Args:
            s3_client: S3Client fixture
        """
        # Should not raise error
        s3_client.delete_file("media/00/00/nonexistent.txt")


class TestFileExists:
    """Test file existence checking."""

    def test_file_exists_returns_true(self, s3_client: S3Client, test_file: Path) -> None:
        """Test file_exists returns True for existing file.

        Args:
            s3_client: S3Client fixture
            test_file: Temporary test file
        """
        # Upload file
        key = s3_client.upload_file(test_file)

        try:
            # Check existence
            assert s3_client.file_exists(key) is True
        finally:
            # Cleanup
            s3_client.delete_file(key)

    def test_file_exists_returns_false(self, s3_client: S3Client) -> None:
        """Test file_exists returns False for non-existent file.

        Args:
            s3_client: S3Client fixture
        """
        assert s3_client.file_exists("media/00/00/nonexistent.txt") is False


class TestDeduplication:
    """Test file deduplication functionality."""

    def test_same_file_uploaded_twice_same_key(
        self, s3_client: S3Client, test_file: Path
    ) -> None:
        """Test that uploading the same file twice results in same key.

        This verifies content-addressed storage deduplication.

        Args:
            s3_client: S3Client fixture
            test_file: Temporary test file
        """
        # Upload file twice
        key1 = s3_client.upload_file(test_file)
        key2 = s3_client.upload_file(test_file)

        try:
            # Should have same key (content-addressed)
            assert key1 == key2, "Same file should generate same key"

            # File should exist only once
            assert s3_client.file_exists(key1)
        finally:
            # Cleanup (only need to delete once)
            s3_client.delete_file(key1)

    def test_different_files_different_keys(
        self, s3_client: S3Client, test_file: Path, test_image_file: Path
    ) -> None:
        """Test that different files get different keys.

        Args:
            s3_client: S3Client fixture
            test_file: Temporary test file
            test_image_file: Temporary PNG file
        """
        # Upload different files
        key1 = s3_client.upload_file(test_file)
        key2 = s3_client.upload_file(test_image_file)

        try:
            # Should have different keys
            assert key1 != key2, "Different files should have different keys"

            # Both should exist
            assert s3_client.file_exists(key1)
            assert s3_client.file_exists(key2)
        finally:
            # Cleanup
            s3_client.delete_file(key1)
            s3_client.delete_file(key2)

    def test_identical_content_different_names_same_key(
        self, s3_client: S3Client
    ) -> None:
        """Test that files with same content but different names get same key.

        Args:
            s3_client: S3Client fixture
        """
        # Create two files with same content but different names
        content = b"Identical content for deduplication test"

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f1:
            f1.write(content)
            file1 = Path(f1.name)

        with tempfile.NamedTemporaryFile(suffix=".dat", delete=False) as f2:
            f2.write(content)
            file2 = Path(f2.name)

        try:
            # Upload both files
            key1 = s3_client.upload_file(file1)
            key2 = s3_client.upload_file(file2)

            # Keys should be the same (content-addressed)
            # Note: Extensions might differ, so compare the hash part
            assert key1.split("/")[-1].split(".")[0] == key2.split("/")[-1].split(".")[0]

        finally:
            # Cleanup
            file1.unlink()
            file2.unlink()
            s3_client.delete_file(key1)
            if key1 != key2:
                s3_client.delete_file(key2)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_upload_empty_file(self, s3_client: S3Client) -> None:
        """Test uploading an empty file.

        Args:
            s3_client: S3Client fixture
        """
        # Create empty file
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            empty_file = Path(f.name)

        try:
            # Upload empty file
            key = s3_client.upload_file(empty_file)

            # Should succeed
            assert s3_client.file_exists(key)

            # Cleanup
            s3_client.delete_file(key)
        finally:
            empty_file.unlink()

    def test_upload_large_file(self, s3_client: S3Client) -> None:
        """Test uploading a larger file (multipart upload if needed).

        Args:
            s3_client: S3Client fixture
        """
        # Create a 10MB file
        size = 10 * 1024 * 1024  # 10MB
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            # Write random-ish data
            for _ in range(size // 1024):
                f.write(b"x" * 1024)
            large_file = Path(f.name)

        try:
            # Upload large file
            key = s3_client.upload_file(large_file)

            # Should succeed
            assert s3_client.file_exists(key)

            # Cleanup
            s3_client.delete_file(key)
        finally:
            large_file.unlink()

    def test_upload_file_without_extension(self, s3_client: S3Client) -> None:
        """Test uploading a file without extension.

        Args:
            s3_client: S3Client fixture
        """
        # Create file without extension
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"File without extension")
            no_ext_file = Path(f.name)

        # Remove extension by renaming
        no_ext_path = no_ext_file.parent / "testfile"
        no_ext_file.rename(no_ext_path)

        try:
            # Upload file
            key = s3_client.upload_file(no_ext_path)

            # Should succeed (might not have extension in key)
            assert s3_client.file_exists(key)

            # Cleanup
            s3_client.delete_file(key)
        finally:
            if no_ext_path.exists():
                no_ext_path.unlink()
