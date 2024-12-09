# app/models.py

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from .database import Base

class DeployedInstance(Base):
    __tablename__ = "deployed_instances"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    port = Column(Integer, unique=True, index=True, nullable=False)
    container_name = Column(String, unique=True, nullable=False)
    db_name = Column(String, unique=True, nullable=False)
    status = Column(String, default="deployed")  # Bisa 'deployed', 'error', dll.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
