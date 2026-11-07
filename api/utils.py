from datetime import datetime, timezone
from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument
from database import db


def _convertir(v):
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, dict):
        return {k: _convertir(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_convertir(x) for x in v]
    return v


def a_json(doc):
    return _convertir(doc)


def validar_id(id):
    try:
        valor = int(id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="ID inválido")
    if valor < 1:
        raise HTTPException(status_code=400, detail="ID inválido")
    return valor


def siguiente_id(coleccion):
    """Contador autoincremental por colección: 1, 2, 3...
    Si el contador está atrasado respecto al mayor _id existente, se corrige solo."""
    ultimo = db[coleccion].find_one({}, {"_id": 1}, sort=[("_id", -1)])
    maximo = ultimo["_id"] if ultimo else 0
    doc = db.contadores.find_one_and_update(
        {"_id": coleccion},
        [{"$set": {"seq": {"$add": [{"$max": [{"$ifNull": ["$seq", 0]}, maximo]}, 1]}}}],
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return doc["seq"]


def insertar(coleccion, datos, session=None):
    nuevo_id = siguiente_id(coleccion)
    db[coleccion].insert_one({"_id": nuevo_id, **datos}, session=session)
    return nuevo_id


def ahora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def a_utc(dt):
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt