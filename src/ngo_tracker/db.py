"""SQLAlchemy models and session management for the funding graph store."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Float, ForeignKey, Index, Integer, String, create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "tracker.db"


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class Entity(Base):
    """An organization or person participating in the funding graph."""

    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    type: Mapped[str] = mapped_column(String(30), index=True)
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ein: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class ApiKey(Base):
    """A hashed API key granting a paid plan."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(20))
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)


class Funding(Base):
    """A documented grant or donation between two entities."""

    __tablename__ = "funding"
    __table_args__ = (
        Index("ix_funding_source", "source_id"),
        Index("ix_funding_target", "target_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("entities.id"))
    target_id: Mapped[int] = mapped_column(ForeignKey("entities.id"))
    amount_usd: Mapped[float] = mapped_column(Float)
    year: Mapped[int] = mapped_column(Integer)
    purpose: Mapped[str | None] = mapped_column(String(500), nullable=True)
    citation: Mapped[str] = mapped_column(String(500))


def make_engine(db_path: Path | str = DEFAULT_DB_PATH):
    """Create an engine and ensure the schema and parent directory exist.

    Args:
        db_path: SQLite file location, or ":memory:" for tests.

    Returns:
        A configured SQLAlchemy engine.
    """
    if db_path == ":memory:":
        # Single shared connection so all sessions/threads see the same data.
        engine = create_engine(
            "sqlite:///:memory:",
            future=True,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
    else:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    return engine


@contextmanager
def session_scope(factory: sessionmaker) -> Iterator[Session]:
    """Provide a transactional session that commits or rolls back.

    Args:
        factory: Session factory bound to an engine.

    Yields:
        An active session; committed on success, rolled back on error.
    """
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
