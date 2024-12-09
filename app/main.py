# app/main.py (tambahkan di bagian atas)
from .database import engine
from . import models

models.Base.metadata.create_all(bind=engine)

# app/main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from . import models, crud, database, deploy
from pydantic import BaseModel
import os
import subprocess

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
        # Panggil skrip nginx_config.sh dengan domain dan port
        subprocess.run(
            ["sudo", "/usr/local/bin/nginx_config.sh", domain, str(port)],
            check=True
        )
    except subprocess.CalledProcessError as e:
        raise Exception(f"NGINX configuration failed: {e}")

@app.post("/deploy", response_model=WikiResponse)
def deploy_wiki(wiki: WikiCreate, db: Session = Depends(get_db)):
    # Cek apakah slug sudah ada
    existing = db.query(models.WikiInstance).filter(models.WikiInstance.slug == wiki.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Slug sudah ada")

    # Deploy wiki.js
    try:
        domain, port = deploy.deploy_wikijs(wiki.slug)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Konfigurasikan NGINX
    try:
        configure_nginx(domain, port)
    except Exception as e:
        # Jika konfigurasi NGINX gagal, hentikan container yang sudah dijalankan
        client = docker.from_env()
        container_name = f"wiki_{wiki.slug}"
        try:
            container = client.containers.get(container_name)
            container.stop()
            container.remove()
        except:
            pass
        raise HTTPException(status_code=500, detail=str(e))

    # Simpan ke database
    url = f"https://{domain}"
    db_instance = crud.create_wiki_instance(db, name=wiki.name, slug=wiki.slug, url=url)
    return db_instance

# Membuat tabel database saat aplikasi dijalankan pertama kali
models.Base.metadata.create_all(bind=database.engine)

# app/main.py (lanjutan)
def obtain_ssl_certificate(domain: str):
    try:
        # Jalankan Certbot untuk mendapatkan sertifikat SSL
        subprocess.run(
            [
                "sudo", "certbot", "--nginx", 
                "-d", domain, 
                "--non-interactive", 
                "--agree-tos", 
                "-m", "admin@yourdomain.com"
            ],
            check=True
        )
    except subprocess.CalledProcessError as e:
        raise Exception(f"SSL Certificate acquisition failed: {e}")

@app.post("/deploy", response_model=WikiResponse)
def deploy_wiki(wiki: WikiCreate, db: Session = Depends(get_db)):
    # Cek apakah slug sudah ada
    existing = db.query(models.WikiInstance).filter(models.WikiInstance.slug == wiki.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Slug sudah ada")

    # Deploy wiki.js
    try:
        domain, port = deploy.deploy_wikijs(wiki.slug)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Konfigurasikan NGINX
    try:
        configure_nginx(domain, port)
    except Exception as e:
        # Jika konfigurasi NGINX gagal, hentikan container yang sudah dijalankan
        client = docker.from_env()
        container_name = f"wiki_{wiki.slug}"
        try:
            container = client.containers.get(container_name)
            container.stop()
            container.remove()
        except:
            pass
        raise HTTPException(status_code=500, detail=str(e))

    # Dapatkan Sertifikat SSL
    try:
        obtain_ssl_certificate(domain)
    except Exception as e:
        # Jika SSL gagal, hapus konfigurasi NGINX dan container
        os.remove(f"/etc/nginx/sites-enabled/{domain}")
        os.remove(f"/etc/nginx/sites-available/{domain}")
        subprocess.run(["sudo", "systemctl", "reload", "nginx"])
        client = docker.from_env()
        container_name = f"wiki_{wiki.slug}"
        try:
            container = client.containers.get(container_name)
            container.stop()
            container.remove()
        except:
            pass
        raise HTTPException(status_code=500, detail=str(e))

    # Simpan ke database
    url = f"https://{domain}"
    db_instance = crud.create_wiki_instance(db, name=wiki.name, slug=wiki.slug, url=url)
    return db_instance
