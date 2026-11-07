import re
from datetime import date, datetime
from typing import Literal, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError
from database import db
from utils import a_json, insertar, validar_id

router = APIRouter(prefix="/api/pacientes", tags=["Pacientes"])


class PacienteIn(BaseModel):
    tipo_documento: Literal["CC", "TI", "CE", "PA", "RC"]
    numero_documento: str
    nombres: str
    apellidos: str
    fecha_nacimiento: date
    sexo: Literal["F", "M"]
    telefono: str
    ciudad: str
    eps_id: int


def consultar(filtro: dict):
    """Devuelve los pacientes con el nombre y régimen de su EPS."""
    pipeline = [
        {"$match": filtro},
        {"$lookup": {"from": "eps", "localField": "eps_id",
                     "foreignField": "_id", "as": "eps"}},
        {"$unwind": {"path": "$eps", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {"eps_nombre": "$eps.nombre", "eps_regimen": "$eps.regimen"}},
        {"$project": {"eps": 0}},
    ]
    return [a_json(d) for d in db.pacientes.aggregate(pipeline)]


def preparar(p: PacienteIn):
    if p.fecha_nacimiento > date.today():
        raise HTTPException(status_code=400, detail="La fecha de nacimiento no puede ser futura")
    eps_oid = validar_id(p.eps_id)
    if not db.eps.find_one({"_id": eps_oid}, {"_id": 1}):
        raise HTTPException(status_code=400, detail="La EPS indicada no existe")
    datos = p.model_dump()
    datos["fecha_nacimiento"] = datetime.combine(p.fecha_nacimiento, datetime.min.time())
    datos["eps_id"] = eps_oid
    return datos


@router.post("/", status_code=201)
def crear(p: PacienteIn):
    datos = preparar(p)
    try:
        nuevo_id = insertar("pacientes", datos)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Ya existe un paciente con ese documento")
    return consultar({"_id": nuevo_id})[0]


@router.get("/")
def listar(
    documento: Optional[str] = None,
    nombre: Optional[str] = None,
    ciudad: Optional[str] = None,
    eps_id: Optional[str] = None,
):
    filtro = {}
    if documento:
        filtro["numero_documento"] = {"$regex": "^" + re.escape(documento)}
    if nombre:
        rx = {"$regex": re.escape(nombre), "$options": "i"}
        filtro["$or"] = [{"nombres": rx}, {"apellidos": rx}]
    if ciudad:
        filtro["ciudad"] = {"$regex": re.escape(ciudad), "$options": "i"}
    if eps_id:
        filtro["eps_id"] = validar_id(eps_id)
    return consultar(filtro)


@router.get("/{id}")
def obtener(id: str):
    res = consultar({"_id": validar_id(id)})
    if not res:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return res[0]


@router.put("/{id}")
def actualizar(id: str, p: PacienteIn):
    oid = validar_id(id)
    datos = preparar(p)
    try:
        res = db.pacientes.update_one({"_id": oid}, {"$set": datos})
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Ya existe un paciente con ese documento")
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return consultar({"_id": oid})[0]


@router.delete("/{id}")
def eliminar(id: str):
    oid = validar_id(id)
    if db.triajes.count_documents({"paciente_id": oid}) > 0:
        raise HTTPException(status_code=409, detail="No se puede eliminar: el paciente tiene triajes registrados")
    res = db.pacientes.delete_one({"_id": oid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return {"mensaje": "Paciente eliminado"}