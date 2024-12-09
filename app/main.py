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

app = FastAPI()

# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic Schemas
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

@app.post("/deploy", response_model=WikiResponse)
def deploy_wiki(wiki: WikiCreate, db: Session = Depends(get_db)):
    # Cek apakah slug sudah ada
    existing = db.query(models.WikiInstance).filter(models.WikiInstance.slug == wiki.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Slug already exists")

    # Deploy wiki.js
    try:
        url = deploy.deploy_wikijs(wiki.slug)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Simpan ke database
    db_instance = crud.create_wiki_instance(db, name=wiki.name, slug=wiki.slug, url=url)
    return db_instance
