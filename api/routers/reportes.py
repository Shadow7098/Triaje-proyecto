from typing import Optional
from fastapi import APIRouter, Query
from database import db
from utils import a_json

router = APIRouter(prefix="/api/reportes", tags=["Reportes"])


def lk(coleccion, campo_local, alias):
    return {"$lookup": {"from": coleccion, "localField": campo_local,
                        "foreignField": "_id", "as": alias}}


def nombre(alias):
    return {"$concat": [f"${alias}.nombres", " ", f"${alias}.apellidos"]}


def ejecutar(pipeline):
    return [a_json(d) for d in db.triajes.aggregate(pipeline)]


@router.get("/urgentes-sin-atencion")
def urgentes_sin_atencion(limite: int = Query(default=20, ge=1, le=100)):
    """Casos de nivel 3 que aún no tienen atención, con el tiempo que llevan esperando."""
    return ejecutar([
        {"$match": {"nivel_asignado": 3, "atencion": {"$exists": False}}},
        {"$sort": {"fecha_hora": -1}},
        {"$limit": limite},
        lk("pacientes", "paciente_id", "paciente"),
        lk("ips", "ips_id", "ips"),
        {"$unwind": "$paciente"},
        {"$unwind": "$ips"},
        {"$project": {
            "fecha_hora": 1, "puntaje_total": 1, "canal": 1,
            "paciente_nombre": nombre("paciente"),
            "telefono": "$paciente.telefono",
            "ips": "$ips.nombre", "ciudad": "$ips.ciudad",
            "minutos_esperando": {"$dateDiff": {
                "startDate": "$fecha_hora", "endDate": "$$NOW", "unit": "minute"}},
        }},
    ])


@router.get("/espera-por-nivel")
def espera_por_nivel(nivel: Optional[int] = Query(default=None, ge=1, le=3)):
    """Minutos entre el triaje y el inicio de la atención, por nivel e IPS."""
    filtro = {"atencion": {"$exists": True}}
    if nivel:
        filtro["nivel_asignado"] = nivel
    return ejecutar([
        {"$match": filtro},
        {"$addFields": {"espera_min": {"$dateDiff": {
            "startDate": "$fecha_hora", "endDate": "$atencion.fecha_hora_inicio",
            "unit": "minute"}}}},
        {"$group": {
            "_id": {"nivel": "$nivel_asignado", "ips_id": "$ips_id"},
            "triajes": {"$sum": 1},
            "espera_promedio_min": {"$avg": "$espera_min"},
            "espera_maxima_min": {"$max": "$espera_min"}}},
        lk("ips", "_id.ips_id", "ips"),
        {"$unwind": "$ips"},
        {"$project": {
            "_id": 0, "nivel": "$_id.nivel", "ips": "$ips.nombre",
            "ciudad": "$ips.ciudad", "triajes": 1,
            "espera_promedio_min": {"$round": ["$espera_promedio_min", 1]},
            "espera_maxima_min": 1}},
        {"$sort": {"nivel": -1, "espera_promedio_min": -1}},
    ])


@router.get("/sintomas-frecuentes")
def sintomas_frecuentes(
    nivel_triaje: Optional[int] = Query(default=None, ge=1, le=3),
    nivel_alerta: Optional[int] = Query(default=None, ge=1, le=3),
    limite: int = Query(default=10, ge=1, le=50),
):
    """Síntomas más reportados con su intensidad promedio.
    nivel_triaje: solo triajes de ese nivel. nivel_alerta: solo síntomas con esa alerta."""
    filtro = {"nivel_asignado": nivel_triaje} if nivel_triaje else {}
    pipeline = [{"$match": filtro}, {"$unwind": "$sintomas"}]
    if nivel_alerta:
        pipeline.append({"$match": {"sintomas.nivel_alerta": nivel_alerta}})
    pipeline += [
        {"$group": {
            "_id": "$sintomas.nombre",
            "categoria": {"$first": "$sintomas.categoria"},
            "nivel_alerta": {"$first": "$sintomas.nivel_alerta"},
            "veces": {"$sum": 1},
            "intensidad_promedio": {"$avg": "$sintomas.intensidad"}}},
        {"$sort": {"veces": -1}},
        {"$limit": limite},
        {"$project": {
            "_id": 0, "sintoma": "$_id", "categoria": 1, "nivel_alerta": 1,
            "veces": 1,
            "intensidad_promedio": {"$round": ["$intensidad_promedio", 1]}}},
    ]
    return ejecutar(pipeline)


@router.get("/eps-urgentes")
def eps_urgentes():
    """EPS con más casos de nivel 3 y cuántos siguen sin atención."""
    return ejecutar([
        {"$match": {"nivel_asignado": 3}},
        lk("pacientes", "paciente_id", "paciente"),
        {"$unwind": "$paciente"},
        {"$group": {
            "_id": "$paciente.eps_id",
            "casos_urgentes": {"$sum": 1},
            "sin_atencion": {"$sum": {"$cond": [
                {"$eq": [{"$type": "$atencion"}, "missing"]}, 1, 0]}}}},
        lk("eps", "_id", "eps"),
        {"$unwind": "$eps"},
        {"$project": {
            "_id": 0, "eps": "$eps.nombre", "regimen": "$eps.regimen",
            "casos_urgentes": 1, "sin_atencion": 1}},
        {"$sort": {"casos_urgentes": -1}},
    ])


