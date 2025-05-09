from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class User(BaseModel):
    id: Optional[int] = None
    username: str
    email: Optional[str] = None
    hashed_password: str
    balance: float = 10.0   # Приветственный бонус для новых пользователей
    disabled: bool = False  # Для удаления или бана пользователя
    created_at: Optional[datetime] = None