# app.py
import streamlit as st
import json
from pathlib import Path
from typing import Dict, List
import base64

st.set_page_config(layout="wide", page_title="Plan UTN Visual", initial_sidebar_state="expanded")


# ---------------------------
# UTIL: ejemplo de materias
# ---------------------------
DEFAULT_MATERIAS = [
    # codigo, nombre, nivel, correlativas (lista)
    {"codigo": "AyED", "nombre": "Algoritmos", "nivel": 1, "correlativas": []},
    {"codigo": "AM1", "nombre": "Análisis Matemático I", "nivel": 1, "correlativas": []},
    {"codigo": "LGC", "nombre": "Lógica", "nivel": 1, "correlativas": []},
    {"codigo": "PdP", "nombre": "Paradigmas de Programación", "nivel": 2, "correlativas": ["AyED"]},
    {"codigo": "SO", "nombre": "Sistemas Operativos", "nivel": 2, "correlativas": ["AyED"]},
    {"codigo": "Sint", "nombre": "Sintaxis y Semántica", "nivel": 2, "correlativas": ["AyED"]},
    {"codigo": "DdS", "nombre": "Desarrollo de Software", "nivel": 3, "correlativas": ["PdP"]},
    {"codigo": "BdD", "nombre": "Bases de Datos", "nivel": 3, "correlativas": ["AyED","PdP","SO"]},
    # agregá más materias reales aquí o cargalas desde plande.json
]

# ---------------------------
# FUNCIONES LÓGICAS
# ---------------------------
def materias_list_to_dict(materias: List[Dict]) -> Dict[str, Dict]:
    """Convierte lista a dict por codigo"""
    d = {}
    for m in materias:
        d[m["codigo"]] = {
            "nombre": m["nombre"],
            "nivel": m.get("nivel", 1),
            "correlativas": m.get("correlativas", []),
        }
    return d

def calc_states(materias_dict: Dict[str, Dict], aprobadas: Dict[str, bool], regularizadas: Dict[str, bool]) -> Dict[str, str]:
    """
    Devuelve estado por materia: "aprobada" / "regularizada" / "habilitada" / "bloqueada"
    Aclaración: tratamos regularizada como "no aprobada plena" pero que puede desbloquear si así lo querés.
    Por defecto, consideramos que **regularizada cuenta como aprobada para desbloqueos**, pero lo indicamos distinto visualmente.
    """
    estados = {}
    # Para evaluar habilitadas debemos considerar aprobadas + regularizadas como "cumplidas"
    cumplidas = {k for k,v in aprobadas.items() if v} | {k for k,v in regularizadas.items() if v}

    for codigo, meta in materias_dict.items():
        if aprobadas.get(codigo, False):
            estados[codigo] = "aprobada"
        elif regularizadas.get(codigo, False):
            estados[codigo] = "regularizada"
        else:
            corr = meta.get("correlativas", [])
            if len(corr) == 0:
                estados[codigo] = "habilitada"  # sin correlativas = habilitada por defecto
            else:
                # si TODAS las correlativas están en "cumplidas", está habilitada
                if all((c in cumplidas) for c in corr):
                    estados[codigo] = "habilitada"
                else:
                    estados[codigo] = "bloqueada"
    return estados

def parse_plande_json(obj):
    """
    Intento heurístico para parsear un export de plande.app.
    Como los exports varían, este parser busca keys obvias y estructura mínima:
    - buscar 'subjects' o 'courses' o 'materias'
    - cada elemento: code (codigo), name/nombre, level/nivel, prerequisites/prereqs
    """
    candidates = []
    if isinstance(obj, dict):
        # buscar claves candidatas
        for key in ("subjects","materias","courses","subjectsList","items"):
            if key in obj:
                candidates = obj[key]
                break
        # si no encontró, tal vez el JSON ya sea la lista
        if not candidates:
            # heurística: si dict tiene many keys que a su vez son materias
            # fallback: si 'data' en objeto
            if "data" in obj and isinstance(obj["data"], list):
                candidates = obj["data"]
            else:
                # intentar interpretar como lista de materias si values tienen 'code' o 'name'
                possible = []
                for v in obj.values():
                    if isinstance(v, dict) and ("code" in v or "nombre" in v or "name" in v):
                        possible.append(v)
                if possible:
                    candidates = possible
    elif isinstance(obj, list):
        candidates = obj

    parsed = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        # obtener campos
        codigo = item.get("code") or item.get("codigo") or item.get("id") or item.get("key") or item.get("short")
        nombre = item.get("name") or item.get("nombre") or item.get("title") or item.get("label")
        nivel = item.get("level") or item.get("nivel") or item.get("year")
        prereqs = item.get("requirements") or item.get("prereqs") or item.get("prerequisites") or item.get("correlativas")
        # normalizar prereqs a lista de strings
        if prereqs is None:
            prereqs = []
        if isinstance(prereqs, str):
            prereqs = [x.strip() for x in prereqs.split(",") if x.strip()]
        if nombre and codigo:
            parsed.append({
                "codigo": str(codigo),
                "nombre": str(nombre),
                "nivel": int(nivel) if nivel and isinstance(nivel, (int,str)) and str(nivel).isdigit() else 1,
                "correlativas": prereqs
            })
    return parsed

