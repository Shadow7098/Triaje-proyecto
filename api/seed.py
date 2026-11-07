"""Genera datos de prueba. Ejecutar desde la carpeta api:  python seed.py
ATENCION: borra el contenido de todas las colecciones y lo vuelve a crear."""
import random
from collections import Counter
from datetime import timedelta
from types import SimpleNamespace

from database import db
from services.clasificacion import clasificar
from utils import ahora

random.seed(42)
AHORA = ahora().replace(second=0, microsecond=0)

COLECCIONES = ["eps", "ips", "sintomas", "medicos", "pacientes",
               "reglas_clasificacion", "triajes", "reevaluaciones", "contadores"]
for c in COLECCIONES:
    db[c].delete_many({})

# ---------- Catálogos ----------
EPS = [
    ("EPS Vida Plena", "900111222-1", "Contributivo"),
    ("EPS Mutual Andina", "900329258-3", "Contributivo"),
    ("EPS Integral", "900445566-7", "Contributivo"),
    ("EPS Nueva Esperanza", "900778899-0", "Subsidiado"),
    ("EPS Vida Sana", "900223344-5", "Subsidiado"),
    ("EPS Salud Común", "900556677-2", "Subsidiado"),
]
eps_docs = [{"_id": i, "nombre": n, "nit": nit, "regimen": r}
            for i, (n, nit, r) in enumerate(EPS, start=1)]

IPS = [
    ("IPS Clínica del Norte", "Medellín", "Calle 4 # 72-26", 3, 60),
    ("IPS Hospital Santander", "Bucaramanga", "Carrera 27 # 15-30", 3, 45),
    ("IPS Clínica del Valle", "Cali", "Avenida 6N # 28-10", 4, 80),
    ("IPS Clínica Marina", "Barranquilla", "Calle 76 # 54-20", 3, 50),
    ("IPS Centro Médico Andino", "Bogotá", "Carrera 15 # 93-40", 4, 90),
    ("IPS Salud Familiar", "Medellín", "Carrera 43A # 10-15", 2, 25),
]
ips_docs = [{"_id": i, "nombre": n, "ciudad": c, "direccion": d,
             "nivel_complejidad": nc, "capacidad_urgencias": cu}
            for i, (n, c, d, nc, cu) in enumerate(IPS, start=1)]

SINTOMAS = [
    ("Tos seca", "Respiratorio", 1), ("Cansancio", "General", 1),
    ("Dolor de cabeza", "Neurológico", 1), ("Dolor de garganta", "Respiratorio", 1),
    ("Congestión nasal", "Respiratorio", 1), ("Náuseas", "Digestivo", 1),
    ("Diarrea", "Digestivo", 1), ("Dolor lumbar", "Musculoesquelético", 1),
    ("Dolor articular", "Musculoesquelético", 1), ("Erupción en la piel", "Piel", 1),
    ("Palpitaciones", "Cardiovascular", 2), ("Mareo", "Neurológico", 2),
    ("Fiebre alta", "Infeccioso", 2), ("Rigidez de cuello", "Neurológico", 2),
    ("Vómito persistente", "Digestivo", 2), ("Dolor abdominal intenso", "Digestivo", 2),
    ("Visión borrosa", "Neurológico", 2),
    ("Dolor de pecho", "Cardiovascular", 3), ("Dificultad para respirar", "Respiratorio", 3),
    ("Desmayo", "Cardiovascular", 3), ("Confusión", "Neurológico", 3),
    ("Convulsiones", "Neurológico", 3), ("Sangrado abundante", "General", 3),
    ("Trauma con deformidad", "Musculoesquelético", 3),
]
sintomas_docs = [{"_id": i, "nombre": n, "categoria": c, "nivel_alerta": a}
                 for i, (n, c, a) in enumerate(SINTOMAS, start=1)]
sid = {n: i for i, (n, _, _) in enumerate(SINTOMAS, start=1)}
sintomas_ids = list(sid.values())

# ---------- Reglas de clasificación ----------
def regla(i, tipo, nivel, minimo, nombres, desc):
    return {"_id": i, "tipo": tipo, "nivel": nivel, "puntaje_minimo": minimo,
            "sintomas_ids": [sid[n] for n in nombres], "descripcion": desc, "activa": True}

