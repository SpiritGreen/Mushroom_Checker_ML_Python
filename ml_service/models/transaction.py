from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class Transaction(BaseModel):
    id: Optional[int] = None
    user_id: int
    prediction_id: Optional[int] = None
    amount: float  
    description: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)