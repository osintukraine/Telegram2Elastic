"""CLI entry point for OSINT Semantic Archive.

This module provides command-line interface for the archive listener.

Usage:
    # Listen for new messages (real-time)
    python -m src listen <channel_username>

    # Import historical messages
    python -m src import <channel_username> --limit 100

    # Import all historical messages
    python -m src import <channel_username>

Examples:
    python -m src listen combat_footage
    python -m src import combat_footage --limit 1000
"""

import asyncio
import logging
import sys
from typing import Optional

import click

from src.core.config import Settings
from src.core.telegram_client import TelegramArchiveClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@click.group()
def cli() -> None:
    """OSINT Semantic Archive - Telegram listener with AI enrichment."""
    pass


@cli.command()
@click.argument("channel_username")
def listen(channel_username: str) -> None:
    """Listen for new messages in real-time.

    This command connects to Telegram and listens for new messages
    in the specified channel. It runs indefinitely until interrupted
    with Ctrl+C.

    Args:
        channel_username: Channel username (without @)

    Example:
        python -m src listen combat_footage
    """
    logger.info("Starting OSINT Semantic Archive listener...")
    logger.info(f"Channel: {channel_username}")

    async def run() -> None:
        """Run the listener."""
        try:
            # Load settings
            settings = Settings()

            # Create client
            client = TelegramArchiveClient(settings)

            # Authenticate
            await client.authenticate()

            # Start listening
            await client.listen(channel_username)

        except KeyboardInterrupt:
            logger.info("\nListener stopped by user")
        except Exception as e:
            logger.error(f"Error running listener: {e}", exc_info=True)
            sys.exit(1)
        finally:
            if 'client' in locals():
                await client.disconnect()

    asyncio.run(run())


@cli.command()
@click.argument("channel_username")
@click.option(
    "--limit",
    "-l",
    type=int,
    default=None,
    help="Maximum number of messages to import (default: all)",
)
def import_messages(channel_username: str, limit: Optional[int]) -> None:
    """Import historical messages from a channel.

    This command fetches historical messages from the specified channel
    and stores them in the database. It can import all messages or a
    limited number of recent messages.

    Args:
        channel_username: Channel username (without @)
        limit: Maximum number of messages to import (None = all)

    Examples:
        python -m src import combat_footage --limit 100
        python -m src import combat_footage
    """
    logger.info("Starting message import...")
    logger.info(f"Channel: {channel_username}")
    if limit:
        logger.info(f"Limit: {limit} messages")
    else:
        logger.info("Limit: all messages")

    async def run() -> None:
        """Run the import."""
        try:
            # Load settings
            settings = Settings()

            # Create client
            client = TelegramArchiveClient(settings)

            # Authenticate
            await client.authenticate()

            # Import messages
            imported = await client.import_messages(channel_username, limit=limit)

            logger.info(f"Import complete: {imported} messages imported")

        except KeyboardInterrupt:
            logger.info("\nImport cancelled by user")
        except Exception as e:
            logger.error(f"Error running import: {e}", exc_info=True)
            sys.exit(1)
        finally:
            if 'client' in locals():
                await client.disconnect()

    asyncio.run(run())


@cli.command()
def version() -> None:
    """Show version information."""
    print("OSINT Semantic Archive v0.1.0")
    print("Telegram listener with AI-powered semantic enrichment")


if __name__ == "__main__":
    cli()
