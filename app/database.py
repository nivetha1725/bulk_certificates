"""Database engine / session setup (SQLite + SQLAlchemy)."""
import logging
from collections.abc import Callable

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]


class Base(DeclarativeBase):
    pass


def create_db_engine(database_url: str) -> Engine:
    """Create an engine. Also used by tests with a temporary database."""
    engine = create_engine(
        database_url,
        # Background tasks run in worker threads, so allow cross-thread use.
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


engine = create_db_engine(settings.database_url)
SessionLocal = create_session_factory(engine)


def init_db() -> None:
    """Create tables if they do not exist yet."""
    import app.models  # noqa: F401  (registers models on Base.metadata)

    Base.metadata.create_all(bind=engine)
    logger.info("Database initialised")
