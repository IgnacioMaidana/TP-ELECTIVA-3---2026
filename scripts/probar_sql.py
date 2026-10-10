"""Prueba manual: pregunta -> SQL -> filas.

Uso (desde la raiz, con el entorno virtual activo):
    python -m scripts.probar_sql "¿Cuántos clientes compran por cada categoría?"
    python -m scripts.probar_sql          (modo interactivo, escribir 'salir' para terminar)
"""
import sys

from src.sql_tool.generador import generar_y_ejecutar


def responder(pregunta: str) -> None:
    r = generar_y_ejecutar(pregunta)
    print(f"\nIntentos: {r.intentos}")
    for h in r.historial:
        estado = "OK" if not h["error"] else f"FALLO ({h['etapa']}): {h['error']}"
        print(f"  - intento {h['intento']}: {estado}")
    if r.sin_sql:
        print("El modelo indica que no se puede responder con la base de datos.")
        return
    print("\nSQL ejecutado:\n" + r.sql)
    if not r.ok:
        print("\nNo se pudo responder:", r.error)
        return
    e = r.ejecucion
    print(f"\nFilas: {e.cantidad}" + ("  (truncado)" if e.truncado else ""))
    for fila in e.filas[:15]:
        print("  ", fila)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        responder(" ".join(sys.argv[1:]))
    else:
        while True:
            q = input("\nPregunta> ").strip()
            if q.lower() in {"salir", "exit", ""}:
                break
            responder(q)
