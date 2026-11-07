import pandas as pd
import streamlit as st
import api

st.set_page_config(page_title="Triaje IPS", layout="wide")
from estilos import aplicar_estilos, colorear_nivel, aviso_nivel
aplicar_estilos()
st.title("Sistema de pre-triaje para IPS")
st.caption("Panel de indicadores")

try:
    urgentes = api.get("/api/reportes/urgentes-sin-atencion", limite=100)
    espera = api.get("/api/reportes/espera-por-nivel")
    sintomas = api.get("/api/reportes/sintomas-frecuentes", limite=10)
    eps = api.get("/api/reportes/eps-urgentes")
except Exception as e:
    st.error(f"No se pudo consultar la API: {e}")
    st.stop()

df_espera = pd.DataFrame(espera)
if not df_espera.empty:
    df_espera["peso"] = df_espera["espera_promedio_min"] * df_espera["triajes"]
    por_nivel = df_espera.groupby("nivel").agg(peso=("peso", "sum"), n=("triajes", "sum"))
    por_nivel["Espera promedio (min)"] = (por_nivel["peso"] / por_nivel["n"]).round(1)
else:
    por_nivel = pd.DataFrame()

c1, c2, c3 = st.columns(3)
c1.metric("Urgentes sin atención", len(urgentes))
if 3 in por_nivel.index:
    c2.metric("Espera promedio nivel 3 (min)", por_nivel.loc[3, "Espera promedio (min)"])
if eps:
    c3.metric("EPS con más urgentes", eps[0]["eps"])

st.divider()
izq, der = st.columns(2)

with izq:
    st.subheader("Espera promedio por nivel (minutos)")
    if not por_nivel.empty:
        st.bar_chart(por_nivel["Espera promedio (min)"])
    st.subheader("EPS con más casos urgentes")
    if eps:
        df = pd.DataFrame(eps).rename(columns={
            "eps": "EPS", "regimen": "Régimen",
            "casos_urgentes": "Casos urgentes", "sin_atencion": "Sin atención"})
        st.dataframe(df, hide_index=True, width="stretch")

with der:
    st.subheader("Síntomas más frecuentes")
    if sintomas:
        df = pd.DataFrame(sintomas).set_index("sintoma")
        st.bar_chart(df["veces"])

st.subheader("Casos urgentes sin atender")
if urgentes:
    df = pd.DataFrame(urgentes)[
        ["_id", "paciente_nombre", "telefono", "ips", "ciudad", "puntaje_total", "minutos_esperando"]
    ].rename(columns={
        "_id": "Triaje", "paciente_nombre": "Paciente", "telefono": "Teléfono",
        "ips": "IPS", "ciudad": "Ciudad", "puntaje_total": "Puntaje",
        "minutos_esperando": "Minutos esperando"})
    st.dataframe(df, hide_index=True, width="stretch")
else:
    st.success("No hay casos urgentes pendientes.")