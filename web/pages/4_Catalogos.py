import pandas as pd
import streamlit as st

import api

st.set_page_config(page_title="Catálogos", layout="wide")
from estilos import aplicar_estilos, colorear_nivel, aviso_nivel
aplicar_estilos()
st.title("Catálogos")

REGIMENES = ["Contributivo", "Subsidiado"]
ESPECIALIDADES = [(1, "Medicina General"), (2, "Medicina de Urgencias"), (3, "Cardiología"),
                  (4, "Neurología"), (5, "Pediatría"), (6, "Medicina Interna")]
TIPOS_REGLA = ["umbral", "critico", "combinacion"]

if "mensaje" in st.session_state:
    st.success(st.session_state.pop("mensaje"))

try:
    eps = api.get("/api/eps/")
    ips = api.get("/api/ips/")
    sintomas = api.get("/api/sintomas/")
    medicos = api.get("/api/medicos/")
    reglas = api.get("/api/reglas/")
except Exception as err:
    st.error(f"No se pudo consultar la API: {err}")
    st.stop()

ips_por_id = {i["_id"]: i for i in ips}
sin_por_id = {s["_id"]: s for s in sintomas}
for m in medicos:
    m["especialidad_nombre"] = m["especialidad"]["nombre"]
for r in reglas:
    r["sintomas_txt"] = ", ".join(r.get("sintomas_nombres", []))


def nombre_ips(i):
    return f"{ips_por_id[i]['nombre']} ({ips_por_id[i]['ciudad']})"


def ejecutar(accion, mensaje):
    try:
        accion()
    except api.ApiError as err:
        st.error(str(err))
        return
    st.session_state["mensaje"] = mensaje
    st.rerun()


def faltan(*textos):
    if not all(t.strip() for t in textos):
        st.warning("Completa todos los campos.")
        return True
    return False


# ------------------------------------------------------------- Formularios
def form_eps(clave, d):
    with st.form(clave):
        c1, c2, c3 = st.columns(3)
        nombre = c1.text_input("Nombre", d.get("nombre", ""))
        nit = c2.text_input("NIT", d.get("nit", ""))
        regimen = c3.selectbox("Régimen", REGIMENES,
                               index=REGIMENES.index(d.get("regimen", "Contributivo")))
        enviado = st.form_submit_button("Guardar", type="primary")
    if enviado and not faltan(nombre, nit):
        return {"nombre": nombre.strip(), "nit": nit.strip(), "regimen": regimen}


def form_ips(clave, d):
    with st.form(clave):
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre", d.get("nombre", ""))
        ciudad = c2.text_input("Ciudad", d.get("ciudad", ""))
        direccion = c1.text_input("Dirección", d.get("direccion", ""))
        nivel = c2.selectbox("Nivel de complejidad", [1, 2, 3, 4],
                             index=d.get("nivel_complejidad", 1) - 1)
        capacidad = c1.number_input("Capacidad de urgencias", min_value=0,
                                    value=d.get("capacidad_urgencias", 0), step=1)
        enviado = st.form_submit_button("Guardar", type="primary")
    if enviado and not faltan(nombre, ciudad, direccion):
        return {"nombre": nombre.strip(), "ciudad": ciudad.strip(),
                "direccion": direccion.strip(), "nivel_complejidad": nivel,
                "capacidad_urgencias": int(capacidad)}


def form_sintoma(clave, d):
    with st.form(clave):
        c1, c2, c3 = st.columns(3)
        nombre = c1.text_input("Nombre", d.get("nombre", ""))
        categoria = c2.text_input("Categoría", d.get("categoria", ""))
        alerta = c3.selectbox("Nivel de alerta", [1, 2, 3],
                              index=d.get("nivel_alerta", 1) - 1)
        enviado = st.form_submit_button("Guardar", type="primary")
    if enviado and not faltan(nombre, categoria):
        return {"nombre": nombre.strip(), "categoria": categoria.strip(),
                "nivel_alerta": alerta}


def form_medico(clave, d):
    if not ips_por_id:
        st.info("Primero registra una IPS.")
        return None
    esp_ids = [e[0] for e in ESPECIALIDADES]
    esp_actual = d.get("especialidad", {}).get("id")
    ips_ids = list(ips_por_id)
    with st.form(clave):
        c1, c2 = st.columns(2)
        nombres = c1.text_input("Nombres", d.get("nombres", ""))
        apellidos = c2.text_input("Apellidos", d.get("apellidos", ""))
        registro = c1.text_input("Registro médico", d.get("registro_medico", ""))
        esp = c2.selectbox("Especialidad", ESPECIALIDADES, format_func=lambda e: e[1],
                           index=esp_ids.index(esp_actual) if esp_actual in esp_ids else 0)
        ips_id = st.selectbox("IPS", ips_ids, format_func=nombre_ips,
                              index=ips_ids.index(d["ips_id"]) if d.get("ips_id") in ips_ids else 0)
        enviado = st.form_submit_button("Guardar", type="primary")
    if enviado and not faltan(nombres, apellidos, registro):
        return {"nombres": nombres.strip(), "apellidos": apellidos.strip(),
                "registro_medico": registro.strip(),
                "especialidad": {"id": esp[0], "nombre": esp[1]}, "ips_id": ips_id}


