from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class Transaction(BaseModel):
    id: Optional[int] = None
    user_id: int
    prediction_id: int
    price: float  # Количество списанных кредитов
    created_at: Optional[datetime] = None