reglas_docs = [
    regla(1, "umbral", 2, 20, [], "Desde 20 puntos el triaje es nivel 2 (media)"),
    regla(2, "umbral", 3, 40, [], "Desde 40 puntos el triaje es nivel 3 (urgente)"),
    regla(3, "critico", 3, None, ["Dolor de pecho", "Convulsiones", "Sangrado abundante"],
          "Síntomas críticos: fuerzan nivel 3"),
    regla(4, "combinacion", 3, None, ["Fiebre alta", "Rigidez de cuello"],
          "Fiebre alta con rigidez de cuello sugiere meningitis"),
    regla(5, "combinacion", 3, None, ["Dificultad para respirar", "Fiebre alta"],
          "Dificultad respiratoria con fiebre alta sugiere neumonía grave"),
    regla(6, "combinacion", 3, None, ["Confusión", "Fiebre alta"],
          "Confusión con fiebre alta sugiere infección grave"),
    regla(7, "combinacion", 2, None, ["Vómito persistente", "Dolor abdominal intenso"],
          "Vómito persistente con dolor abdominal intenso"),
]
db.sintomas.insert_many(sintomas_docs)
db.reglas_clasificacion.insert_many(reglas_docs)

# ---------- Médicos ----------
ESPECIALIDADES = [(1, "Medicina General"), (2, "Medicina de Urgencias"), (3, "Cardiología"),
                  (4, "Neurología"), (5, "Pediatría"), (6, "Medicina Interna")]
NOMBRES = ["Laura", "Carlos", "Diana", "Andrés", "Sofía", "Juan", "Valentina", "Camilo",
           "Gabriela", "Santiago", "Luisa", "Mateo", "Paula", "Felipe", "Natalia",
           "Sebastián", "Daniela", "Jorge", "Camila", "David"]
APELLIDOS = ["Gómez", "Ramírez", "Torres", "Hernández", "Giraldo", "Zapata", "Jiménez",
             "Cardona", "López", "Mejía", "Gutiérrez", "Díaz", "Henao", "Restrepo",
             "Vargas", "Ortiz", "Muñoz", "Rojas", "Castaño", "Londoño"]

medicos_docs = []
for i in range(1, 19):  # 3 médicos por IPS
    esp = random.choice(ESPECIALIDADES)
    medicos_docs.append({
        "_id": i, "nombres": random.choice(NOMBRES),
        "apellidos": f"{random.choice(APELLIDOS)} {random.choice(APELLIDOS)}",
        "registro_medico": f"RM-{10000 + i}",
        "especialidad": {"id": esp[0], "nombre": esp[1]},
        "ips_id": (i - 1) % len(IPS) + 1,
    })
medicos_por_ips = {}
for m in medicos_docs:
    medicos_por_ips.setdefault(m["ips_id"], []).append(m["_id"])

# ---------- Pacientes ----------
CIUDADES = sorted({c for _, c, _, _, _ in IPS})
pacientes_docs, usados = [], set()
for i in range(1, 121):
    nac = AHORA - timedelta(days=random.randint(365, 85 * 365))
    edad = (AHORA - nac).days // 365
    if edad < 7:
        tipo = "RC"
    elif edad < 18:
        tipo = "TI"
    else:
        tipo = "CC" if random.random() < 0.95 else "CE"
    while True:
        numero = str(random.randint(10000000, 1099999999))
        if (tipo, numero) not in usados:
            usados.add((tipo, numero))
            break
    pacientes_docs.append({
        "_id": i, "tipo_documento": tipo, "numero_documento": numero,
        "nombres": random.choice(NOMBRES),
        "apellidos": f"{random.choice(APELLIDOS)} {random.choice(APELLIDOS)}",
        "fecha_nacimiento": nac.replace(hour=0, minute=0, second=0, microsecond=0),
        "sexo": random.choice(["F", "M"]),
        "telefono": "3" + f"{random.randint(0, 999999999):09d}",
        "ciudad": random.choice(CIUDADES),
        "eps_id": random.randint(1, len(EPS)),
    })

# ---------- Triajes (el nivel lo calcula la misma función que usa la API) ----------
CIE10 = [("R07.4", "Dolor torácico no especificado"), ("J18.9", "Neumonía no especificada"),
         ("G03.9", "Meningitis, no especificada"), ("A09", "Diarrea y gastroenteritis de presunto origen infeccioso"),
         ("I20.9", "Angina de pecho, no especificada"), ("K29.7", "Gastritis, no especificada"),
         ("G43.9", "Migraña, no especificada"), ("M25.5", "Dolor articular"),
         ("J06.9", "Infección aguda de las vías respiratorias superiores"),
         ("R55", "Síncope y colapso"), ("G40.9", "Epilepsia, tipo no especificado"),
         ("S06.0", "Conmoción cerebral"), ("L50.9", "Urticaria, no especificada"),
         ("N39.0", "Infección de vías urinarias, sitio no especificado")]
