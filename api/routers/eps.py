import re
from typing import Optional, Literal
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError
from database import db

router = APIRouter(prefix="/api/eps", tags=["EPS"])


class EPSIn(BaseModel):
    nombre: str
    nit: str
    regimen: Literal["Contributivo", "Subsidiado"]


from utils import a_json, insertar , validar_id


@router.post("/", status_code=201)
def crear(eps: EPSIn):
    try:
        nuevo_id = insertar("eps", eps.model_dump())
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Ya existe una EPS con ese NIT")
    return a_json(db.eps.find_one({"_id": nuevo_id}))


@router.get("/")
def listar(nombre: Optional[str] = None, regimen: Optional[str] = None):
    filtro = {}
    if nombre:
        filtro["nombre"] = {"$regex": re.escape(nombre), "$options": "i"}
    if regimen:
        filtro["regimen"] = regimen
    return [a_json(d) for d in db.eps.find(filtro)]


@router.get("/{id}")
def obtener(id: str):
    doc = db.eps.find_one({"_id": validar_id(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="EPS no encontrada")
    return a_json(doc)


@router.put("/{id}")
def actualizar(id: str, eps: EPSIn):
    oid = validar_id(id)
    try:
        res = db.eps.update_one({"_id": oid}, {"$set": eps.model_dump()})
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Ya existe una EPS con ese NIT")
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="EPS no encontrada")
    return a_json(db.eps.find_one({"_id": oid}))


@router.delete("/{id}")
def eliminar(id: str):
    oid = validar_id(id)
    if db.pacientes.count_documents({"eps_id": oid}) > 0:
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: hay pacientes asociados a esta EPS",
        )
    res = db.eps.delete_one({"_id": oid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="EPS no encontrada")
    return {"mensaje": "EPS eliminada"}