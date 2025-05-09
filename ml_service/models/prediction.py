from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class Prediction(BaseModel):
    id: Optional[int] = None
    user_id: int
    model_id: int
    input_data: List[Dict[str, Any]]  # Список словарей с данными грибов
    result: Optional[List[str]] = None  # Список предсказаний (e - edible или p - poisonous)
    status: str = "pending"  # pending, completed, failed
    created_at: Optional[datetime] = None

    model_config = ConfigDict(arbitrary_types_allowed=True) # Чтобы избежать ошибок с pydantic