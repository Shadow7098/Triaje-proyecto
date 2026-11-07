from datetime import date

import pandas as pd
import streamlit as st

import api

st.set_page_config(page_title="Pacientes", layout="wide")
from estilos import aplicar_estilos, colorear_nivel, aviso_nivel
aplicar_estilos()
st.title("Pacientes")

TIPOS_DOC = ["CC", "TI", "CE", "PA", "RC"]
SEXOS = {"F": "Femenino", "M": "Masculino"}

if "mensaje" in st.session_state:
    st.success(st.session_state.pop("mensaje"))

try:
    eps_lista = api.get("/api/eps/")
except Exception as err:
    st.error(f"No se pudo consultar la API: {err}")
    st.stop()

eps_por_id = {x["_id"]: x for x in eps_lista}


def nombre_eps(i):
    return f"{eps_por_id[i]['nombre']} ({eps_por_id[i]['regimen']})"


tab_buscar, tab_nuevo = st.tabs(["Buscar y editar", "Nuevo paciente"])

# ------------------------------------------------------------- Buscar y editar
with tab_buscar:
    f1, f2, f3, f4 = st.columns(4)
    documento = f1.text_input("Documento (empieza por)")
    nombre = f2.text_input("Nombre o apellido")
    ciudad = f3.text_input("Ciudad")
    eps_f = f4.selectbox("EPS", [None] + list(eps_por_id),
                         format_func=lambda i: "Todas" if i is None else nombre_eps(i))

    try:
        pacientes = api.get("/api/pacientes/", documento=documento, nombre=nombre,
                            ciudad=ciudad, eps_id=eps_f)
    except api.ApiError as err:
        st.error(str(err))
        pacientes = []

    st.caption(f"{len(pacientes)} pacientes encontrados")
    if pacientes:
        df = pd.DataFrame(pacientes)[[
            "_id", "tipo_documento", "numero_documento", "nombres", "apellidos",
            "fecha_nacimiento", "sexo", "telefono", "ciudad", "eps_nombre"]]
        df["fecha_nacimiento"] = df["fecha_nacimiento"].str[:10]
        df = df.rename(columns={
            "_id": "ID", "tipo_documento": "Tipo", "numero_documento": "Documento",
            "nombres": "Nombres", "apellidos": "Apellidos",
            "fecha_nacimiento": "Nacimiento", "sexo": "Sexo", "telefono": "Teléfono",
            "ciudad": "Ciudad", "eps_nombre": "EPS"})
        st.dataframe(df, hide_index=True, width="stretch")

        st.divider()
        por_id = {p["_id"]: p for p in pacientes}
        sel = st.selectbox(
            "Paciente a editar o eliminar", list(por_id),
            format_func=lambda i: (f"{por_id[i]['nombres']} {por_id[i]['apellidos']} - "
                                   f"{por_id[i]['tipo_documento']} {por_id[i]['numero_documento']}"))
        p = por_id[sel]

        with st.form(f"editar_{sel}"):
            c1, c2 = st.columns(2)
            tipo = c1.selectbox("Tipo de documento", TIPOS_DOC,
                                index=TIPOS_DOC.index(p["tipo_documento"]))
            numero = c2.text_input("Número de documento", value=p["numero_documento"])
            nombres = c1.text_input("Nombres", value=p["nombres"])
            apellidos = c2.text_input("Apellidos", value=p["apellidos"])
            nacimiento = c1.date_input(
                "Fecha de nacimiento", value=date.fromisoformat(p["fecha_nacimiento"][:10]),
                min_value=date(1900, 1, 1), max_value=date.today())
            sexo = c2.selectbox("Sexo", list(SEXOS), index=list(SEXOS).index(p["sexo"]),
                                format_func=SEXOS.get)
            telefono = c1.text_input("Teléfono", value=p["telefono"])
            ciudad_e = c2.text_input("Ciudad", value=p["ciudad"])
            eps_e = st.selectbox("EPS", list(eps_por_id),
                                 index=list(eps_por_id).index(p["eps_id"]),
                                 format_func=nombre_eps)
            guardar = st.form_submit_button("Guardar cambios", type="primary")

        if guardar:
            if not all(v.strip() for v in (numero, nombres, apellidos, telefono, ciudad_e)):
                st.warning("Completa todos los campos.")
            else:
                try:
                    api.put(f"/api/pacientes/{sel}", {
                        "tipo_documento": tipo, "numero_documento": numero.strip(),
                        "nombres": nombres.strip(), "apellidos": apellidos.strip(),
                        "fecha_nacimiento": nacimiento.isoformat(), "sexo": sexo,
                        "telefono": telefono.strip(), "ciudad": ciudad_e.strip(),
                        "eps_id": eps_e})
                    st.session_state["mensaje"] = f"Paciente {sel} actualizado."
                    st.rerun()
                except api.ApiError as err:
                    st.error(str(err))

        confirmar = st.checkbox("Confirmo que quiero eliminar este paciente",
                                key=f"conf_{sel}")
        if st.button("Eliminar paciente", disabled=not confirmar):
            try:
                api.delete(f"/api/pacientes/{sel}")
                st.session_state["mensaje"] = f"Paciente {sel} eliminado."
                st.rerun()
            except api.ApiError as err:
                st.error(str(err))

# ------------------------------------------------------------- Nuevo paciente
with tab_nuevo:
    st.subheader("Registrar un paciente")
    with st.form("nuevo_paciente", clear_on_submit=True):
        c1, c2 = st.columns(2)
        tipo = c1.selectbox("Tipo de documento", TIPOS_DOC)
        numero = c2.text_input("Número de documento")
        nombres = c1.text_input("Nombres")
        apellidos = c2.text_input("Apellidos")
        nacimiento = c1.date_input("Fecha de nacimiento", value=date(2000, 1, 1),
                                   min_value=date(1900, 1, 1), max_value=date.today())
        sexo = c2.selectbox("Sexo", list(SEXOS), format_func=SEXOS.get)
        telefono = c1.text_input("Teléfono")
        ciudad_n = c2.text_input("Ciudad")
        eps_n = st.selectbox("EPS", list(eps_por_id), format_func=nombre_eps)
        crear = st.form_submit_button("Registrar paciente", type="primary")

    if crear:
        if not all(v.strip() for v in (numero, nombres, apellidos, telefono, ciudad_n)):
            st.warning("Completa todos los campos.")
        else:
            try:
                nuevo = api.post("/api/pacientes/", {
                    "tipo_documento": tipo, "numero_documento": numero.strip(),
                    "nombres": nombres.strip(), "apellidos": apellidos.strip(),
                    "fecha_nacimiento": nacimiento.isoformat(), "sexo": sexo,
                    "telefono": telefono.strip(), "ciudad": ciudad_n.strip(),
                    "eps_id": eps_n})
                st.success(f"Paciente registrado con el ID {nuevo['_id']}: "
                           f"{nuevo['nombres']} {nuevo['apellidos']}")
            except api.ApiError as err:
                st.error(str(err))