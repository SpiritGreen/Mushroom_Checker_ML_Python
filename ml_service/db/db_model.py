from sqlalchemy import Column, Integer, String, Float
from database import Base

class DBModel(Base):
    __tablename__ = "models"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50))
    cost = Column(Float)
    file_path = Column(String(255))  