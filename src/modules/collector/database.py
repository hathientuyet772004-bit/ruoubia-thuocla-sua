from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from shared.config import settings

DATABASE_URL = settings.database_url

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
