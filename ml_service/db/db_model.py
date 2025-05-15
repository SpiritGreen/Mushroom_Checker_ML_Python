from sqlalchemy import Column, Integer, String, Float
from database import Base

class DBModel(Base):
    __tablename__ = "models"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    cost = Column(Float, nullable=False)
    file_path = Column(String, nullable=False)