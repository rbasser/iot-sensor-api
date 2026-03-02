from models import SensorReading
from sqlalchemy.orm import Session
from schemas import ReadingCreate

def create_reading(db: Session, data: ReadingCreate):
    reading_instance = SensorReading(**data.model_dump())
    db.add(reading_instance)
    db.commit()
    db.refresh(reading_instance)
    return reading_instance
    
def get_readings(db: Session, skip: int = 0, limit: int = 100):
    # Added skip/limit so you don't crash your server trying to load millions of rows at once
    return db.query(SensorReading).order_by(SensorReading.timestamp.desc()).offset(skip).limit(limit).all()

def get_reading(db: Session, reading_id: int):
    return db.query(SensorReading).filter(SensorReading.id == reading_id).first()

def get_latest_reading(db: Session):
    return db.query(SensorReading).order_by(SensorReading.timestamp.desc()).first()

def delete_reading(db: Session, id: int):
    reading_queryset = db.query(SensorReading).filter(SensorReading.id == id).first()
    if reading_queryset:
        db.delete(reading_queryset)
        db.commit()
    return reading_queryset