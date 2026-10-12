"""Registro de cada pregunta en formato JSON por linea (T-27, RF-16, RNF-05).

Archivo: logs/agente.jsonl. Sirve de evidencia para el informe (CA-10: se ve
que ruta eligio el agente y por que).
"""
import json
import logging
from datetime import datetime

from src import config

RUTA_LOG = config.RAIZ / "logs" / "agente.jsonl"
logger = logging.getLogger("agente")


def registrar(estado: dict) -> None:
    """Guarda un resumen de la interaccion. Nunca interrumpe al agente si falla."""
    try:
        sql = estado.get("resultado_sql")
        evento = {
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "pregunta": estado.get("pregunta"),
            "idioma": estado.get("idioma"),
            "ruta": estado.get("ruta"),
            "justificacion": estado.get("justificacion"),
            "intentos_router": estado.get("intentos_router"),
            "router_respuesta_invalida": estado.get("respuesta_invalida") or None,
            "consulta_documentos": estado.get("consulta_documentos") or None,
            "sql": sql.sql if sql else None,
            "intentos_sql": sql.intentos if sql else None,
            "error_sql": (sql.error or None) if sql else None,
            "documentos": [{"cita": f.cita, "similitud": f.similitud}
                           for f in (estado.get("fragmentos") or [])] or None,
            "latencia_s": estado.get("latencia_s"),
            "respuesta": estado.get("respuesta"),
        }
        RUTA_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(RUTA_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(evento, ensure_ascii=False) + "\n")
        logger.info("ruta=%s idioma=%s latencia=%ss", evento["ruta"], evento["idioma"], evento["latencia_s"])
    except Exception:          # el registro es secundario
        logger.exception("No se pudo registrar la interaccion")
