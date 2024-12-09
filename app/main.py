# app/main.py

import subprocess
import logging
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import List
from app.deploy import deploy_wikijs, configure_nginx
from . import crud, models, schemas
from .database import SessionLocal, engine
from sqlalchemy.orm import Session
import os
import docker

# Inisialisasi database
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dependency untuk mendapatkan sesi DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# API Token untuk otentikasi (opsional)
API_TOKEN = os.getenv("API_TOKEN", "your_default_api_token")

def verify_api_token(token: str = Header(...)):
    if token != API_TOKEN:
        logger.warning("Invalid API Token")
        raise HTTPException(status_code=403, detail="Forbidden")

# Inisialisasi Docker client
client = docker.from_env()

@app.post("/deploy", response_model=schemas.DeployResponse, dependencies=[Depends(verify_api_token)])
def deploy_wiki_endpoint(request: schemas.DeployRequest, db: Session = Depends(get_db)):
    """
    Endpoint untuk mendepoy instance Wiki.js baru.
    """
    try:
        instance_create = schemas.InstanceCreate(name=request.name)
        domain, port = deploy_wikijs(instance_create)
        logger.info(f"Deployed Wiki.js instance on port {port}.")

        # Konfigurasi NGINX
        configure_nginx(domain, port)

        # Kembalikan respons
        db_instance = db.query(models.DeployedInstance).filter(models.DeployedInstance.port == port).first()
        return schemas.DeployResponse(
            id=db_instance.id,
            name=db_instance.name,
            port=db_instance.port,
            status=db_instance.status
        )

    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/instances", response_model=List[schemas.Instance], dependencies=[Depends(verify_api_token)])
def read_instances(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Mendapatkan daftar semua instance yang telah di-deploy.
    """
    instances = crud.get_instances(db, skip=skip, limit=limit)
    return instances

@app.get("/instances/{instance_id}", response_model=schemas.Instance, dependencies=[Depends(verify_api_token)])
def read_instance(instance_id: int, db: Session = Depends(get_db)):
    """
    Mendapatkan detail dari sebuah instance berdasarkan ID.
    """
    db_instance = crud.get_instance(db, instance_id)
    if db_instance is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    return db_instance

@app.put("/instances/{instance_id}", response_model=schemas.Instance, dependencies=[Depends(verify_api_token)])
def update_instance_endpoint(instance_id: int, instance_update: schemas.InstanceUpdate, db: Session = Depends(get_db)):
    """
    Memperbarui informasi sebuah instance.
    """
    db_instance = crud.update_instance(db, instance_update, instance_id)
    if db_instance is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    return db_instance

@app.delete("/instances/{instance_id}", response_model=schemas.Instance, dependencies=[Depends(verify_api_token)])
def delete_instance_endpoint(instance_id: int, db: Session = Depends(get_db)):
    """
    Menghapus sebuah instance yang telah di-deploy.
    """
    db_instance = crud.delete_instance(db, instance_id)
    if db_instance is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    # Stop dan hapus Docker container
    try:
        container = client.containers.get(db_instance.container_name)
        container.stop()
        container.remove()
        logger.info(f"Container '{db_instance.container_name}' telah dihentikan dan dihapus.")
    except docker.errors.NotFound:
        logger.warning(f"Container '{db_instance.container_name}' tidak ditemukan.")
    except docker.errors.APIError as e:
        logger.error(f"Error saat menghapus container '{db_instance.container_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error saat menghapus container: {e}")
    
    # Hapus konfigurasi NGINX
    config_filename = f"{db_instance.name}_{db_instance.port}"
    config_path = f"/etc/nginx/sites-enabled/{config_filename}"
    available_path = f"/etc/nginx/sites-available/{config_filename}"
    try:
        if os.path.islink(config_path):
            os.unlink(config_path)
            logger.info(f"Symlink '{config_path}' telah dihapus.")
        if os.path.exists(available_path):
            os.remove(available_path)
            logger.info(f"File konfigurasi '{available_path}' telah dihapus.")
        # Test dan reload NGINX
        subprocess.run(['sudo', 'nginx', '-t'], check=True)
        subprocess.run(['sudo', 'systemctl', 'reload', 'nginx'], check=True)
    except Exception as e:
        logger.error(f"Error saat menghapus konfigurasi NGINX: {e}")
        raise HTTPException(status_code=500, detail=f"Error saat menghapus konfigurasi NGINX: {e}")
    
    # Hapus database
    try:
        subprocess.run(
            ['sudo', '-u', 'postgres', 'psql', '-c', f"DROP DATABASE IF EXISTS {db_instance.db_name};"],
            check=True
        )
        logger.info(f"Database '{db_instance.db_name}' telah dihapus.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Gagal menghapus database '{db_instance.db_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Gagal menghapus database: {e}")
    
    return db_instance
