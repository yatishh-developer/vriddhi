import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from core.config import settings


logger = logging.getLogger("vriddhi.database")


try:
    SQLALCHEMY_DATABASE_URL = settings.get_database_url()
except Exception as e:
    logger.exception("Error constructing the database URL: %s", e)
    raise


engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()
