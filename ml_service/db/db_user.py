from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from datetime import datetime
from database import Base

class DBUser(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255))
    balance = Column(Float, default=10.0)  # Бонус при регистрации (10 кредитов)
    disabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)