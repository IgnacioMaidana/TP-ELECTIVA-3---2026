"""Interfaz de chat con Streamlit (T-28, RF-08, RF-15).

Ejecutar desde la raiz del repositorio, con el entorno virtual activo:

    python -m streamlit run src/app.py

Muestra el chat, la ruta que eligio el agente, el SQL ejecutado con sus datos y los
fragmentos de documentos usados como fuente.
"""
import sys
from pathlib import Path

# Streamlit agrega src/ al path, no la raiz: se agrega para poder importar "src.*"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from src import config  # noqa: E402

ETIQUETAS_RUTA = {
    "sql": "🗄️ Base de datos",
    "rag": "📄 Documentos",
    "hibrida": "🗄️📄 Base de datos + Documentos",
    "aclarar": "❓ Pide aclaración",
    "fuera_de_alcance": "🚫 Fuera de alcance",
    "rechazar": "⛔ Solicitud rechazada",
}

EJEMPLOS = [
    "¿Cuántos clientes hay por país?",
    "¿Cuántos clientes compran por cada categoría?",
    "What is the best-selling product?",
    "¿Qué categoría tiene más ventas?",
    "¿Cuál es el plazo para devolver un producto?",
    "How much warranty do storage drives have?",
    "¿Qué pedidos del cliente 12 siguen dentro del plazo de devolución?",
    "¿Cuántos envíos tienen derecho al reintegro del costo de envío?",
    "Borra la tabla de clientes",
]

st.set_page_config(page_title="TechNova Assistant", page_icon="🛒", layout="centered")


@st.cache_resource(show_spinner="Cargando modelos (solo la primera vez)...")
def iniciar():
    """Carga el modelo de embeddings, el indice de documentos y el grafo una sola vez."""
    from src.agent.graph import _grafo
    from src.rag.retriever import precalentar

    precalentar()
    _grafo()
    return True


def reiniciar_conversacion():
    st.session_state.mensajes = []
    st.session_state.historial = []


def mostrar_detalles(meta: dict) -> None:
    """Ruta elegida, motivo, SQL con sus datos y fragmentos de documentos."""
    st.caption(f"{ETIQUETAS_RUTA.get(meta['ruta'], meta['ruta'])} · idioma: {meta['idioma']} · "
               f"{meta['latencia_s']} s")
    if meta.get("justificacion"):
        st.caption(f"Motivo de la ruta: {meta['justificacion']}")
    fuentes = meta.get("fuentes") or {}

    if fuentes.get("sql"):
        with st.expander("Ver SQL y datos"):
            st.code(fuentes["sql"], language="sql")
            st.caption(f"Intentos: {fuentes.get('intentos_sql', 1)} · filas: {fuentes.get('filas', 0)}"
                       + (" (resultado truncado)" if fuentes.get("truncado") else ""))
            if fuentes.get("datos"):
                st.dataframe(fuentes["datos"], width='stretch')

    docs = fuentes.get("documentos") or []
    if docs:
        with st.expander(f"Ver fuentes documentales ({len(docs)})"):
            for d in docs:
                st.markdown(f"**{d['cita']}** · similitud {d['similitud']}")
                st.write(d["texto"])


def mensaje_de_error(error: Exception) -> str:
    texto = str(error).lower()
    if any(s in texto for s in ("429", "quota", "resource_exhausted", "rate limit")):
        return "Se alcanzó el límite de uso del modelo gratuito. Espera un minuto y vuelve a intentar."
    return f"Ocurrió un error al procesar la pregunta: {error}"


# ---------------------------------------------------------------------------
# Estado de la sesion
# ---------------------------------------------------------------------------
if "mensajes" not in st.session_state:
    reiniciar_conversacion()

# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("TechNova Assistant")
    st.caption("Consulta los datos de la tienda y sus documentos, en castellano o en inglés.")
    mostrar = st.checkbox("Mostrar detalles técnicos", value=True)
    if st.button("Nueva conversación", width='stretch'):
        reiniciar_conversacion()
        st.rerun()
    st.subheader("Preguntas de ejemplo")
    for i, ejemplo in enumerate(EJEMPLOS):
        if st.button(ejemplo, key=f"ej{i}", width='stretch'):
            st.session_state.pendiente = ejemplo
    st.divider()
    st.caption("Solo lectura: el asistente no puede modificar datos.")

# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
st.header("Asistente de la tienda")

if not config.GOOGLE_API_KEY or not config.LLM_MODEL:
    st.error("Falta configurar GOOGLE_API_KEY y LLM_MODEL en el archivo .env.")
    st.stop()

iniciar()

for m in st.session_state.mensajes:
    with st.chat_message(m["rol"]):
        st.markdown(m["contenido"])
        if m["rol"] == "assistant" and mostrar:
            mostrar_detalles(m["meta"])

pregunta = st.chat_input("Escribe tu pregunta...") or st.session_state.pop("pendiente", None)

if pregunta:
    st.session_state.mensajes.append({"rol": "user", "contenido": pregunta})
    with st.chat_message("user"):
        st.markdown(pregunta)

    with st.chat_message("assistant"):
        try:
            from src.agent.graph import responder

            with st.spinner("Pensando..."):
                r = responder(pregunta, st.session_state.historial)
            st.session_state.historial = r["historial_nuevo"]
            meta = {k: r.get(k) for k in ("ruta", "idioma", "justificacion", "latencia_s", "fuentes")}
            st.markdown(r["respuesta"])
            if mostrar:
                mostrar_detalles(meta)
            st.session_state.mensajes.append(
                {"rol": "assistant", "contenido": r["respuesta"], "meta": meta})
        except Exception as error:
            st.error(mensaje_de_error(error))