def to_downloadable_json(data: dict):
    s = json.dumps(data, indent=2, ensure_ascii=False)
    b64 = base64.b64encode(s.encode()).decode()
    href = f"data:application/json;base64,{b64}"
    return href

# ---------------------------
# UI: Sidebar
# ---------------------------
st.sidebar.title("Configuración / Import")
st.sidebar.markdown("Subí un JSON exportado de Plande.app **o** subí/pega tu propio JSON/CSV de materias. Si no subís nada, se usa un ejemplo mínimo.")

uploaded = st.sidebar.file_uploader("Subir JSON/CSV de materias (opcional)", type=['json','csv'])
use_default = False
materias = None

if uploaded:
    raw = uploaded.read()
    try:
        if uploaded.type == "application/json" or str(uploaded.name).endswith(".json"):
            obj = json.loads(raw.decode())
            parsed = parse_plande_json(obj)
            if parsed:
                materias = parsed
            else:
                st.sidebar.warning("JSON cargado: no pude parsearlo automáticamente. Intentá exportar desde plande.app como 'subjects' o subí CSV.")
        else:
            # CSV simple: columnas codigo,nombre,nivel,correlativas (correlativas separadas por ;)
            import csv, io
            reader = csv.DictReader(io.StringIO(raw.decode()))
            parsed = []
            for r in reader:
                parsed.append({
                    "codigo": r.get("codigo") or r.get("code") or r.get("id"),
                    "nombre": r.get("nombre") or r.get("name"),
                    "nivel": int(r.get("nivel") or r.get("level") or 1),
                    "correlativas": [x.strip() for x in (r.get("correlativas") or r.get("prereqs") or "").split(";") if x.strip()]
                })
            materias = parsed
    except Exception as e:
        st.sidebar.error(f"Error parsing file: {e}")
        materias = None

if materias is None:
    st.sidebar.info("Usando dataset de ejemplo (puedes subir tu JSON de Plande.app para poblar todo automáticamente).")
    materias = DEFAULT_MATERIAS.copy()

# Normalizar dict
materias_dict = materias_list_to_dict(materias)

# session state: estados de aprobadas / regularizadas
if "aprobadas" not in st.session_state:
    st.session_state.aprobadas = {k: False for k in materias_dict.keys()}
if "regularizadas" not in st.session_state:
    st.session_state.regularizadas = {k: False for k in materias_dict.keys()}

# Si el JSON trae materias no presentes en session_state, agregarlas
for c in materias_dict.keys():
    if c not in st.session_state.aprobadas:
        st.session_state.aprobadas[c] = False
    if c not in st.session_state.regularizadas:
        st.session_state.regularizadas[c] = False

# ---------------------------
# MAIN: controles globales
# ---------------------------
st.title("Plan de carrera — Visual UTN (Streamlit)")
st.markdown("Carga tu plan desde Plande.app (JSON) o edita manualmente. Marca las materias como *Aprobada* o *Regularizada*; la app calculará habilitadas automáticamente.")

col_controls = st.columns([1,1,2])
with col_controls[0]:
    if st.button("Marcar todo aprobado (ejemplo)"):
        for k in st.session_state.aprobadas:
            st.session_state.aprobadas[k] = True

