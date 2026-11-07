from fastapi import HTTPException
from database import db
from utils import validar_id


def clasificar(reportes):
    """Calcula el puntaje y el nivel de un triaje.
    Devuelve (sintomas_embebidos, puntaje_total, nivel, reglas_aplicadas)."""
    ids = [validar_id(r.sintoma_id) for r in reportes]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=400, detail="Hay síntomas repetidos en el triaje")

    catalogo = {s["_id"]: s for s in db.sintomas.find({"_id": {"$in": ids}})}
    if len(catalogo) != len(ids):
        raise HTTPException(status_code=400, detail="Alguno de los síntomas indicados no existe")

    sintomas = []
    puntaje_total = 0
    for r, oid in zip(reportes, ids):
        s = catalogo[oid]
        puntaje_total += s["nivel_alerta"] * r.intensidad
        sintomas.append({
            "sintoma_id": oid,
            "nombre": s["nombre"],
            "categoria": s["categoria"],
            "nivel_alerta": s["nivel_alerta"],
            "intensidad": r.intensidad,
            "duracion_horas": r.duracion_horas,
        })

    reportados = set(ids)
    nivel = 1
    reglas_aplicadas = []
    reglas = list(db.reglas_clasificacion.find({"activa": True}))

    # 1. Umbral: se aplica el de mayor nivel que alcance el puntaje
    umbrales = [r for r in reglas
                if r["tipo"] == "umbral" and puntaje_total >= r["puntaje_minimo"]]
    if umbrales:
        mejor = max(umbrales, key=lambda r: r["nivel"])
        nivel = max(nivel, mejor["nivel"])
        reglas_aplicadas.append(mejor["_id"])

    # 2. Críticas (basta un síntoma) y combinaciones (deben estar todos)
    for r in reglas:
        sids = set(r.get("sintomas_ids", []))
        if r["tipo"] == "critico" and sids & reportados:
            nivel = max(nivel, r["nivel"])
            reglas_aplicadas.append(r["_id"])
        elif r["tipo"] == "combinacion" and sids and sids <= reportados:
            nivel = max(nivel, r["nivel"])
            reglas_aplicadas.append(r["_id"])

    return sintomas, puntaje_total, nivel, reglas_aplicadas