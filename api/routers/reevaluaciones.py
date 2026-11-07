from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from database import client, db
from utils import a_json, a_utc, ahora, insertar, validar_id

router = APIRouter(prefix="/api/reevaluaciones", tags=["Reevaluaciones"])


class ReevaluacionIn(BaseModel):
    triaje_id: int
    nivel_nuevo: int = Field(ge=2, le=3)
    motivo: str = Field(min_length=5)
    fecha_hora: Optional[datetime] = None


def consultar(filtro: dict):
    """Reevaluaciones con el nombre del paciente y el puntaje del triaje."""
    pipeline = [
        {"$match": filtro},
        {"$sort": {"fecha_hora": -1}},
        {"$lookup": {"from": "triajes", "localField": "triaje_id",
                     "foreignField": "_id", "as": "triaje"}},
        {"$unwind": {"path": "$triaje", "preserveNullAndEmptyArrays": True}},
        {"$lookup": {"from": "pacientes", "localField": "triaje.paciente_id",
                     "foreignField": "_id", "as": "paciente"}},
        {"$unwind": {"path": "$paciente", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {
            "paciente_nombre": {"$concat": ["$paciente.nombres", " ", "$paciente.apellidos"]},
            "puntaje_total": "$triaje.puntaje_total",
        }},
        {"$project": {"triaje": 0, "paciente": 0}},
    ]
    return [a_json(d) for d in db.reevaluaciones.aggregate(pipeline)]


@router.post("/", status_code=201)
def crear(r: ReevaluacionIn):
    triaje_oid = validar_id(r.triaje_id)
    triaje = db.triajes.find_one({"_id": triaje_oid})
    if not triaje:
        raise HTTPException(status_code=400, detail="El triaje indicado no existe")
    if "atencion" in triaje:
        raise HTTPException(status_code=409, detail="El triaje ya fue atendido; no se puede reevaluar")

    nivel_anterior = triaje["nivel_asignado"]
    if r.nivel_nuevo <= nivel_anterior:
        raise HTTPException(
            status_code=400,
            detail=f"La reevaluación solo puede subir el nivel (nivel actual: {nivel_anterior})",
        )

    ahora_ = ahora()
    fecha = a_utc(r.fecha_hora) if r.fecha_hora else ahora_
    if fecha > ahora_ + timedelta(minutes=5):
        raise HTTPException(status_code=400, detail="La fecha de la reevaluación no puede ser futura")
    if fecha < triaje["fecha_hora"]:
        raise HTTPException(status_code=400, detail="La reevaluación no puede ser anterior al triaje")

    doc = {
        "triaje_id": triaje_oid,
        "fecha_hora": fecha,
        "nivel_anterior": nivel_anterior,
        "nivel_nuevo": r.nivel_nuevo,
        "motivo": r.motivo,
    }

    def aplicar(sesion):
        res = db.triajes.update_one(
            {"_id": triaje_oid, "nivel_asignado": nivel_anterior,
             "atencion": {"$exists": False}},
            {"$set": {"nivel_asignado": r.nivel_nuevo}},
            session=sesion,
        )
        if res.modified_count == 0:
            raise HTTPException(status_code=409,
                                detail="El triaje cambió mientras se procesaba; intenta de nuevo")
        return insertar("reevaluaciones", doc, session=sesion)

    with client.start_session() as sesion:
        nuevo_id = sesion.with_transaction(aplicar)
    return consultar({"_id": nuevo_id})[0]


@router.get("/")
def listar(
    triaje_id: Optional[str] = None,
    nivel_nuevo: Optional[int] = Query(default=None, ge=2, le=3),
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
):
    filtro = {}
    if triaje_id:
        filtro["triaje_id"] = validar_id(triaje_id)
    if nivel_nuevo:
        filtro["nivel_nuevo"] = nivel_nuevo
    if desde or hasta:
        filtro["fecha_hora"] = {}
        if desde:
            filtro["fecha_hora"]["$gte"] = a_utc(desde)
        if hasta:
            filtro["fecha_hora"]["$lte"] = a_utc(hasta)
    return consultar(filtro)


@router.get("/{id}")
def obtener(id: str):
    res = consultar({"_id": validar_id(id)})
    if not res:
        raise HTTPException(status_code=404, detail="Reevaluación no encontrada")
    return res[0]