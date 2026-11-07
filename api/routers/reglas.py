from typing import List, Literal, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator
from database import db
from utils import a_json, validar_id, insertar

router = APIRouter(prefix="/api/reglas", tags=["Reglas de clasificación"])


class ReglaIn(BaseModel):
    tipo: Literal["umbral", "critico", "combinacion"]
    nivel: int = Field(ge=2, le=3)
    puntaje_minimo: Optional[int] = Field(default=None, ge=1)
    sintomas_ids: List[int] = []
    descripcion: str
    activa: bool = True

    @model_validator(mode="after")
    def revisar(self):
        if self.tipo == "umbral":
            if self.puntaje_minimo is None:
                raise ValueError("Una regla de umbral requiere puntaje_minimo")
            if self.sintomas_ids:
                raise ValueError("Una regla de umbral no lleva síntomas")
        if self.tipo == "critico":
            if self.nivel != 3:
                raise ValueError("Una regla crítica siempre fuerza nivel 3")
            if len(self.sintomas_ids) < 1:
                raise ValueError("Una regla crítica requiere al menos 1 síntoma")
        if self.tipo == "combinacion":
            if len(set(self.sintomas_ids)) < 2:
                raise ValueError("Una combinación requiere al menos 2 síntomas")
        return self


def consultar(filtro: dict):
    """Devuelve las reglas con los nombres de sus síntomas ($lookup)."""
    pipeline = [
        {"$match": filtro},
        {"$lookup": {"from": "sintomas", "localField": "sintomas_ids",
                     "foreignField": "_id", "as": "sintomas"}},
        {"$addFields": {"sintomas_nombres": "$sintomas.nombre"}},
        {"$project": {"sintomas": 0}},
    ]
    return [a_json(d) for d in db.reglas_clasificacion.aggregate(pipeline)]


def preparar(r: ReglaIn, id_actual=None):
    datos = r.model_dump()
    oids = [validar_id(i) for i in dict.fromkeys(r.sintomas_ids)]
    if oids and db.sintomas.count_documents({"_id": {"$in": oids}}) != len(oids):
        raise HTTPException(status_code=400, detail="Alguno de los síntomas indicados no existe")
    datos["sintomas_ids"] = oids
    if r.tipo == "umbral" and r.activa:
        filtro = {"tipo": "umbral", "nivel": r.nivel, "activa": True}
        if id_actual:
            filtro["_id"] = {"$ne": id_actual}
        if db.reglas_clasificacion.count_documents(filtro) > 0:
            raise HTTPException(status_code=409, detail="Ya hay una regla de umbral activa para ese nivel")
    return datos


@router.post("/", status_code=201)
def crear(r: ReglaIn):
    datos = preparar(r)
    res = nuevo_id = insertar("reglas_clasificacion", datos)
    return consultar({"_id": nuevo_id})[0]


@router.get("/")
def listar(
    tipo: Optional[str] = None,
    nivel: Optional[int] = None,
    activa: Optional[bool] = None,
):
    filtro = {}
    if tipo:
        filtro["tipo"] = tipo
    if nivel:
        filtro["nivel"] = nivel
    if activa is not None:
        filtro["activa"] = activa
    return consultar(filtro)


@router.get("/{id}")
def obtener(id: str):
    res = consultar({"_id": validar_id(id)})
    if not res:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    return res[0]


@router.put("/{id}")
def actualizar(id: str, r: ReglaIn):
    oid = validar_id(id)
    datos = preparar(r, id_actual=oid)
    res = db.reglas_clasificacion.update_one({"_id": oid}, {"$set": datos})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    return consultar({"_id": oid})[0]


@router.delete("/{id}")
def eliminar(id: str):
    oid = validar_id(id)
    if db.triajes.count_documents({"reglas_aplicadas": oid}) > 0:
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: la regla fue aplicada en triajes. Desactívala con activa=false",
        )
    res = db.reglas_clasificacion.delete_one({"_id": oid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    return {"mensaje": "Regla eliminada"}