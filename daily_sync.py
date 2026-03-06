import os
import sys
from sqlalchemy.orm import Session
from db import SessionLocal
from models import SensorReading, DailySummary
from datetime import datetime, timedelta
from sqlalchemy import func

def run_aggregation():
    db = SessionLocal()
    try:
        yesterday = (datetime.now() - timedelta(days=1)).date()
        
        print(f"Starting aggregation for: {yesterday}")

        time_bounds = db.query(
            func.min(SensorReading.timestamp),
            func.max(SensorReading.timestamp),
            func.count(SensorReading.id)
        ).filter(func.date(SensorReading.timestamp) == yesterday).first()

        first_reading = time_bounds[0]
        last_reading = time_bounds[1]
        reading_count = time_bounds[2]

        if not first_reading or not last_reading:
            print(f"No data found for {yesterday}. Skipping.")
            return

        data_span = last_reading - first_reading
        
        minimum_span = timedelta(hours=18)
        
        if data_span < minimum_span:
            print(f"Skipping: Data only spans {data_span} (Requires at least {minimum_span}). Total readings: {reading_count}.")
            return

        stats = db.query(
            func.avg(SensorReading.temperature),
            func.avg(SensorReading.humidity),
            func.avg(SensorReading.pressure),
            func.count(SensorReading.reboot_flag)
        ).filter(func.date(SensorReading.timestamp) == yesterday).first()

        summary = DailySummary(
            date=yesterday,
            avg_temp=round(stats[0], 2),
            avg_humidity=round(stats[1], 2),
            avg_pressure=round(stats[2], 0),
            reboot_count=stats[3]
        )
        
        db.add(summary)
        db.commit()
        print(f"Aggregation successful! Summarized {reading_count} readings for {yesterday}.")
        
    except Exception as e:
        print(f"Error during aggregation: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_aggregation()