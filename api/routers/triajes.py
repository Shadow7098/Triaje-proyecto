from datetime import datetime, timedelta
from typing import List, Literal, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from database import db
from services.clasificacion import clasificar
from utils import a_json, a_utc, ahora, insertar, validar_id

router = APIRouter(prefix="/api/triajes", tags=["Triajes"])


class SintomaReporte(BaseModel):
    sintoma_id: int
    intensidad: int = Field(ge=1, le=10)
    duracion_horas: int = Field(ge=1)


class TriajeIn(BaseModel):
    paciente_id: int
    ips_id: int
    canal: Literal["Chatbot", "Cuestionario"]
    fecha_hora: Optional[datetime] = None
    sintomas: List[SintomaReporte] = Field(min_length=1, max_length=10)


class DiagnosticoIn(BaseModel):
    codigo_cie10: str
    descripcion: str


class AtencionIn(BaseModel):
    medico_id: int
    fecha_hora_inicio: Optional[datetime] = None
    duracion_minutos: int = Field(ge=1)
    resultado: Literal["Alta", "Remision", "Hospitalizacion"]
    diagnostico: DiagnosticoIn


def consultar(filtro: dict, limite: Optional[int] = None):
    """Triajes con nombres de paciente, IPS y médico ($lookup)."""
    pipeline = [{"$match": filtro}, {"$sort": {"fecha_hora": -1}}]
    if limite:
        pipeline.append({"$limit": limite})
    pipeline += [
        {"$lookup": {"from": "pacientes", "localField": "paciente_id",
                     "foreignField": "_id", "as": "paciente"}},
        {"$lookup": {"from": "ips", "localField": "ips_id",
                     "foreignField": "_id", "as": "ips"}},
        {"$lookup": {"from": "medicos", "localField": "atencion.medico_id",
                     "foreignField": "_id", "as": "medico"}},
        {"$unwind": {"path": "$paciente", "preserveNullAndEmptyArrays": True}},
        {"$unwind": {"path": "$ips", "preserveNullAndEmptyArrays": True}},
        {"$unwind": {"path": "$medico", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {
            "paciente_nombre": {"$concat": ["$paciente.nombres", " ", "$paciente.apellidos"]},
            "ips_nombre": "$ips.nombre",
            "medico_nombre": {"$concat": ["$medico.nombres", " ", "$medico.apellidos"]},
        }},
        {"$project": {"paciente": 0, "ips": 0, "medico": 0}},
    ]
    return [a_json(d) for d in db.triajes.aggregate(pipeline)]


@router.post("/", status_code=201)
def crear(t: TriajeIn):
    paciente_oid = validar_id(t.paciente_id)
    ips_oid = validar_id(t.ips_id)
    if not db.pacientes.find_one({"_id": paciente_oid}, {"_id": 1}):
        raise HTTPException(status_code=400, detail="El paciente indicado no existe")
    if not db.ips.find_one({"_id": ips_oid}, {"_id": 1}):
        raise HTTPException(status_code=400, detail="La IPS indicada no existe")

    ahora_ = ahora()
    fecha = a_utc(t.fecha_hora) if t.fecha_hora else ahora_
    if fecha > ahora_ + timedelta(minutes=5):
        raise HTTPException(status_code=400, detail="La fecha del triaje no puede ser futura")

    pendiente = db.triajes.find_one({
        "paciente_id": paciente_oid,
        "atencion": {"$exists": False},
        "fecha_hora": {"$gte": fecha - timedelta(hours=24)},
    }, {"_id": 1})
    if pendiente:
        raise HTTPException(status_code=409,
                            detail="El paciente ya tiene un triaje sin atender en las últimas 24 horas")

    sintomas, puntaje, nivel, reglas = clasificar(t.sintomas)

    nuevo_id = insertar("triajes", {
        "paciente_id": paciente_oid,
        "ips_id": ips_oid,
        "fecha_hora": fecha,
        "canal": t.canal,
        "nivel_asignado": nivel,
        "puntaje_total": puntaje,
        "reglas_aplicadas": reglas,
        "sintomas": sintomas,
    })
    return consultar({"_id": nuevo_id})[0]


@router.get("/")
def listar(
    nivel: Optional[int] = Query(default=None, ge=1, le=3),
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    ips_id: Optional[str] = None,
    paciente_id: Optional[str] = None,
    atendido: Optional[bool] = None,
    limite: int = Query(default=50, ge=1, le=200),
):
    filtro = {}
    if nivel:
        filtro["nivel_asignado"] = nivel
    if desde or hasta:
        filtro["fecha_hora"] = {}
        if desde:
            filtro["fecha_hora"]["$gte"] = a_utc(desde)
        if hasta:
            filtro["fecha_hora"]["$lte"] = a_utc(hasta)
    if ips_id:
        filtro["ips_id"] = validar_id(ips_id)
    if paciente_id:
        filtro["paciente_id"] = validar_id(paciente_id)
    if atendido is not None:
        filtro["atencion"] = {"$exists": atendido}
    return consultar(filtro, limite)


@router.get("/{id}")
def obtener(id: str):
    res = consultar({"_id": validar_id(id)})
    if not res:
        raise HTTPException(status_code=404, detail="Triaje no encontrado")
    return res[0]


@router.patch("/{id}/atencion")
def registrar_atencion(id: str, a: AtencionIn):
    oid = validar_id(id)
    triaje = db.triajes.find_one({"_id": oid})
    if not triaje:
        raise HTTPException(status_code=404, detail="Triaje no encontrado")
    if "atencion" in triaje:
        raise HTTPException(status_code=409, detail="El triaje ya tiene una atención registrada")

    medico = db.medicos.find_one({"_id": validar_id(a.medico_id)})
    if not medico:
        raise HTTPException(status_code=400, detail="El médico indicado no existe")
    if medico["ips_id"] != triaje["ips_id"]:
        raise HTTPException(status_code=409, detail="El médico pertenece a otra IPS")

    inicio = a_utc(a.fecha_hora_inicio) if a.fecha_hora_inicio else ahora()
    if inicio < triaje["fecha_hora"]:
        raise HTTPException(status_code=400, detail="La atención no puede iniciar antes del triaje")

    res = db.triajes.update_one(
        {"_id": oid, "atencion": {"$exists": False}},
        {"$set": {"atencion": {
            "medico_id": medico["_id"],
            "fecha_hora_inicio": inicio,
            "duracion_minutos": a.duracion_minutos,
            "resultado": a.resultado,
            "diagnostico": a.diagnostico.model_dump(),
        }}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=409, detail="El triaje ya tiene una atención registrada")
    return consultar({"_id": oid})[0]


@router.delete("/{id}")
def eliminar(id: str):
    oid = validar_id(id)
    triaje = db.triajes.find_one({"_id": oid}, {"atencion": 1})
    if not triaje:
        raise HTTPException(status_code=404, detail="Triaje no encontrado")
    if "atencion" in triaje:
        raise HTTPException(status_code=409, detail="No se puede eliminar: el triaje ya tiene atención registrada")
    if db.reevaluaciones.count_documents({"triaje_id": oid}) > 0:
        raise HTTPException(status_code=409, detail="No se puede eliminar: el triaje tiene reevaluaciones")
    db.triajes.delete_one({"_id": oid})
    return {"mensaje": "Triaje eliminado"}