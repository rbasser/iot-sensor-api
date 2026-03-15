import os
import sys
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from sqlalchemy.dialects.postgresql import insert
from db import SessionLocal
from models import SensorReading, DailySummary
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/London") 

def run_retroactive_aggregation(days_back=7):
    if SessionLocal is None:
        print("ERROR: No database URL found. Check your .env file.")
        sys.exit(1)
    db = SessionLocal()
    try:
        today = datetime.now(tz=TZ).date()

        for i in range(days_back, 0, -1):
            target_date = today - timedelta(days=i)
            print(f"--- Processing {target_date} ---")

            existing_summary = db.query(DailySummary).filter(
                func.date(DailySummary.date) == target_date
            ).first()
            if existing_summary:
                print(f"Summary already exists. Skipping.")
                continue

            day_start = datetime(
                target_date.year, target_date.month, target_date.day,
                tzinfo=TZ
            )
            day_end = day_start + timedelta(days=1)

            time_bounds = db.query(
                func.min(SensorReading.timestamp),
                func.max(SensorReading.timestamp),
                func.count(SensorReading.id)
            ).filter(
                SensorReading.timestamp >= day_start,
                SensorReading.timestamp < day_end
            ).first()

            first_reading, last_reading, reading_count = time_bounds

            if not first_reading or not last_reading:
                print(f"No data found. Skipping.")
                continue

            data_span = last_reading - first_reading
            minimum_span = timedelta(hours=18)

            if data_span < minimum_span:
                print(
                    f"Skipping: Data only spans {data_span} "
                    f"(Requires at least {minimum_span}). "
                    f"Total readings: {reading_count}."
                )
                continue

            stats = db.query(
                func.avg(SensorReading.temperature),
                func.avg(SensorReading.humidity),
                func.avg(SensorReading.pressure),
                func.count(SensorReading.reboot_flag)
            ).filter(
                SensorReading.timestamp >= day_start,
                SensorReading.timestamp < day_end
            ).first()

            
            stmt = insert(DailySummary).values(
            date=target_date,
            avg_temp=round(stats[0], 2),
            avg_humidity=round(stats[1], 2),
            avg_pressure=round(stats[2], 0),
            reboot_count=int(stats[3] or 0)
            ).on_conflict_do_nothing()

            try:
                db.execute(stmt)
                db.commit()
                print(f"Aggregation successful! Summarised {reading_count} readings.")
            except Exception as e:
                db.rollback()
                print(f"Failed to commit summary for {target_date}: {e}")

    except Exception as e:
        print(f"Unexpected error during aggregation: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_retroactive_aggregation(days_back=7)