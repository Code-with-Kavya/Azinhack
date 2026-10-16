"""Database engine configuration and session dependency for SQLite via SQLModel.

Stores profiles in `profiles.db` at the project root.
"""

import os
from pathlib import Path
from typing import Generator
from sqlmodel import Session, SQLModel, create_engine

# Determine project root: backend/.. -> gov-scheme-agent/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_FILE = PROJECT_ROOT / "profiles.db"

# Allow overriding via environment variable
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_FILE.as_posix()}")

# check_same_thread=False is required for SQLite when accessed by multi-threaded FastAPI
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)


def init_db() -> None:
    """Creates database tables defined in SQLModel if they do not exist, and migrates missing columns."""
    from sqlmodel import text
    import models  # noqa: F401

    SQLModel.metadata.create_all(engine)

    # Safe SQLite column migrations for Stage 3 new Application fields
    if DATABASE_URL.startswith("sqlite"):
        with engine.connect() as conn:
            try:
                res = conn.execute(text("PRAGMA table_info(applications)")).fetchall()
                existing_cols = {row[1] for row in res}
                if existing_cols:
                    if "mode" not in existing_cols:
                        conn.execute(text("ALTER TABLE applications ADD COLUMN mode VARCHAR DEFAULT 'dry_run'"))
                    if "screenshot_url" not in existing_cols:
                        conn.execute(text("ALTER TABLE applications ADD COLUMN screenshot_url VARCHAR"))
                    if "updated_at" not in existing_cols:
                        conn.execute(text("ALTER TABLE applications ADD COLUMN updated_at TIMESTAMP"))
                    conn.commit()
            except Exception as e:
                # Table might not exist yet or other non-fatal error
                pass


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a scoped database session."""
    with Session(engine) as session:
        yield session
