import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("EXT_DB_URL")
if SQLALCHEMY_DATABASE_URL:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
else:
    engine = None

if engine:
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    SessionLocal = None
    
Base = declarative_base()

def get_db():
    if SessionLocal is None:
        raise RuntimeError("No database URL found. Set DATABASE_URL or EXT_DB_URL.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_table():
    if engine is None:
        raise RuntimeError("No database URL found. Set DATABASE_URL or EXT_DB_URL.")
    Base.metadata.create_all(bind=engine)