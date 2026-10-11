"""Estado compartido del grafo del agente (T-20).

Cada nodo recibe el estado completo y devuelve solo las claves que modifica.
"""
from typing import TypedDict


class EstadoAgente(TypedDict, total=False):
    # --- entrada ---
    pregunta: str            # lo que escribio el usuario
    historial: list          # mensajes previos como tuplas (rol, texto): "human" / "ai"
    hoy: str                 # fecha de referencia AAAA-MM-DD

    # --- decision del router ---
    ruta: str                # sql | rag | hibrida | aclarar | fuera_de_alcance | rechazar
    idioma: str              # "es" o "en"
    justificacion: str       # por que eligio esa ruta (RF-16)
    pregunta_autonoma: str   # la pregunta reescrita sin depender del historial
    consulta_documentos: str  # la pregunta reescrita en castellano para buscar en los PDFs (D-20)
    mensaje_aclaracion: str  # pregunta de aclaracion (solo ruta "aclarar")

    # --- resultados de las herramientas ---
    fragmentos: list         # fragmentos de PDFs recuperados (RAG)
    resultado_sql: object    # ResultadoSQL de la herramienta SQL

    # --- salida ---
    respuesta: str
    fuentes: dict            # {"sql", "filas", "truncado", "intentos_sql", "documentos": [...]}
