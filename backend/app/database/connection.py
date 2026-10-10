from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_database_engine(database_url: str, **engine_options):
    if database_url.startswith("sqlite"):
        connect_args = engine_options.get("connect_args", {})
        engine_options["connect_args"] = {
            **connect_args,
            "check_same_thread": False,
        }

    database_engine = create_engine(database_url, **engine_options)

    if database_url.startswith("sqlite"):
        event.listen(
            database_engine,
            "connect",
            enable_sqlite_foreign_keys,
        )

    return database_engine


engine = create_database_engine(settings.database_url)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
