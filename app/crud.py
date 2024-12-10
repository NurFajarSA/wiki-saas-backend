# app/crud.py
from sqlalchemy.orm import Session
from . import models

def create_wiki_instance(db: Session, name: str, url: str):
    db_instance = models.WikiInstance(name=name, url=url)
    db.add(db_instance)
    db.commit()
    db.refresh(db_instance)
    return db_instance

def get_wiki_instance(db: Session, wiki_id: int):
    return db.query(models.WikiInstance).filter(models.WikiInstance.id == wiki_id).first()