ESPERA = {1: (30, 240), 2: (15, 90), 3: (5, 40)}  # minutos hasta la atención
RESULTADOS = ["Alta", "Remision", "Hospitalizacion"]
PESOS = {1: [90, 8, 2], 2: [60, 25, 15], 3: [15, 35, 50]}
MOTIVOS = ["Empeoramiento de la intensidad de los síntomas",
           "Aparición de un síntoma nuevo mientras espera",
           "Fiebre en aumento y malestar general",
           "Dolor que no cede con el tratamiento inicial",
           "Dificultad respiratoria progresiva",
           "Signos de deterioro en la valoración de enfermería"]


def reportes_aleatorios():
    n = random.choices([1, 2, 3, 4], [35, 35, 20, 10])[0]
    return [SimpleNamespace(
        sintoma_id=s,
        intensidad=random.choices(range(1, 11), weights=[3, 4, 5, 5, 5, 4, 4, 3, 2, 2])[0],
        duracion_horas=random.randint(1, 72),
    ) for s in random.sample(sintomas_ids, n)]


# 300 triajes: 8 pacientes reincidentes (3-4 triajes en menos de 30 días) y el resto al azar
planes = []
for pid in random.sample(range(1, 121), 8):
    base = AHORA - timedelta(days=random.randint(35, 70))
    for _ in range(random.choice([3, 4])):
        planes.append((pid, base + timedelta(days=random.randint(0, 25),
                                             minutes=random.randint(0, 1000))))
while len(planes) < 300:
    planes.append((random.randint(1, 120),
                   AHORA - timedelta(minutes=random.randint(30, 90 * 24 * 60))))
planes.sort(key=lambda p: p[1])

triajes_docs = []
for tid, (pid, fecha) in enumerate(planes, start=1):
    fecha = fecha.replace(second=0, microsecond=0)
    ips_id = random.randint(1, len(IPS))
    sintomas, puntaje, nivel, reglas = clasificar(reportes_aleatorios())
    doc = {"_id": tid, "paciente_id": pid, "ips_id": ips_id, "fecha_hora": fecha,
           "canal": random.choice(["Chatbot", "Cuestionario"]),
           "nivel_asignado": nivel, "puntaje_total": puntaje,
           "reglas_aplicadas": reglas, "sintomas": sintomas}
    if random.random() < 0.9:
        inicio = fecha + timedelta(minutes=random.randint(*ESPERA[nivel]))
        if inicio < AHORA:
            cie = random.choice(CIE10)
            doc["atencion"] = {
                "medico_id": random.choice(medicos_por_ips[ips_id]),
                "fecha_hora_inicio": inicio,
                "duracion_minutos": random.randint(10, 90),
                "resultado": random.choices(RESULTADOS, PESOS[nivel])[0],
                "diagnostico": {"codigo_cie10": cie[0], "descripcion": cie[1]},
            }
    triajes_docs.append(doc)

# ---------- Reevaluaciones (antes de la atención, solo suben el nivel) ----------
candidatos = [t for t in triajes_docs
              if t["nivel_asignado"] in (1, 2) and "atencion" in t
              and (t["atencion"]["fecha_hora_inicio"] - t["fecha_hora"]).total_seconds() >= 15 * 60]
reevaluaciones_docs = []
for n, t in enumerate(random.sample(candidatos, min(30, len(candidatos))), start=1):
    minutos = int((t["atencion"]["fecha_hora_inicio"] - t["fecha_hora"]).total_seconds() // 60)
    nivel_ant = t["nivel_asignado"]
    nivel_nuevo = random.randint(nivel_ant + 1, 3)
    reevaluaciones_docs.append({
        "_id": n, "triaje_id": t["_id"],
        "fecha_hora": t["fecha_hora"] + timedelta(minutes=random.randint(5, minutos - 5)),
        "nivel_anterior": nivel_ant, "nivel_nuevo": nivel_nuevo,
        "motivo": random.choice(MOTIVOS),
    })
    t["nivel_asignado"] = nivel_nuevo
    t["atencion"]["resultado"] = random.choices(RESULTADOS, [20, 25, 55])[0]

# ---------- Carga ----------
colecciones = {
    "eps": eps_docs, "ips": ips_docs, "sintomas": sintomas_docs, "medicos": medicos_docs,
    "pacientes": pacientes_docs, "reglas_clasificacion": reglas_docs,
    "triajes": triajes_docs, "reevaluaciones": reevaluaciones_docs,
}
for nombre, docs in colecciones.items():
    if nombre not in ("sintomas", "reglas_clasificacion"):
        db[nombre].insert_many(docs)

print("Datos generados:")
for nombre, docs in colecciones.items():
    print(f"  {nombre}: {len(docs)}")
print("Triajes por nivel:", dict(sorted(Counter(t["nivel_asignado"] for t in triajes_docs).items())))
print("Triajes sin atención:", sum(1 for t in triajes_docs if "atencion" not in t))