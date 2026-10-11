import os
from pathlib import Path
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config.settings import settings
from app.database.base import Base

# Ensure parent directory exists for SQLite database file
db_path = Path(settings.DATABASE_PATH)
db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Generator for database sessions suitable for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_db_context():
    """Context manager for database sessions in services/standalone logic."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def init_db():
    """Initialize database tables automatically on startup and apply lightweight column migrations."""
    # Import models to ensure they are registered on Base.metadata
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Lightweight column migration for evolved columns in SQLite
    with engine.connect() as conn:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        if "incidents" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("incidents")]
            if "radius_m" not in columns:
                conn.execute(text("ALTER TABLE incidents ADD COLUMN radius_m FLOAT DEFAULT 500.0"))
            if "first_seen" not in columns:
                conn.execute(text("ALTER TABLE incidents ADD COLUMN first_seen VARCHAR(50)"))
            if "last_seen" not in columns:
                conn.execute(text("ALTER TABLE incidents ADD COLUMN last_seen VARCHAR(50)"))
            if "evidence_references" not in columns:
                conn.execute(text("ALTER TABLE incidents ADD COLUMN evidence_references JSON DEFAULT '[]'"))
            conn.commit()
        if "monitored_routes" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("monitored_routes")]
            if "replacement_attempts" not in columns:
                conn.execute(text("ALTER TABLE monitored_routes ADD COLUMN replacement_attempts JSON DEFAULT '[]'"))
            conn.commit()

# Auto-initialize database tables on connection setup
init_db()
