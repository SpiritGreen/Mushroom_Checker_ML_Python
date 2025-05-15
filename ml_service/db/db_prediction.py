from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey
from datetime import datetime
from database import Base

class DBPrediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    model_id = Column(Integer, ForeignKey("models.id"))
    input_data = Column(JSON)
    result = Column(JSON)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)