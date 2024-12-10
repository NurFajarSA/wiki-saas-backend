# app/crud.py
from sqlalchemy.orm import Session
from . import models

def create_wiki_instance(db: Session, name: str, url: str, org_id: str):
    db_instance = models.WikiInstance(name=name, url=url, org_id=org_id)
    db.add(db_instance)
    db.commit()
    db.refresh(db_instance)
    return db_instance

def get_wiki_instance(db: Session, org_id: str):
    return db.query(models.WikiInstance).filter(models.WikiInstance.org_id == org_id).first()
