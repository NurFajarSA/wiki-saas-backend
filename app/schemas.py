# app/schemas.py

from pydantic import BaseModel
from typing import Optional

class DeployRequest(BaseModel):
    id: int
    name: str

class DeployResponse(BaseModel):
    id: int
    name: str
    port: int
    status: str

    class Config:
        from_attributes = True

class Instance(BaseModel):
    id: int
    name: str
    port: int
    status: str

    class Config:
        from_attributes = True

class InstanceCreate(BaseModel):
    name: str

class InstanceUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
