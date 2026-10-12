"""Muestra entradas de logs/agente.jsonl para diagnosticar una pregunta.

Uso:  python -m scripts.ver_log "calificación 1"          (ultimas 5 coincidencias)
      python -m scripts.ver_log "Mundial" -n 10
"""
import argparse
import json

from src.agent.logging_utils import RUTA_LOG


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("texto", help="texto a buscar dentro de la pregunta")
    ap.add_argument("-n", type=int, default=5)
    args = ap.parse_args()

    eventos = [json.loads(l) for l in RUTA_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    coincidencias = [e for e in eventos if args.texto.lower() in (e.get("pregunta") or "").lower()][-args.n:]
    for e in coincidencias:
        print("-" * 78)
        print(f"{e['fecha']} | ruta: {e['ruta']} | idioma: {e['idioma']} | intentos router: {e.get('intentos_router')}"
              f" | {e['latencia_s']} s")
        print("Pregunta:", e["pregunta"])
        print("Motivo:  ", e.get("justificacion"))
        if e.get("consulta_documentos"):
            print("Consulta a los documentos:", e["consulta_documentos"])
        for d in e.get("documentos") or []:
            print(f"   Documento: {d['cita']} (similitud {d['similitud']})")
        if e.get("sql"):
            print("SQL:", e["sql"])
        if e.get("router_respuesta_invalida"):
            print("Respuesta del router que no se pudo interpretar:", e["router_respuesta_invalida"])
        print("Respuesta:", (e.get("respuesta") or "")[:400].replace("\n", " "))
    if not coincidencias:
        print("Sin coincidencias.")


if __name__ == "__main__":
    main()
