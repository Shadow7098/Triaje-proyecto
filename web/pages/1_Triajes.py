from datetime import datetime, time

import pandas as pd
import streamlit as st

import api

st.set_page_config(page_title="Triajes", layout="wide")
from estilos import aplicar_estilos, colorear_nivel, aviso_nivel
aplicar_estilos()
st.title("Triajes")

NIVELES = {1: "1 - Normal", 2: "2 - Media", 3: "3 - Urgente"}


@st.cache_data(ttl=60)
def cargar(ruta):
    return api.get(ruta)


try:
    pacientes = cargar("/api/pacientes/")
    ips_lista = cargar("/api/ips/")
    sintomas = cargar("/api/sintomas/")
    reglas = cargar("/api/reglas/")
except Exception as e:
    st.error(f"No se pudo consultar la API: {e}")
    st.stop()

pac_por_id = {p["_id"]: p for p in pacientes}
ips_por_id = {i["_id"]: i for i in ips_lista}
sin_por_id = {s["_id"]: s for s in sintomas}
reglas_por_id = {r["_id"]: r for r in reglas}


def nombre_paciente(i):
    p = pac_por_id[i]
    return f"{p['nombres']} {p['apellidos']} - {p['tipo_documento']} {p['numero_documento']}"


def nombre_ips(i):
    return f"{ips_por_id[i]['nombre']} ({ips_por_id[i]['ciudad']})"


tab_nuevo, tab_consulta = st.tabs(["Nuevo triaje", "Consultar triajes"])

# ---------------------------------------------------------------- Nuevo triaje
with tab_nuevo:
    st.subheader("Registrar un triaje")
    c1, c2, c3 = st.columns(3)
    paciente_id = c1.selectbox("Paciente", list(pac_por_id), format_func=nombre_paciente)
    ips_id = c2.selectbox("IPS", list(ips_por_id), format_func=nombre_ips)
    canal = c3.selectbox("Canal", ["Chatbot", "Cuestionario"])

    elegidos = st.multiselect(
        "Síntomas reportados", list(sin_por_id),
        format_func=lambda i: f"{sin_por_id[i]['nombre']} (alerta {sin_por_id[i]['nivel_alerta']})",
    )
    reportes = []
    for sid in elegidos:
        a, b, c = st.columns([2, 2, 2])
        a.markdown(f"**{sin_por_id[sid]['nombre']}**")
        intensidad = b.slider("Intensidad (1-10)", 1, 10, 5, key=f"int_{sid}")
        horas = c.number_input("Duración (horas)", min_value=1, value=6, step=1, key=f"dur_{sid}")
        reportes.append({"sintoma_id": sid, "intensidad": intensidad, "duracion_horas": int(horas)})

    if st.button("Registrar triaje", type="primary"):
        if not reportes:
            st.warning("Selecciona al menos un síntoma.")
        else:
            try:
                t = api.post("/api/triajes/", {
                    "paciente_id": paciente_id, "ips_id": ips_id,
                    "canal": canal, "sintomas": reportes,
                })
                aviso_nivel(t["nivel_asignado"],
            f"Triaje {t['_id']} registrado para {t['paciente_nombre']}: "
            f"{NIVELES[t['nivel_asignado']]}")
                m1, m2 = st.columns(2)
                m1.metric("Nivel asignado", NIVELES[t["nivel_asignado"]])
                m2.metric("Puntaje total", t["puntaje_total"])
                if t["reglas_aplicadas"]:
                    st.write("Reglas aplicadas:")
                    for rid in t["reglas_aplicadas"]:
                        st.write(f"- {reglas_por_id.get(rid, {}).get('descripcion', rid)}")
            except api.ApiError as e:
                st.error(str(e))

# ----------------------------------------------------------- Consultar triajes
with tab_consulta:
    st.subheader("Buscar triajes")
    f1, f2, f3 = st.columns(3)
    nivel = f1.selectbox("Nivel", [None, 1, 2, 3],
                         format_func=lambda n: "Todos" if n is None else NIVELES[n])
    estado = f2.selectbox("Estado", [None, "true", "false"],
                          format_func=lambda v: {None: "Todos", "true": "Atendidos",
                                                 "false": "Sin atención"}[v])
    ips_f = f3.selectbox("IPS", [None] + list(ips_por_id), key="ips_filtro",
                         format_func=lambda i: "Todas" if i is None else nombre_ips(i))
    g1, g2, g3 = st.columns(3)
    pac_f = g1.selectbox("Paciente", [None] + list(pac_por_id), key="pac_filtro",
                         format_func=lambda i: "Todos" if i is None else nombre_paciente(i))
    desde = g2.date_input("Desde", value=None)
    hasta = g3.date_input("Hasta", value=None)
    limite = st.slider("Máximo de resultados", 10, 200, 50)

    if st.button("Buscar", type="primary") or "triajes_res" not in st.session_state:
        try:
            st.session_state["triajes_res"] = api.get(
                "/api/triajes/", nivel=nivel, atendido=estado, ips_id=ips_f,
                paciente_id=pac_f, limite=limite,
                desde=datetime.combine(desde, time.min).isoformat() if desde else None,
                hasta=datetime.combine(hasta, time.max).isoformat() if hasta else None,
            )
        except api.ApiError as e:
            st.error(str(e))
            st.session_state["triajes_res"] = []

    res = st.session_state.get("triajes_res", [])
    st.caption(f"{len(res)} triajes encontrados")
    if res:
        filas = [{
            "Triaje": t["_id"],
            "Fecha": t["fecha_hora"][:16].replace("T", " "),
            "Paciente": t["paciente_nombre"],
            "IPS": t["ips_nombre"],
            "Canal": t["canal"],
            "Nivel": NIVELES[t["nivel_asignado"]],
            "Puntaje": t["puntaje_total"],
            "Resultado": t.get("atencion", {}).get("resultado", "Sin atención"),
            "Médico": t.get("medico_nombre") or "",
        } for t in res]
        st.dataframe(pd.DataFrame(filas).style.map(colorear_nivel, subset=["Nivel"]),
             hide_index=True, width="stretch")

        st.divider()
        sel = st.selectbox("Ver detalle del triaje", [t["_id"] for t in res])
        t = next(x for x in res if x["_id"] == sel)
        st.markdown(f"**Triaje {t['_id']}** - {t['paciente_nombre']} - {NIVELES[t['nivel_asignado']]}")
        df_s = pd.DataFrame(t["sintomas"])[
            ["nombre", "categoria", "nivel_alerta", "intensidad", "duracion_horas"]
        ].rename(columns={"nombre": "Síntoma", "categoria": "Categoría",
                          "nivel_alerta": "Alerta", "intensidad": "Intensidad",
                          "duracion_horas": "Horas"})
        st.dataframe(df_s, hide_index=True, width="stretch")
        if t["reglas_aplicadas"]:
            st.write("Reglas aplicadas: " + "; ".join(
                reglas_por_id.get(r, {}).get("descripcion", str(r)) for r in t["reglas_aplicadas"]))
        a = t.get("atencion")
        if a:
            st.write(f"Atención: {a['resultado']} - {a['diagnostico']['codigo_cie10']} "
                     f"{a['diagnostico']['descripcion']} ({a['duracion_minutos']} min, "
                     f"{t.get('medico_nombre')})")
        else:
            st.info("Este triaje aún no tiene atención registrada.")