from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session


# Project directory
BASE_DIR = Path(__file__).resolve().parent

# SQLite database file
DATABASE_PATH = BASE_DIR / "students.db"

DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"


# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)


# Create database session
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# Base class for database models
class Base(DeclarativeBase):
    pass


# Database dependency
def get_db():
    db: Session = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# Initialize database tables
def init_db():
    Base.metadata.create_all(bind=engine)