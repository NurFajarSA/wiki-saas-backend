# app/main.py

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
    id: str
    name: str
    slug: str

class WikiResponse(BaseModel):
    id: str
    name: str
    slug: str
    url: str

    class Config:
        orm_mode = True

@app.post("/deploy", response_model=WikiResponse)
def deploy_wiki(wiki: WikiCreate, db: Session = Depends(get_db)):
    try:
        base_url, port = deploy.deploy_wikijs(wiki.slug)
        logger.info(f"Deployed wiki.js for slug '{wiki.slug}' on base_url '{base_url}' and port '{port}'.")
    except Exception as e:
        logger.error(f"Deployment failed for slug '{wiki.slug}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Simpan ke database
    url = f"{base_url}:{port}"
    try:
        db_instance = crud.create_wiki_instance(db, name=wiki.name, slug=wiki.slug, url=url)
        logger.info(f"Saved wiki instance '{wiki.slug}' to database with URL '{url}'.")
    except Exception as db_error:
        logger.error(f"Failed to save wiki instance '{wiki.slug}' to database: {db_error}")
        raise HTTPException(status_code=500, detail="Gagal menyimpan ke database.")

    return db_instance
