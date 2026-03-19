from sqlalchemy import func

from models import SensorReading
from sqlalchemy.orm import Session
from schemas import ReadingCreate
from datetime import datetime, timedelta, timezone

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

def get_readings_since(db: Session, hours: int = 1):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return db.query(SensorReading).filter(SensorReading.timestamp >= cutoff).order_by(SensorReading.timestamp.desc()).all()

def get_reading_at_offset(db: Session, minutes_ago: int = 60, window_minutes: int = 3):
    target = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    window = timedelta(minutes=window_minutes)
    return db.query(SensorReading).filter(
        SensorReading.timestamp >= target - window,
        SensorReading.timestamp <= target + window
    ).order_by(
        func.abs(
            func.extract('epoch', SensorReading.timestamp) -
            func.extract('epoch', target)
        )
    ).first()
    
def get_bucketed_readings(db: Session, hours: int, bucket_seconds: float):
    result = db.execute(text("""
        SELECT
            MIN(timestamp) as timestamp,
            ROUND(AVG(temperature)::numeric, 2) as temperature,
            ROUND(AVG(humidity)::numeric, 2) as humidity,
            ROUND(AVG(pressure)::numeric, 0) as pressure
        FROM (
            SELECT *,
                FLOOR(EXTRACT(EPOCH FROM timestamp) / :bucket_seconds) as bucket
            FROM sensor_readings
            WHERE timestamp >= NOW() - (:hours * INTERVAL '1 hour')
        ) bucketed
        GROUP BY bucket
        ORDER BY timestamp DESC
    """), {"bucket_seconds": float(bucket_seconds), "hours": hours})
    return [dict(row._mapping) for row in result]

def delete_reading(db: Session, id: int):
    reading_queryset = db.query(SensorReading).filter(SensorReading.id == id).first()
    if reading_queryset:
        db.delete(reading_queryset)
        db.commit()
    return reading_queryset