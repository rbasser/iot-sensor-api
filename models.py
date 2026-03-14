from db import Base
from sqlalchemy import Date, Integer, Column, Float, String, DateTime
from sqlalchemy.sql import func

class SensorReading(Base):
    __tablename__ = "sensor_readings"
    
    id = Column(Integer, primary_key=True, index=True)
    # Server-side timestamp on creation
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True) 
    temperature = Column(Float)
    humidity = Column(Float)
    pressure = Column(Integer)
    gas_resistance = Column(Integer, nullable=True) 
    reboot_flag = Column(String, nullable=True) 
    
class DailySummary(Base):
    __tablename__ = "daily_summaries"
    id           = Column(Integer, primary_key=True)
    date         = Column(Date, unique=True, index=True)  # Date not DateTime
    avg_temp     = Column(Float)
    avg_humidity = Column(Float)
    avg_pressure = Column(Integer)
    reboot_count = Column(Integer)
