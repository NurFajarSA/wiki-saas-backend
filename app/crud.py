# app/crud.py

from sqlalchemy.orm import Session
import models, schemas

def get_instance(db: Session, instance_id: int):
    return db.query(models.DeployedInstance).filter(models.DeployedInstance.id == instance_id).first()

def get_instances(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.DeployedInstance).offset(skip).limit(limit).all()

def create_instance(db: Session, instance: schemas.InstanceCreate):
    db_instance = models.DeployedInstance(
        name=instance.name,
        port=0,  # Akan diatur selama deployment
        container_name="",  # Akan diatur selama deployment
        db_name="",  # Akan diatur selama deployment
    )
    db.add(db_instance)
    db.commit()
    db.refresh(db_instance)
    return db_instance

def update_instance(db: Session, instance: schemas.InstanceUpdate, instance_id: int):
    db_instance = get_instance(db, instance_id)
    if db_instance:
        if instance.name:
            db_instance.name = instance.name
        if instance.status:
            db_instance.status = instance.status
        db.commit()
        db.refresh(db_instance)
    return db_instance

def delete_instance(db: Session, instance_id: int):
    db_instance = get_instance(db, instance_id)
    if db_instance:
        db.delete(db_instance)
        db.commit()
    return db_instance
