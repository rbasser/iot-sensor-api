import os
from fastapi import FastAPI, Depends, HTTPException, Query, status, Security
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import services, models, schemas
from db import get_db, engine
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from sqlalchemy import func

app = FastAPI()


API_KEY_SECRET = os.getenv("API_KEY", "my_super_secret_key")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows any website to access data, required for dashboard to fetch data
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


static_path = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Serve the dashboard at /dashboard
@app.get("/dashboard", include_in_schema=False)
async def get_dashboard():
    return FileResponse(os.path.join(static_path, "index.html"))


def get_api_key(api_key: str = Security(api_key_header)):
    if api_key == API_KEY_SECRET:
        return api_key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API Key"
    )

# GET has no authentication, allowing access to dashboard
@app.get("/readings/", response_model=list[schemas.Reading]) 
async def get_all_readings(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return services.get_readings(db, skip=skip, limit=limit)

@app.get("/readings/latest", response_model=schemas.Reading)
def get_latest_sensor_reading(db: Session = Depends(get_db)):
    reading = services.get_latest_reading(db)
    if reading:
        return reading
    raise HTTPException(status_code=404, detail="No readings found")

@app.get("/readings/history", response_model=list[schemas.Reading])
def get_reading_history(hours: int = 1, db: Session = Depends(get_db)):
    return services.get_readings_since(db, hours=hours)

@app.get("/readings/at-offset", response_model=schemas.Reading)
def get_reading_at_offset(
    minutes_ago: int = 60,
    window_minutes: int = 3,
    db: Session = Depends(get_db)
):
    reading = services.get_reading_at_offset(db, minutes_ago=minutes_ago, window_minutes=window_minutes)
    if reading:
        return reading
    raise HTTPException(status_code=404, detail=f"No reading found within {window_minutes} min of {minutes_ago} min ago")

@app.get("/readings/summary")
def get_readings_summary(
    hours: int = Query(default=168, ge=1, le=168),
    buckets: int = Query(default=1000, ge=10, le=2000),
    db: Session = Depends(get_db)
):
    bucket_seconds = (hours * 3600) / buckets
    return services.get_bucketed_readings(db, hours=hours, bucket_seconds=bucket_seconds)

@app.get("/readings/{id}", response_model=schemas.Reading)
def get_reading_by_id(id: int, db: Session = Depends(get_db)):
    reading = services.get_reading(db, id)
    if reading:
        return reading
    raise HTTPException(status_code=404, detail="Reading Not Found")

@app.get("/")
async def read_index():
    return FileResponse(os.path.join('static', 'index.html'))

@app.get("/summaries/", response_model=list[schemas.DailySummary])
def get_daily_summaries(db: Session = Depends(get_db)):
    return db.query(models.DailySummary).order_by(models.DailySummary.date.desc()).limit(7).all()


#POST and DELETE require authentication; only authorised users can modify data
@app.post("/readings/", dependencies=[Depends(get_api_key)])
async def create_new_reading(reading: schemas.ReadingIncoming, db: Session = Depends(get_db)):
    is_valid = (
        (80000 <= reading.pressure <= 120000) and
        (-10 <= reading.temperature <= 50) and
        (0.0 <= reading.humidity <= 100.0)
    )

    if is_valid:
        valid_reading = schemas.ReadingCreate(**reading.model_dump())
        return services.create_reading(db, valid_reading)
    else:
        print(f"Silently dropped invalid data: {reading.model_dump()}")
        return JSONResponse(
            status_code=status.HTTP_200_OK, 
            content={"detail": "Data received but filtered out due to out-of-bounds values."}
        )
        

@app.post("/sync/daily", dependencies=[Depends(get_api_key)])
async def trigger_daily_sync(db: Session = Depends(get_db)):
    """
    Triggered by a GitHub Action. Calculates and saves the daily summary for yesterday.
    Requires the X-API-Key header.
    """
    try:
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        print(f"Starting aggregation for: {yesterday}")

        time_bounds = db.query(
            func.min(models.SensorReading.timestamp),
            func.max(models.SensorReading.timestamp),
            func.count(models.SensorReading.id)
        ).filter(func.date(models.SensorReading.timestamp) == yesterday).first()

        first_reading = time_bounds[0]
        last_reading = time_bounds[1]
        reading_count = time_bounds[2]

        if not first_reading or not last_reading:
            return {"status": "skipped", "message": f"No data found for {yesterday}."}

        data_span = last_reading - first_reading
        minimum_span = timedelta(hours=18)
        
        if data_span < minimum_span:
            return {"status": "skipped", "message": f"Data only spans {data_span} (Requires {minimum_span}). Readings: {reading_count}."}

        stats = db.query(
            func.avg(models.SensorReading.temperature),
            func.avg(models.SensorReading.humidity),
            func.avg(models.SensorReading.pressure),
            func.count(models.SensorReading.reboot_flag)
        ).filter(func.date(models.SensorReading.timestamp) == yesterday).first()

        summary = models.DailySummary(
            date=yesterday,
            avg_temp=round(stats[0], 2),
            avg_humidity=round(stats[1], 2),
            avg_pressure=round(stats[2], 0),
            reboot_count=stats[3]
        )
        
        db.add(summary)
        db.commit()
        
        return {"status": "success", "message": f"Summarized {reading_count} readings for {yesterday}."}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Aggregation error: {str(e)}")
        
@app.delete("/readings/{id}", response_model=schemas.Reading, dependencies=[Depends(get_api_key)])
def delete_reading_entry(id: int, db: Session = Depends(get_db)):
    deleted_entry = services.delete_reading(db, id)
    if deleted_entry:
        return deleted_entry
    raise HTTPException(status_code=404, detail="Failed to delete reading")




