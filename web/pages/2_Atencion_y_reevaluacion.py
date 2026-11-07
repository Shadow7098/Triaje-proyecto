import pandas as pd
import streamlit as st

import api

st.set_page_config(page_title="Atención y reevaluación", layout="wide")
from estilos import aplicar_estilos, colorear_nivel, aviso_nivel
aplicar_estilos()
st.title("Atención y reevaluación")

NIVELES = {1: "1 - Normal", 2: "2 - Media", 3: "3 - Urgente"}
RESULTADOS = ["Alta", "Remision", "Hospitalizacion"]
DIAGNOSTICOS = [
    ("R07.4", "Dolor torácico no especificado"),
    ("J18.9", "Neumonía no especificada"),
    ("G03.9", "Meningitis, no especificada"),
    ("A09", "Diarrea y gastroenteritis de presunto origen infeccioso"),
    ("I20.9", "Angina de pecho, no especificada"),
    ("K29.7", "Gastritis, no especificada"),
    ("G43.9", "Migraña, no especificada"),
    ("M25.5", "Dolor articular"),
    ("J06.9", "Infección aguda de las vías respiratorias superiores"),
    ("R55", "Síncope y colapso"),
    ("G40.9", "Epilepsia, tipo no especificado"),
    ("S06.0", "Conmoción cerebral"),
    ("L50.9", "Urticaria, no especificada"),
    ("N39.0", "Infección de vías urinarias, sitio no especificado"),
]

if "mensaje" in st.session_state:
    st.success(st.session_state.pop("mensaje"))

try:
    pendientes = api.get("/api/triajes/", atendido="false", limite=200)
except Exception as e:
    st.error(f"No se pudo consultar la API: {e}")
    st.stop()

# Cola de espera: primero los más urgentes y, dentro de cada nivel, los más antiguos
pendientes.sort(key=lambda t: (-t["nivel_asignado"], t["fecha_hora"]))
por_id = {t["_id"]: t for t in pendientes}


def etiqueta(i):
    t = por_id[i]
    return (f"Triaje {t['_id']} - {t['paciente_nombre']} - {NIVELES[t['nivel_asignado']]} - "
            f"{t['ips_nombre']} - {t['fecha_hora'][:16].replace('T', ' ')}")


st.caption(f"{len(pendientes)} triajes esperando atención")
tab_atencion, tab_reeval = st.tabs(["Registrar atención", "Reevaluar"])

# ------------------------------------------------------------ Registrar atención
with tab_atencion:
    if not pendientes:
        st.info("No hay triajes pendientes de atención.")
    else:
        sel = st.selectbox("Triaje a atender", list(por_id), format_func=etiqueta,
                           key="triaje_atencion")
        t = por_id[sel]
        aviso_nivel(t["nivel_asignado"], f"Nivel {NIVELES[t['nivel_asignado']]}")
        st.write("Síntomas: " + ", ".join(
            f"{s['nombre']} (intensidad {s['intensidad']})" for s in t["sintomas"]))

        try:
            medicos = api.get("/api/medicos/", ips_id=t["ips_id"])
        except api.ApiError as e:
            st.error(str(e))
            medicos = []

        if not medicos:
            st.warning("Esta IPS no tiene médicos registrados.")
        else:
            medico_id = st.selectbox(
                f"Médico de {t['ips_nombre']}", [m["_id"] for m in medicos],
                format_func=lambda i: next(
                    f"{m['nombres']} {m['apellidos']} - {m['especialidad']['nombre']}"
                    for m in medicos if m["_id"] == i))
            c1, c2 = st.columns(2)
            duracion = c1.number_input("Duración de la atención (minutos)",
                                       min_value=1, value=20, step=5)
            resultado = c2.selectbox("Resultado", RESULTADOS)
            diag = st.selectbox("Diagnóstico (CIE-10)", DIAGNOSTICOS,
                                format_func=lambda d: f"{d[0]} - {d[1]}")

            if st.button("Registrar atención", type="primary"):
                try:
                    api.patch(f"/api/triajes/{sel}/atencion", {
                        "medico_id": medico_id,
                        "duracion_minutos": int(duracion),
                        "resultado": resultado,
                        "diagnostico": {"codigo_cie10": diag[0], "descripcion": diag[1]},
                    })
                    st.session_state["mensaje"] = f"Atención registrada para el triaje {sel}."
                    st.rerun()
                except api.ApiError as e:
                    st.error(str(e))

# ------------------------------------------------------------------- Reevaluar
with tab_reeval:
    if not pendientes:
        st.info("No hay triajes pendientes que reevaluar.")
    else:
        sel = st.selectbox("Triaje a reevaluar", list(por_id), format_func=etiqueta,
                           key="triaje_reeval")
        t = por_id[sel]
        actual = t["nivel_asignado"]
        st.metric("Nivel actual", NIVELES[actual])

        opciones = [n for n in (2, 3) if n > actual]
        if not opciones:
            st.info("Este triaje ya es nivel 3: no se puede subir más.")
        else:
            nuevo = st.selectbox("Nuevo nivel", opciones, format_func=lambda n: NIVELES[n])
            motivo = st.text_area("Motivo de la reevaluación",
                                  placeholder="Ej.: el paciente refiere empeoramiento de los síntomas")
            if st.button("Registrar reevaluación", type="primary"):
                try:
                    api.post("/api/reevaluaciones/", {
                        "triaje_id": sel, "nivel_nuevo": nuevo, "motivo": motivo})
                    st.session_state["mensaje"] = (
                        f"Triaje {sel} reevaluado: de nivel {actual} a nivel {nuevo}.")
                    st.rerun()
                except api.ApiError as e:
                    st.error(str(e))

        st.divider()
        st.subheader("Historial de reevaluaciones de este triaje")
        try:
            historial = api.get("/api/reevaluaciones/", triaje_id=sel)
        except api.ApiError as e:
            st.error(str(e))
            historial = []
        if historial:
            df = pd.DataFrame(historial)[
                ["fecha_hora", "nivel_anterior", "nivel_nuevo", "motivo"]
            ].rename(columns={"fecha_hora": "Fecha", "nivel_anterior": "Nivel anterior",
                              "nivel_nuevo": "Nivel nuevo", "motivo": "Motivo"})
            df["Fecha"] = df["Fecha"].str[:16].str.replace("T", " ")
            st.dataframe(df, hide_index=True, width="stretch")
        else:
            st.caption("Este triaje no tiene reevaluaciones.")