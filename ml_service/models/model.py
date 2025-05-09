from pydantic import BaseModel
from typing import Optional

class Model(BaseModel):
    id: int
    name: str
    cost: float  # Стоимость предсказания в токенах