from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

class ReadingBase(BaseModel):
    pressure: int = Field(..., ge= 80000, le= 120000) 
    temperature: float = Field(..., ge= -10, le= 50) 
    humidity: float = Field(..., ge=0.0, le=100.0)
    gas_resistance: Optional[int] = None
    reboot_flag: Optional[str] = None

class ReadingCreate(ReadingBase):
    pass

class Reading(ReadingBase):
    id: int
    timestamp: datetime
    
    model_config = ConfigDict(from_attributes=True)