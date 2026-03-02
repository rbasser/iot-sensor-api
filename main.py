import os
from fastapi import FastAPI, Depends, HTTPException, status, Security
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import services, models, schemas
from db import get_db, engine
from sqlalchemy.orm import Session

models.Base.metadata.create_all(bind=engine)

app = FastAPI()


API_KEY_SECRET = os.getenv("API_KEY", "my_super_secret_key")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows any website to access your data
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_api_key(api_key: str = Security(api_key_header)):
    if api_key == API_KEY_SECRET:
        return api_key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API Key"
    )


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
        
@app.delete("/readings/{id}", response_model=schemas.Reading, dependencies=[Depends(get_api_key)])
def delete_reading_entry(id: int, db: Session = Depends(get_db)):
    deleted_entry = services.delete_reading(db, id)
    if deleted_entry:
        return deleted_entry
    raise HTTPException(status_code=404, detail="Failed to delete reading")


@app.get("/readings/", response_model=list[schemas.Reading]) 
async def get_all_readings(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return services.get_readings(db, skip=skip, limit=limit)

@app.get("/readings/latest", response_model=schemas.Reading)
def get_latest_sensor_reading(db: Session = Depends(get_db)):
    reading = services.get_latest_reading(db)
    if reading:
        return reading
    raise HTTPException(status_code=404, detail="No readings found")

@app.get("/readings/{id}", response_model=schemas.Reading)
def get_reading_by_id(id: int, db: Session = Depends(get_db)):
    reading = services.get_reading(db, id)
    if reading:
        return reading
    raise HTTPException(status_code=404, detail="Reading Not Found")

@app.get("/")
async def read_index():
    return FileResponse(os.path.join('static', 'index.html'))