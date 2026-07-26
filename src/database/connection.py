import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import Config
from src.database.models import (
    ArticleRecommendation,
    ArticleContradiction,
    Base,
)

logger = logging.getLogger(__name__)

engine = create_engine(
    Config.DATABASE_URL,
    echo=False,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def init_db():
    try:
        logger.info(
            "Connecting to PostgreSQL and verifying tables..."
        )

        logger.info("Database: %s", engine.url.database)
        logger.info(
            "Registered tables: %s",
            list(Base.metadata.tables.keys()),
        )

        Base.metadata.create_all(bind=engine)

        logger.info(
            "Database schemas are fully initialized and ready"
        )

    except Exception as error:
        logger.exception(
            "Failed to connect or initialize database tables: %s",
            error,
        )
        raise