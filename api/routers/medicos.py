import re
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError
from database import db
from utils import a_json, validar_id, insertar

router = APIRouter(prefix="/api/medicos", tags=["Médicos"])


class EspecialidadIn(BaseModel):
    id: int
    nombre: str


class MedicoIn(BaseModel):
    nombres: str
    apellidos: str
    registro_medico: str
    especialidad: EspecialidadIn
    ips_id: int


def consultar(filtro: dict):
    """Devuelve los médicos con el nombre de su IPS (relación con $lookup)."""
    pipeline = [
        {"$match": filtro},
        {"$lookup": {"from": "ips", "localField": "ips_id",
                     "foreignField": "_id", "as": "ips"}},
        {"$unwind": {"path": "$ips", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {"ips_nombre": "$ips.nombre", "ips_ciudad": "$ips.ciudad"}},
        {"$project": {"ips": 0}},
    ]
    return [a_json(d) for d in db.medicos.aggregate(pipeline)]


def preparar(m: MedicoIn):
    datos = m.model_dump()
    ips_oid = validar_id(m.ips_id)
    if not db.ips.find_one({"_id": ips_oid}, {"_id": 1}):
        raise HTTPException(status_code=400, detail="La IPS indicada no existe")
    datos["ips_id"] = ips_oid
    return datos


@router.post("/", status_code=201)
def crear(m: MedicoIn):
    datos = preparar(m)
    try:
       nuevo_id = insertar("medicos", datos)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Ya existe un médico con ese registro médico")
    return consultar({"_id": nuevo_id})[0]


@router.get("/")
def listar(
    nombre: Optional[str] = None,
    especialidad: Optional[str] = None,
    ips_id: Optional[str] = None,
):
    filtro = {}
    if nombre:
        rx = {"$regex": re.escape(nombre), "$options": "i"}
        filtro["$or"] = [{"nombres": rx}, {"apellidos": rx}]
    if especialidad:
        filtro["especialidad.nombre"] = {"$regex": re.escape(especialidad), "$options": "i"}
    if ips_id:
        filtro["ips_id"] = validar_id(ips_id)
    return consultar(filtro)


@router.get("/{id}")
def obtener(id: str):
    res = consultar({"_id": validar_id(id)})
    if not res:
        raise HTTPException(status_code=404, detail="Médico no encontrado")
    return res[0]


@router.put("/{id}")
def actualizar(id: str, m: MedicoIn):
    oid = validar_id(id)
    datos = preparar(m)
    try:
        res = db.medicos.update_one({"_id": oid}, {"$set": datos})
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Ya existe un médico con ese registro médico")
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Médico no encontrado")
    return consultar({"_id": oid})[0]


@router.delete("/{id}")
def eliminar(id: str):
    oid = validar_id(id)
    if db.triajes.count_documents({"atencion.medico_id": oid}) > 0:
        raise HTTPException(status_code=409, detail="No se puede eliminar: el médico tiene atenciones registradas")
    res = db.medicos.delete_one({"_id": oid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Médico no encontrado")
    return {"mensaje": "Médico eliminado"}