import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Fetch the URL from environment variables if on render (using internal link), fetching external link locally otherwise
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("EXT_DB_URL")
if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError("No database URL found. Set DATABASE_URL or EXT_DB_URL.")
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