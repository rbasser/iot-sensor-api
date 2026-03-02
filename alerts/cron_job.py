import os
from sqlalchemy.orm import Session
from db import SessionLocal
from models import SensorReading, DailySummary # Assuming you added DailySummary to models.py
from datetime import datetime, timedelta
from sqlalchemy import func

def run_aggregation():
    db = SessionLocal()
    try:
        # 1. Define the target date (yesterday)
        yesterday = (datetime.now() - timedelta(days=1)).date()
        
        print(f"Starting aggregation for: {yesterday}")

        # 2. Calculate averages and count reboots
        # Using func.date() to filter the timestamp to just that day
        stats = db.query(
            func.avg(SensorReading.temperature),
            func.avg(SensorReading.humidity),
            func.avg(SensorReading.pressure),
            func.count(SensorReading.reboot_flag)
        ).filter(func.date(SensorReading.timestamp) == yesterday).first()

        if stats[0] is None:
            print("No data found for yesterday. Skipping.")
            return

        # 3. Save to DailySummary table
        summary = DailySummary(
            date=yesterday,
            avg_temp=round(stats[0], 2),
            avg_humidity=round(stats[1], 2),
            avg_pressure=round(stats[2], 0),
            reboot_count=stats[3]
        )
        
        db.add(summary)
        db.commit()
        print("Aggregation successful.")
        
    except Exception as e:
        print(f"Error during aggregation: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_aggregation()