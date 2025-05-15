from sqlalchemy import Column, Integer, String, JSON, DateTime
from database import Base
from datetime import datetime, timezone

class DBPrediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    model_id = Column(Integer, nullable=False)
    input_data = Column(JSON, nullable=False)
    result = Column(JSON, nullable=True)  
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))