#!/usr/bin/env python3
"""Create Telegram session file for authentication.

This script helps create a Telegram session file using Telethon.
Session files are tied to your IP address due to Telegram's security.

The session file will be stored in data/sessions/ directory and can be
reused for subsequent connections without re-authentication.

Usage:
    python scripts/create_session.py

Environment Variables:
    TELEGRAM_API_ID: Telegram API ID from https://my.telegram.org
    TELEGRAM_API_HASH: Telegram API hash from https://my.telegram.org
    TELEGRAM_PHONE: Phone number for authentication (with country code)
    TELEGRAM_SESSION_NAME: Session file name (without .session extension)

Example .env:
    TELEGRAM_API_ID=12345678
    TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
    TELEGRAM_PHONE=+1234567890
    TELEGRAM_SESSION_NAME=osint_archive
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from telethon import TelegramClient

from src.core.config import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def create_session() -> None:
    """Create Telegram session file with interactive authentication."""
    try:
        # Load settings
        settings = Settings()

        # Create session directory
        session_dir = Path("data/sessions")
        session_dir.mkdir(parents=True, exist_ok=True)
        session_path = session_dir / settings.telegram_session_name

        logger.info("Creating Telegram session...")
        logger.info(f"Session will be saved to: {session_path}.session")
        logger.info(f"Phone number: {settings.telegram_phone}")
        logger.info("")

        # Create Telethon client
        client = TelegramClient(
            str(session_path),
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )

        # Start client (will prompt for code and password if needed)
        await client.start(phone=settings.telegram_phone)

        # Get user info to verify authentication
        me = await client.get_me()

        logger.info("")
        logger.info("=" * 70)
        logger.info("Session created successfully!")
        logger.info("=" * 70)
        logger.info(f"Authenticated as: {me.first_name} {me.last_name or ''}")
        logger.info(f"Username: @{me.username}")
        logger.info(f"Phone: {me.phone}")
        logger.info(f"Session file: {session_path}.session")
        logger.info("")
        logger.info("You can now use this session to run the archive listener:")
        logger.info("  python -m src listen <channel_username>")
        logger.info("  python -m src import <channel_username> --limit 100")
        logger.info("=" * 70)

        # Disconnect
        await client.disconnect()

    except KeyboardInterrupt:
        logger.info("\nAuthentication cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to create session: {e}", exc_info=True)
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                  Telegram Session Creator                            ║
║                  OSINT Semantic Archive                              ║
╚══════════════════════════════════════════════════════════════════════╝

This script will help you create a Telegram session file for archiving.
You will need:
  1. API credentials from https://my.telegram.org
  2. Access to your phone for SMS code
  3. Your 2FA password (if enabled)

Session files are tied to your IP address. If your IP changes, you may
need to re-authenticate.
""")

    try:
        # Load settings to validate before starting
        Settings()
    except Exception as e:
        logger.error("Configuration error. Please check your .env file:")
        logger.error(str(e))
        logger.error("")
        logger.error("Required environment variables:")
        logger.error("  TELEGRAM_API_ID")
        logger.error("  TELEGRAM_API_HASH")
        logger.error("  TELEGRAM_PHONE")
        logger.error("  TELEGRAM_SESSION_NAME")
        sys.exit(1)

    # Run async function
    asyncio.run(create_session())


if __name__ == "__main__":
    main()