with col_controls[1]:
    if st.button("Limpiar estado"):
        for k in st.session_state.aprobadas:
            st.session_state.aprobadas[k] = False
        for k in st.session_state.regularizadas:
            st.session_state.regularizadas[k] = False

with col_controls[2]:
    download_json = {
        "aprobadas": st.session_state.aprobadas,
        "regularizadas": st.session_state.regularizadas,
        "materias": materias
    }
    st.download_button("Descargar progreso (JSON)", data=json.dumps(download_json, ensure_ascii=False, indent=2), file_name="plan_estado.json")


# ---------------------------
# Mostrar visual por NIVELES (columnas)
# ---------------------------
# calcular estados
estados = calc_states(materias_dict, st.session_state.aprobadas, st.session_state.regularizadas)

# agrupar por nivel ordenado
niveles = sorted(set([m["nivel"] for m in materias]))
max_level = max(niveles) if niveles else 1

# crear columnas por nivel
cols = st.columns(max_level)
for i, col in enumerate(cols, start=1):
    with col:
        st.markdown(f"### Nivel {i}")
        # ordenar materias por nombre dentro del nivel
        nivel_mats = [c for c,m in materias_dict.items() if m["nivel"]==i]
        if not nivel_mats:
            st.write("_Sin materias en este nivel_")
        for codigo in sorted(nivel_mats, key=lambda x: materias_dict[x]["nombre"]):
            meta = materias_dict[codigo]
            estado = estados.get(codigo, "bloqueada")
            nombre = meta["nombre"]
            # checkbox / toggles
            col1, col2 = st.columns([3,1])
            with col1:
                # mostrar nombre + codigo + correlativas
                corr = meta.get("correlativas", [])
                corr_label = f" ({', '.join(corr)})" if corr else ""
                # mostrar como boton/markdown con color
                if estado == "aprobada":
                    style = "background:#1f9d3a;color:white;padding:6px;border-radius:6px"
                elif estado == "regularizada":
                    style = "background:#4ec1d3;color:black;padding:6px;border-radius:6px"
                elif estado == "habilitada":
                    style = "background:#ffd166;color:black;padding:6px;border-radius:6px"
                else:
                    style = "background:#ef476f;color:white;padding:6px;border-radius:6px"
                st.markdown(f"<div style='{style}'>{nombre} <small>({codigo})</small> {corr_label}</div>", unsafe_allow_html=True)
            with col2:
                # checkboxes para cambiar estado
                ap = st.checkbox("A", key=f"ap_{codigo}", value=st.session_state.aprobadas.get(codigo, False))
                reg = st.checkbox("R", key=f"rg_{codigo}", value=st.session_state.regularizadas.get(codigo, False))
                # sincronzar session_state
                st.session_state.aprobadas[codigo] = ap
                st.session_state.regularizadas[codigo] = reg

# ---------------------------
# Panel derecho: info y consultas
# ---------------------------
st.sidebar.header("Consultas rápidas")
selected = st.sidebar.text_input("Buscar materia por código o nombre")
if selected:
    res = []
    for c, m in materias_dict.items():
        if selected.lower() in c.lower() or selected.lower() in m["nombre"].lower():
            res.append((c, m))
    if res:
        for c,m in res:
            st.sidebar.write(f"**{c}** — {m['nombre']} (nivel {m['nivel']})")
            st.sidebar.write(f"Correlativas: {', '.join(m['correlativas']) if m['correlativas'] else 'Ninguna'}")
            st.sidebar.write(f"Estado: {estados[c]}")
    else:
        st.sidebar.write("No se encontró.")

st.sidebar.markdown("---")
st.sidebar.header("Import / Editar materias")
if st.sidebar.button("Exportar materias (ejemplo)"):
    st.sidebar.markdown(to_downloadable_json({"materias": materias}), unsafe_allow_html=True)

st.sidebar.markdown("**Si querés que cargue automáticamente desde Plande.app:**")
st.sidebar.markdown("- Exportá tu plan en JSON desde Plande.app y subilo arriba (File uploader).")
st.sidebar.markdown("- Si la estructura no coincide, podés editar el JSON manualmente o cargar CSV.")

st.sidebar.markdown("---")
st.sidebar.write("Hecho por: plantilla Streamlit · Personalizá la lista de materias y correlativas según tu plan.")

