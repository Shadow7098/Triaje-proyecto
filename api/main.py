from fastapi import FastAPI
from database import client, db
from routers import eps, ips, sintomas, medicos, pacientes, reglas, triajes, reevaluaciones, reportes

app = FastAPI(title="API Triaje IPS")

# Índices
db.eps.create_index("nit", unique=True)
db.ips.create_index([("nombre", 1), ("ciudad", 1)], unique=True)
db.sintomas.create_index("nombre", unique=True)
db.medicos.create_index("registro_medico", unique=True)
db.pacientes.create_index([("tipo_documento", 1), ("numero_documento", 1)], unique=True)
db.triajes.create_index([("nivel_asignado", 1), ("fecha_hora", -1)])
db.triajes.create_index("paciente_id")
db.reevaluaciones.create_index("triaje_id")

for r in (eps, ips, sintomas, medicos, pacientes, reglas, triajes, reevaluaciones, reportes):
    app.include_router(r.router)


@app.get("/salud")
def salud():
    client.admin.command("ping")
    return {"estado": "ok", "base_de_datos": db.name}