# app/models.py
from sqlalchemy import Column, String
from .database import Base

class WikiInstance(Base):
    __tablename__ = "wiki_instances"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    url = Column(String, unique=True, index=True, nullable=False)
