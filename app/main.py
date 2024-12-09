# app/main.py

import os
import subprocess
import logging
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from . import models, crud, database, deploy
from .database import engine

# Membuat tabel database saat aplikasi dijalankan pertama kali
models.Base.metadata.create_all(bind=engine)

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Dependency untuk mendapatkan sesi database
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Schema Pydantic
class WikiCreate(BaseModel):
    id: int
    name: str
    slug: str

class WikiResponse(BaseModel):
    id: int
    name: str
    slug: str
    url: str

    class Config:
        orm_mode = True

def configure_nginx(domain: str, port: int):
    try:
        logger.info(f"Configuring NGINX for domain: {domain} on port: {port}")
        subprocess.run(
            ["sudo", "/usr/local/bin/nginx_config.sh", domain, str(port)],
            check=True
        )
        logger.info("NGINX configuration successful.")
    except subprocess.CalledProcessError as e:
        logger.error(f"NGINX configuration failed: {e}")
        raise Exception(f"NGINX configuration failed: {e}")

def obtain_ssl_certificate(domain: str):
    try:
        logger.info(f"Obtaining SSL certificate for domain: {domain}")
        subprocess.run(
            [
                "sudo", "certbot", "--nginx", 
                "-d", domain, 
                "--non-interactive", 
                "--agree-tos", 
                "-m", "admin@yourdomain.com"  # Ganti dengan email Anda
            ],
            check=True
        )
        logger.info("SSL certificate obtained successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"SSL Certificate acquisition failed: {e}")
        raise Exception(f"SSL Certificate acquisition failed: {e}")

@app.post("/deploy", response_model=WikiResponse)
def deploy_wiki(wiki: WikiCreate, db: Session = Depends(get_db)):
    # Cek apakah slug sudah ada
    existing = db.query(models.WikiInstance).filter(models.WikiInstance.slug == wiki.slug).first()
    if existing:
        logger.warning(f"Deploy failed: Slug '{wiki.slug}' already exists.")
        raise HTTPException(status_code=400, detail="Slug sudah ada")

    # Deploy wiki.js
    try:
        domain, port = deploy.deploy_wikijs(wiki.slug)
        logger.info(f"Deployed wiki.js for slug '{wiki.slug}' on domain '{domain}' and port '{port}'.")
    except Exception as e:
        logger.error(f"Deployment failed for slug '{wiki.slug}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Konfigurasikan NGINX
    try:
        configure_nginx(domain, port)
    except Exception as e:
        logger.error(f"NGINX configuration failed for slug '{wiki.slug}': {e}")
        # Jika konfigurasi NGINX gagal, hentikan dan hapus container
        client = docker.from_env()
        container_name = f"wiki_{wiki.slug}"
        try:
            container = client.containers.get(container_name)
            container.stop()
            container.remove()
            logger.info(f"Stopped and removed container '{container_name}' due to NGINX failure.")
        except docker.errors.NotFound:
            logger.warning(f"Container '{container_name}' not found during cleanup.")
        except Exception as cleanup_error:
            logger.error(f"Error during container cleanup: {cleanup_error}")
        raise HTTPException(status_code=500, detail=str(e))

    # Dapatkan Sertifikat SSL
    try:
        obtain_ssl_certificate(domain)
    except Exception as e:
        logger.error(f"SSL acquisition failed for domain '{domain}': {e}")
        # Jika SSL gagal, hapus konfigurasi NGINX dan container
        try:
            os.remove(f"/etc/nginx/sites-enabled/{domain}")
            os.remove(f"/etc/nginx/sites-available/{domain}")
            subprocess.run(["sudo", "systemctl", "reload", "nginx"], check=True)
            logger.info(f"Removed NGINX configuration for domain '{domain}' due to SSL failure.")
        except FileNotFoundError:
            logger.warning(f"NGINX configuration files for domain '{domain}' not found during cleanup.")
        except subprocess.CalledProcessError as reload_error:
            logger.error(f"Failed to reload NGINX during cleanup: {reload_error}")
        except Exception as cleanup_error:
            logger.error(f"Error during NGINX cleanup: {cleanup_error}")
        
        # Hentikan dan hapus container
        client = docker.from_env()
        container_name = f"wiki_{wiki.slug}"
        try:
            container = client.containers.get(container_name)
            container.stop()
            container.remove()
            logger.info(f"Stopped and removed container '{container_name}' due to SSL failure.")
        except docker.errors.NotFound:
            logger.warning(f"Container '{container_name}' not found during SSL cleanup.")
        except Exception as cleanup_error:
            logger.error(f"Error during container cleanup after SSL failure: {cleanup_error}")
        
        raise HTTPException(status_code=500, detail=str(e))

    # Simpan ke database
    url = f"https://{domain}"
    try:
        db_instance = crud.create_wiki_instance(db, name=wiki.name, slug=wiki.slug, url=url)
        logger.info(f"Saved wiki instance '{wiki.slug}' to database with URL '{url}'.")
    except Exception as db_error:
        logger.error(f"Failed to save wiki instance '{wiki.slug}' to database: {db_error}")
        # Opsional: Anda bisa menghentikan dan menghapus container serta konfigurasi NGINX jika penyimpanan database gagal
        raise HTTPException(status_code=500, detail="Gagal menyimpan ke database.")

    return db_instance