@router.get("/subclasificados")
def subclasificados(limite: int = Query(default=10, ge=1, le=50)):
    """Hospitalizados cuyo nivel INICIAL fue menor a 3 (posible subclasificación).
    El nivel inicial es el nivel_anterior de la primera reevaluación o, si no hubo, el vigente."""
    return ejecutar([
        {"$match": {"atencion.resultado": "Hospitalizacion"}},
        {"$lookup": {
            "from": "reevaluaciones", "let": {"tid": "$_id"},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$triaje_id", "$$tid"]}}},
                {"$sort": {"fecha_hora": 1}}],
            "as": "reevaluaciones"}},
        {"$addFields": {"nivel_inicial": {"$ifNull": [
            {"$arrayElemAt": ["$reevaluaciones.nivel_anterior", 0]}, "$nivel_asignado"]}}},
        {"$match": {"nivel_inicial": {"$lt": 3}}},
        {"$sort": {"puntaje_total": -1}},
        {"$limit": limite},
        lk("pacientes", "paciente_id", "paciente"),
        {"$unwind": "$paciente"},
        {"$project": {
            "fecha_hora": 1, "puntaje_total": 1,
            "paciente_nombre": nombre("paciente"),
            "nivel_inicial": 1, "nivel_final": "$nivel_asignado",
            "fue_reevaluado": {"$gt": [{"$size": "$reevaluaciones"}, 0]},
            "diagnostico": "$atencion.diagnostico.descripcion"}},
    ])


@router.get("/reincidentes")
def reincidentes(
    dias: int = Query(default=30, ge=1, le=365),
    minimo: int = Query(default=3, ge=2, le=20),
):
    """Pacientes con al menos `minimo` triajes dentro de una ventana de `dias` días."""
    return ejecutar([
        {"$setWindowFields": {
            "partitionBy": "$paciente_id",
            "sortBy": {"fecha_hora": 1},
            "output": {"triajes_en_ventana": {
                "$count": {}, "window": {"range": [-dias, "current"], "unit": "day"}}}}},
        {"$match": {"triajes_en_ventana": {"$gte": minimo}}},
        {"$group": {
            "_id": "$paciente_id",
            "maximo_en_ventana": {"$max": "$triajes_en_ventana"},
            "ultimo_triaje": {"$max": "$fecha_hora"}}},
        lk("pacientes", "_id", "paciente"),
        {"$unwind": "$paciente"},
        {"$project": {
            "_id": 0, "paciente_id": "$_id",
            "paciente_nombre": nombre("paciente"),
            "documento": "$paciente.numero_documento",
            "maximo_en_ventana": 1, "ultimo_triaje": 1}},
        {"$sort": {"maximo_en_ventana": -1, "ultimo_triaje": -1}},
    ])


@router.get("/reclasificaciones")
def reclasificaciones():
    """Cuántos casos subieron de nivel, y cuánto tardaron en empeorar y en ser atendidos."""
    return [a_json(d) for d in db.reevaluaciones.aggregate([
        lk("triajes", "triaje_id", "triaje"),
        {"$unwind": "$triaje"},
        {"$addFields": {
            "min_hasta_reeval": {"$dateDiff": {
                "startDate": "$triaje.fecha_hora", "endDate": "$fecha_hora",
                "unit": "minute"}},
            "min_reeval_a_atencion": {"$dateDiff": {
                "startDate": "$fecha_hora",
                "endDate": "$triaje.atencion.fecha_hora_inicio", "unit": "minute"}}}},
        {"$group": {
            "_id": {"de": "$nivel_anterior", "a": "$nivel_nuevo"},
            "casos": {"$sum": 1},
            "prom_hasta_reevaluacion": {"$avg": "$min_hasta_reeval"},
            "prom_reevaluacion_a_atencion": {"$avg": "$min_reeval_a_atencion"}}},
        {"$project": {
            "_id": 0, "de_nivel": "$_id.de", "a_nivel": "$_id.a", "casos": 1,
            "minutos_hasta_reevaluacion": {"$round": ["$prom_hasta_reevaluacion", 1]},
            "minutos_reevaluacion_a_atencion": {"$round": ["$prom_reevaluacion_a_atencion", 1]}}},
        {"$sort": {"de_nivel": 1, "a_nivel": 1}},
    ])]


@router.get("/carga-medicos")
def carga_medicos(limite: int = Query(default=10, ge=1, le=50)):
    """Atenciones por médico, con duración promedio, hospitalizaciones y casos urgentes."""
    return ejecutar([
        {"$match": {"atencion": {"$exists": True}}},
        {"$group": {
            "_id": "$atencion.medico_id",
            "atenciones": {"$sum": 1},
            "duracion_promedio_min": {"$avg": "$atencion.duracion_minutos"},
            "hospitalizaciones": {"$sum": {"$cond": [
                {"$eq": ["$atencion.resultado", "Hospitalizacion"]}, 1, 0]}},
            "urgentes": {"$sum": {"$cond": [{"$eq": ["$nivel_asignado", 3]}, 1, 0]}}}},
        lk("medicos", "_id", "medico"),
        {"$unwind": "$medico"},
        lk("ips", "medico.ips_id", "ips"),
        {"$unwind": "$ips"},
        {"$project": {
            "_id": 0, "medico_id": "$_id", "medico": nombre("medico"),
            "especialidad": "$medico.especialidad.nombre", "ips": "$ips.nombre",
            "atenciones": 1, "hospitalizaciones": 1, "urgentes": 1,
            "duracion_promedio_min": {"$round": ["$duracion_promedio_min", 1]}}},
        {"$sort": {"atenciones": -1}},
        {"$limit": limite},
    ])