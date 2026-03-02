from db import Base
from sqlalchemy import Integer, Column, Float, String, DateTime
from sqlalchemy.sql import func

class SensorReading(Base):
    __tablename__ = "sensor_readings"
    
    id = Column(Integer, primary_key=True, index=True)
    # Automatically generates a server-side timestamp on creation
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True) 


    temperature = Column(Float)
    humidity = Column(Float)
    pressure = Column(Integer)
    gas_resistance = Column(Integer, nullable=True) # Allowed to be null
    reboot_flag = Column(String, nullable=True)     # Store "rebooted" or leave null