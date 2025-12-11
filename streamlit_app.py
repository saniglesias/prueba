import streamlit as st
import json
from pathlib import Path

# ==========================
# CONFIG
# ==========================
st.set_page_config(page_title="Plan UTN - Plan K2023", layout="wide")

# ==========================
# CARGA DE MATERIAS
# ==========================
MATERIAS_PATH = Path("materias_planK2023.json")

if not MATERIAS_PATH.exists():
    st.error("ERROR: No se encontró 'materias_planK2023.json' en la carpeta del proyecto.")
    st.stop()

materias = json.loads(MATERIAS_PATH.read_text(encoding="utf-8"))

# Convertimos a dict por código
materias_dict = {m["codigo"]: m for m in materias}

# ==========================
# ESTADO EN SESSION
# ==========================
if "aprobadas" not in st.session_state:
    st.session_state.aprobadas = {k: False for k in materias_dict.keys()}

if "regularizadas" not in st.session_state:
    st.session_state.regularizadas = {k: False for k in materias_dict.keys()}

# ==========================
# LÓGICA DE ESTADOS
# ==========================
def calcular_estado(codigo):
    """
    Estados:
    - aprobada
    - regularizada
    - habilitada (cumple correlativas con R o A)
    - bloqueada
    """

    if st.session_state.aprobadas[codigo]:
        return "aprobada"
    if st.session_state.regularizadas[codigo]:
        return "regularizada"

    corr = materias_dict[codigo]["correlativas"]
    if not corr:
        return "habilitada"  # Sin correlativas → siempre habilitada

    # Si TODAS las correlativas están en (aprobadas + regularizadas)
    cumplidas = {
        c for c in materias_dict.keys()
        if st.session_state.aprobadas[c] or st.session_state.regularizadas[c]
    }

    if all(c in cumplidas for c in corr):
        return "habilitada"

    return "bloqueada"


def color_estado(estado):
    if estado == "aprobada":
        return "background:#28a745;color:white;padding:6px;border-radius:6px;"
    if estado == "regularizada":
        return "background:#5bc0de;color:black;padding:6px;border-radius:6px;"
    if estado == "habilitada":
        return "background:#f7d44c;color:black;padding:6px;border-radius:6px;"
    return "background:#dc3545;color:white;padding:6px;border-radius:6px;"


# ==========================
# UI SUPERIOR
# ==========================
st.title("📘 Plan de Carrera UTN FRBA – Plan K2023 (visual por niveles)")

colA, colB = st.columns(2)
with colA:
    if st.button("Marcar todo como NO aprobado / NO regularizado"):
        for k in st.session_state.aprobadas:
            st.session_state.aprobadas[k] = False
        for k in st.session_state.regularizadas:
            st.session_state.regularizadas[k] = False

with colB:
    st.download_button(
        "Descargar Progreso (JSON)",
        json.dumps({
            "aprobadas": st.session_state.aprobadas,
            "regularizadas": st.session_state.regularizadas,
        }, indent=2, ensure_ascii=False),
        file_name="progreso_plan.json"
    )

# ==========================
# AGRUPAMOS POR NIVELES
# ==========================
niveles = sorted(set(m["nivel"] for m in materias))
cols = st.columns(len(niveles))

for i, nivel in enumerate(niveles):
    with cols[i]:
        st.markdown(f"## Nivel {nivel}")

        materias_nivel = [m for m in materias if m["nivel"] == nivel]
        materias_nivel = sorted(materias_nivel, key=lambda x: x["nombre"])

        for m in materias_nivel:
            codigo = m["codigo"]
            nombre = m["nombre"]
            corr = m["correlativas"]
            corr_str = f" <small>({', '.join(corr)})</small>" if corr else ""

            estado = calcular_estado(codigo)
            estilo = color_estado(estado)

            # Caja visual
            st.markdown(
                f"<div style='{estilo}'><b>{nombre}</b> — {codigo}{corr_str}</div>",
                unsafe_allow_html=True
            )

            # Controles de estado
            c1, c2 = st.columns(2)

            with c1:
                st.session_state.aprobadas[codigo] = st.checkbox(
                    "Aprobada",
                    value=st.session_state.aprobadas[codigo],
                    key=f"ap_{codigo}_{nivel}"
                )

            with c2:
                st.session_state.regularizadas[codigo] = st.checkbox(
                    "Regularizada",
                    value=st.session_state.regularizadas[codigo],
                    key=f"reg_{codigo}_{nivel}"
                )

