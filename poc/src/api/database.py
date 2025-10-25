"""Database connection and session management for API.

This module provides synchronous database access for the REST API.
For PoC simplicity, we use synchronous SQLAlchemy instead of async.
"""

from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import Settings

# Global instances (lazy-loaded)
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_engine() -> Engine:
    """Get or create the database engine.

    Returns:
        Engine: SQLAlchemy engine instance
    """
    global _engine
    if _engine is None:
        settings = Settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,  # Verify connections before using
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_factory() -> sessionmaker:
    """Get or create the session factory.

    Returns:
        sessionmaker: SQLAlchemy session factory
    """
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Dependency function to get database session.

    This is used with FastAPI's dependency injection to provide
    database sessions to endpoint handlers.

    Yields:
        Session: SQLAlchemy database session

    Example:
        @app.get("/endpoint")
        def my_endpoint(db: Session = Depends(get_db)):
            # Use db session here
            pass
    """
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    """Check if database connection is healthy.

    Returns:
        bool: True if database is accessible, False otherwise
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False
