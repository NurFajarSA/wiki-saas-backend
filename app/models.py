# app/models.py
from sqlalchemy import Column, String, Integer
from .database import Base

class WikiInstance(Base):
    __tablename__ = "wiki_instances"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, unique=True, index=True, nullable=False)
    url = Column(String, unique=True, index=True, nullable=False)
