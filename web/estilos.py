import streamlit as st

COLORES_NIVEL = {1: ("#15803D", "#DCFCE7"),
                 2: ("#B45309", "#FEF3C7"),
                 3: ("#B91C1C", "#FEE2E2")}


def aplicar_estilos():
    st.markdown("""
    <style>
    h1 { color: #0F766E; }
    [data-testid="stMetric"] {
        background: #FFFFFF; border: 1px solid #D1E7E5;
        border-left: 6px solid #0F766E; border-radius: 10px; padding: 12px 16px;
    }
    [data-testid="stSidebar"] { background: #0F766E; }
    [data-testid="stSidebar"] * { color: #FFFFFF; }
    </style>
    """, unsafe_allow_html=True)


def colorear_nivel(valor):
    """Colorea una celda de tabla según el nivel (el texto empieza por 1, 2 o 3)."""
    for n, (color, fondo) in COLORES_NIVEL.items():
        if str(valor).startswith(str(n)):
            return f"background-color: {fondo}; color: {color}; font-weight: 600"
    return ""


def aviso_nivel(nivel, texto):
    """Mensaje con el color del nivel."""
    if nivel == 3:
        st.error(texto)
    elif nivel == 2:
        st.warning(texto)
    else:
        st.success(texto)