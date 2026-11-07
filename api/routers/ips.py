import re
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError
from database import db
from utils import a_json, validar_id, insertar

router = APIRouter(prefix="/api/ips", tags=["IPS"])


class IPSIn(BaseModel):
    nombre: str
    ciudad: str
    direccion: str
    nivel_complejidad: int = Field(ge=1, le=4)
    capacidad_urgencias: int = Field(ge=0)


@router.post("/", status_code=201)
def crear(ips: IPSIn):
    try:
        nuevo_id = insertar("ips", ips.model_dump())
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Ya existe una IPS con ese nombre en esa ciudad")
    return a_json(db.ips.find_one({"_id": nuevo_id}))


@router.get("/")
def listar(
    nombre: Optional[str] = None,
    ciudad: Optional[str] = None,
    nivel_complejidad: Optional[int] = None,
):
    filtro = {}
    if nombre:
        filtro["nombre"] = {"$regex": re.escape(nombre), "$options": "i"}
    if ciudad:
        filtro["ciudad"] = {"$regex": re.escape(ciudad), "$options": "i"}
    if nivel_complejidad:
        filtro["nivel_complejidad"] = nivel_complejidad
    return [a_json(d) for d in db.ips.find(filtro)]


@router.get("/{id}")
def obtener(id: str):
    doc = db.ips.find_one({"_id": validar_id(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="IPS no encontrada")
    return a_json(doc)


@router.put("/{id}")
def actualizar(id: str, ips: IPSIn):
    oid = validar_id(id)
    try:
        res = db.ips.update_one({"_id": oid}, {"$set": ips.model_dump()})
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Ya existe una IPS con ese nombre en esa ciudad")
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="IPS no encontrada")
    return a_json(db.ips.find_one({"_id": oid}))


@router.delete("/{id}")
def eliminar(id: str):
    oid = validar_id(id)
    if db.medicos.count_documents({"ips_id": oid}) > 0:
        raise HTTPException(status_code=409, detail="No se puede eliminar: hay médicos asociados a esta IPS")
    if db.triajes.count_documents({"ips_id": oid}) > 0:
        raise HTTPException(status_code=409, detail="No se puede eliminar: hay triajes asociados a esta IPS")
    res = db.ips.delete_one({"_id": oid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="IPS no encontrada")
    return {"mensaje": "IPS eliminada"}