def form_regla(clave, d):
    with st.form(clave):
        c1, c2, c3 = st.columns(3)
        tipo = c1.selectbox("Tipo", TIPOS_REGLA,
                            index=TIPOS_REGLA.index(d.get("tipo", "umbral")))
        nivel = c2.selectbox("Nivel que asigna", [2, 3], index=[2, 3].index(d.get("nivel", 3)))
        puntaje = c3.number_input("Puntaje mínimo (solo umbral)", min_value=0,
                                  value=d.get("puntaje_minimo") or 0, step=1)
        sints = st.multiselect(
            "Síntomas (solo crítico o combinación)", list(sin_por_id),
            default=[s for s in d.get("sintomas_ids", []) if s in sin_por_id],
            format_func=lambda i: sin_por_id[i]["nombre"])
        descripcion = st.text_input("Descripción", d.get("descripcion", ""))
        activa = st.checkbox("Activa", value=d.get("activa", True))
        enviado = st.form_submit_button("Guardar", type="primary")
    if enviado and not faltan(descripcion):
        return {"tipo": tipo, "nivel": nivel,
                "puntaje_minimo": int(puntaje) if tipo == "umbral" else None,
                "sintomas_ids": [] if tipo == "umbral" else sints,
                "descripcion": descripcion.strip(), "activa": activa}


# ------------------------------------------------------- Sección genérica
def seccion(nombre, ruta, datos, columnas, etiqueta, formulario):
    if datos:
        df = pd.DataFrame(datos)[list(columnas)].rename(columns=columnas)
        st.dataframe(df, hide_index=True, width="stretch")
    else:
        st.info("No hay registros.")

    with st.expander(f"Agregar {nombre}"):
        nuevo = formulario(f"nuevo_{ruta}", {})
        if nuevo:
            ejecutar(lambda: api.post(ruta, nuevo), "Registro creado.")

    if not datos:
        return
    st.divider()
    por_id = {d["_id"]: d for d in datos}
    sel = st.selectbox(f"Editar o eliminar ({nombre})", list(por_id),
                       format_func=lambda i: etiqueta(por_id[i]), key=f"sel_{ruta}")
    cambios = formulario(f"editar_{ruta}_{sel}", por_id[sel])
    if cambios:
        ejecutar(lambda: api.put(f"{ruta}{sel}", cambios), f"Registro {sel} actualizado.")
    confirmar = st.checkbox("Confirmo que quiero eliminar este registro",
                            key=f"conf_{ruta}_{sel}")
    if st.button("Eliminar", key=f"del_{ruta}_{sel}", disabled=not confirmar):
        ejecutar(lambda: api.delete(f"{ruta}{sel}"), f"Registro {sel} eliminado.")


VISTAS = ["EPS", "IPS", "Síntomas", "Médicos", "Reglas de clasificación"]
vista = st.radio("Catálogo", VISTAS, horizontal=True, key="catalogo_vista",
                 label_visibility="collapsed")
st.divider()

if vista == "EPS":
    seccion("EPS", "/api/eps/", eps,
            {"_id": "ID", "nombre": "Nombre", "nit": "NIT", "regimen": "Régimen"},
            lambda d: f"{d['_id']} - {d['nombre']}", form_eps)

elif vista == "IPS":
    seccion("IPS", "/api/ips/", ips,
            {"_id": "ID", "nombre": "Nombre", "ciudad": "Ciudad", "direccion": "Dirección",
             "nivel_complejidad": "Complejidad", "capacidad_urgencias": "Capacidad"},
            lambda d: f"{d['_id']} - {d['nombre']} ({d['ciudad']})", form_ips)

elif vista == "Síntomas":
    seccion("síntoma", "/api/sintomas/", sintomas,
            {"_id": "ID", "nombre": "Nombre", "categoria": "Categoría",
             "nivel_alerta": "Alerta"},
            lambda d: f"{d['_id']} - {d['nombre']}", form_sintoma)

elif vista == "Médicos":
    seccion("médico", "/api/medicos/", medicos,
            {"_id": "ID", "nombres": "Nombres", "apellidos": "Apellidos",
             "registro_medico": "Registro", "especialidad_nombre": "Especialidad",
             "ips_nombre": "IPS"},
            lambda d: f"{d['_id']} - {d['nombres']} {d['apellidos']}", form_medico)

else:
    seccion("regla", "/api/reglas/", reglas,
            {"_id": "ID", "tipo": "Tipo", "nivel": "Nivel", "puntaje_minimo": "Puntaje mínimo",
             "sintomas_txt": "Síntomas", "descripcion": "Descripción", "activa": "Activa"},
            lambda d: f"{d['_id']} - {d['descripcion']}", form_regla)