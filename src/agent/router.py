"""Router: decide de que fuente sale la respuesta (T-21, RF-05).

Una llamada al LLM devuelve un JSON con la ruta, el idioma, la justificacion, la
pregunta autosuficiente y la consulta en castellano para los documentos (D-20).
"""
import json
import re

from src.agent.prompts import RUTAS, prompt_router
from src.llm import invocar

MAX_MENSAJES_HISTORIAL = 6


def _historial_a_texto(historial: list) -> str:
    if not historial:
        return ""
    lineas = []
    for rol, texto in historial[-MAX_MENSAJES_HISTORIAL:]:
        lineas.append(f"{'Usuario' if rol == 'human' else 'Asistente'}: {texto}")
    return "Historial reciente:\n" + "\n".join(lineas) + "\n\n"


def parsear_decision(texto: str, pregunta: str = ""):
    """Convierte la respuesta del LLM en un diccionario valido, o None si no se puede."""
    t = texto.strip()
    bloque = re.search(r"```(?:json)?\s*(.*?)```", t, flags=re.S | re.I)
    if bloque:
        t = bloque.group(1).strip()
    objeto = re.search(r"\{.*\}", t, flags=re.S)
    if not objeto:
        return None
    try:
        d = json.loads(objeto.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(d, dict) or d.get("ruta") not in RUTAS:
        return None
    return {
        "ruta": d["ruta"],
        "idioma": d.get("idioma") if d.get("idioma") in ("es", "en") else "es",
        "justificacion": str(d.get("justificacion", "")),
        "pregunta_autonoma": str(d.get("pregunta_autonoma") or pregunta),
        "consulta_documentos": str(d.get("consulta_documentos") or ""),
        "mensaje_aclaracion": str(d.get("mensaje_aclaracion") or ""),
    }


def decidir(pregunta: str, historial: list, hoy: str) -> dict:
    """Clasifica la pregunta. Si el LLM no devuelve un JSON valido tras 2 intentos,
    usa la ruta "hibrida" (consulta ambas fuentes, ambas de solo lectura)."""
    mensajes = [("system", prompt_router(hoy)),
                ("human", f"{_historial_a_texto(historial)}Pregunta actual: {pregunta}")]
    for _ in range(2):
        respuesta = invocar(mensajes)
        decision = parsear_decision(respuesta, pregunta)
        if decision:
            return decision
        mensajes += [("ai", respuesta),
                     ("human", "Responde únicamente con el objeto JSON pedido, sin texto adicional.")]
    return {"ruta": "hibrida", "idioma": "es", "pregunta_autonoma": pregunta,
            "justificacion": "El router no devolvió un JSON válido; se consultan ambas fuentes.",
            "consulta_documentos": pregunta, "mensaje_aclaracion": ""}
