import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Fetch the URL from environment variables, fallback to local for testing
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# Render uses 'postgres://' but SQLAlchemy requires 'postgresql://'
if not SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
    if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)
    else:
        raise ValueError("Invalid DATABASE_URL format. Must start with 'postgres://' or 'postgresql://'.")

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_table():
    Base.metadata.create_all(bind=engine)