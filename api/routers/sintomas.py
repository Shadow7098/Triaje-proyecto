import re
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError
from database import db
from utils import a_json, validar_id, insertar

router = APIRouter(prefix="/api/sintomas", tags=["Síntomas"])


class SintomaIn(BaseModel):
    nombre: str
    categoria: str
    nivel_alerta: int = Field(ge=1, le=3)


@router.post("/", status_code=201)
def crear(s: SintomaIn):
    try:
        nuevo_id = insertar("sintomas", s.model_dump())
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Ya existe un síntoma con ese nombre")
    return a_json(db.sintomas.find_one({"_id": nuevo_id}))


@router.get("/")
def listar(
    nombre: Optional[str] = None,
    categoria: Optional[str] = None,
    nivel_alerta: Optional[int] = None,
):
    filtro = {}
    if nombre:
        filtro["nombre"] = {"$regex": re.escape(nombre), "$options": "i"}
    if categoria:
        filtro["categoria"] = {"$regex": re.escape(categoria), "$options": "i"}
    if nivel_alerta:
        filtro["nivel_alerta"] = nivel_alerta
    return [a_json(d) for d in db.sintomas.find(filtro)]


@router.get("/{id}")
def obtener(id: str):
    doc = db.sintomas.find_one({"_id": validar_id(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Síntoma no encontrado")
    return a_json(doc)


@router.put("/{id}")
def actualizar(id: str, s: SintomaIn):
    oid = validar_id(id)
    try:
        res = db.sintomas.update_one({"_id": oid}, {"$set": s.model_dump()})
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Ya existe un síntoma con ese nombre")
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Síntoma no encontrado")
    return a_json(db.sintomas.find_one({"_id": oid}))


@router.delete("/{id}")
def eliminar(id: str):
    oid = validar_id(id)
    if db.triajes.count_documents({"sintomas.sintoma_id": oid}) > 0:
        raise HTTPException(status_code=409, detail="No se puede eliminar: el síntoma está en triajes")
    if db.reglas_clasificacion.count_documents({"sintomas_ids": oid}) > 0:
        raise HTTPException(status_code=409, detail="No se puede eliminar: el síntoma está en reglas de clasificación")
    res = db.sintomas.delete_one({"_id": oid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Síntoma no encontrado")
    return {"mensaje": "Síntoma eliminado"}