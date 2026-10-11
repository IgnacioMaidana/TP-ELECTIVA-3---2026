"""Chat de consola con el agente (prueba manual antes de la interfaz).

Uso:  python -m scripts.chat          (escribir 'salir' para terminar)
"""
from src.agent.graph import responder


def main():
    historial = []
    print("Agente TechNova (escribe 'salir' para terminar)")
    while True:
        pregunta = input("\nTú> ").strip()
        if pregunta.lower() in {"salir", "exit", ""}:
            break
        r = responder(pregunta, historial)
        historial = r["historial_nuevo"]
        print(f"\n[ruta: {r['ruta']} | idioma: {r['idioma']} | {r['latencia_s']} s]")
        print(f"[motivo: {r.get('justificacion', '')}]\n")
        print(r["respuesta"])
        f = r.get("fuentes", {})
        if f.get("sql"):
            print(f"\n  SQL: {f['sql']}")
        for d in f.get("documentos", []):
            print(f"  Doc: {d['cita']} (similitud {d['similitud']})")


if __name__ == "__main__":
    main()
