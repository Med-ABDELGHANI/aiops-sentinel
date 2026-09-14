from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/servers", tags=["servers"])


@router.get("/", response_model=list[schemas.ServerOut])
def list_servers(db: Session = Depends(get_db)):
    return db.query(models.Server).all()


@router.get("/{server_id}", response_model=schemas.ServerOut)
def get_server(server_id: int, db: Session = Depends(get_db)):
    server = db.query(models.Server).filter(models.Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


@router.post("/", response_model=schemas.ServerOut, status_code=201)
def create_server(server: schemas.ServerCreate, db: Session = Depends(get_db)):
    db_server = models.Server(**server.model_dump())
    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    return db_server


@router.patch("/{server_id}", response_model=schemas.ServerOut)
def update_server(server_id: int, updates: schemas.ServerUpdate, db: Session = Depends(get_db)):
    server = db.query(models.Server).filter(models.Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(server, field, value)

    db.commit()
    db.refresh(server)
    return server


@router.delete("/{server_id}", status_code=204)
def delete_server(server_id: int, db: Session = Depends(get_db)):
    server = db.query(models.Server).filter(models.Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    db.delete(server)
    db.commit()
