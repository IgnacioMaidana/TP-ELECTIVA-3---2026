"""Ejecuta la suite de evaluacion contra el agente real (T-30, T-31, T-43).

Uso (desde la raiz, con el entorno virtual activo y la base levantada):

    python -m tests.run_eval                       # una corrida completa
    python -m tests.run_eval --repeticiones 2      # dos corridas (mide la variacion)
    python -m tests.run_eval --tipos sql,rag       # solo algunos tipos
    python -m tests.run_eval --ids SQL-03,HIB-01   # solo algunas preguntas

Cada pregunta se evalua en cuatro dimensiones:
  ruta       el agente eligio la fuente correcta (RF-05, CA-10)
  respuesta  el contenido es correcto: los DATOS que devolvio la base coinciden con una
             consulta de referencia escrita a mano, o el texto/fuentes cumplen lo esperado
  idioma     respondio en el idioma de la pregunta (RF-02)
  seguro     ningun SQL ejecutado viola las reglas del validador (RNF-01)

Una pregunta esta APROBADA si cumple las cuatro.

Genera docs/eval_resultados.md (tablas para el informe) y docs/eval_resultados.json.
Consume cuota del LLM gratuito: cada corrida usa unas 70 llamadas.
"""
import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import yaml

from src import config, llm
from src.agent.graph import responder
from src.sql_tool.executor import ejecutar_consulta
from src.sql_tool.validator import validar_sql
from tests.evaluacion import (comparar_filas, contiene_alguna, contiene_todas, idioma_de_texto,
                              resumir)

RAIZ = Path(__file__).resolve().parent.parent
PREGUNTAS = Path(__file__).resolve().parent / "eval_questions.yaml"
SALIDA_MD = RAIZ / "docs" / "eval_resultados.md"
SALIDA_JSON = RAIZ / "docs" / "eval_resultados.json"


def cargar_preguntas() -> list:
    return yaml.safe_load(PREGUNTAS.read_text(encoding="utf-8"))


def _rutas(item: dict) -> list:
    r = item["ruta"]
    return r if isinstance(r, list) else [r]


def resolver_variables(item: dict) -> dict:
    """Reemplaza {nombre} en la pregunta por el valor que devuelve su consulta.
    Devuelve una copia del item, o None si la consulta no devuelve datos."""
    item = dict(item)
    for nombre, sql in (item.get("variables") or {}).items():
        r = ejecutar_consulta(sql)
        if not r.ok or not r.filas:
            return None
        valor = str(list(r.filas[0].values())[0])
        for campo in ("pregunta", "sql_referencia"):
            if item.get(campo):
                item[campo] = item[campo].replace("{" + nombre + "}", valor)
    return item


def evaluar(item: dict, estado: dict, ref_filas) -> dict:
    """Aplica todas las comprobaciones de un item al estado final del agente."""
    fallos = []
    respuesta = estado.get("respuesta", "")
    fuentes = estado.get("fuentes") or {}

    ruta_ok = estado.get("ruta") in _rutas(item)
    if not ruta_ok:
        fallos.append(f"ruta: esperada {_rutas(item)}, obtenida {estado.get('ruta')}")

    respuesta_ok = True

    def falla(mensaje):
        nonlocal respuesta_ok
        respuesta_ok = False
        fallos.append(mensaje)

    if ref_filas is not None:
        if "datos" not in fuentes and ref_filas:
            falla("no hay datos de la base en la respuesta")
        else:
            opc = item.get("comparar") or {}
            ok, detalle = comparar_filas(ref_filas, fuentes.get("datos") or [],
                                         exacto=opc.get("exacto", False),
                                         tolerancia=opc.get("tolerancia", 0.01))
            if not ok:
                falla(f"datos: {detalle}")
    if item.get("sin_sql") and fuentes.get("sql"):
        falla("ejecutó SQL y no debía")
    if item.get("sin_fuentes") and fuentes:
        falla("consultó fuentes y no debía")
    if item.get("usa_documentos"):
        citas = [d["cita"] for d in fuentes.get("documentos") or []]
        if not citas:
            falla("no recuperó documentos")
        elif item.get("documento") and not any(item["documento"] in c for c in citas):
            falla(f"no usó el documento '{item['documento']}'")
    if item.get("debe_contener") and not contiene_todas(respuesta, item["debe_contener"]):
        falla(f"la respuesta no contiene {item['debe_contener']}")
    if item.get("debe_contener_alguno") and not contiene_alguna(respuesta, item["debe_contener_alguno"]):
        falla("la respuesta no contiene ninguna de las expresiones esperadas")
    if item.get("no_debe_contener") and contiene_alguna(respuesta, item["no_debe_contener"]):
        falla("la respuesta contiene una expresión prohibida")

    idioma_ok = estado.get("idioma") == item["idioma"] and idioma_de_texto(respuesta) in (item["idioma"], "?")
    if not idioma_ok:
        fallos.append(f"idioma: esperado {item['idioma']}, router {estado.get('idioma')}, "
                      f"texto {idioma_de_texto(respuesta)}")

    seguro = True
    if fuentes.get("sql") and not validar_sql(fuentes["sql"]).ok:
        seguro = False
        fallos.append("el SQL ejecutado no pasa el validador")

    return {"ruta_ok": ruta_ok, "respuesta_ok": respuesta_ok, "idioma_ok": idioma_ok,
            "seguro": seguro, "aprobada": ruta_ok and respuesta_ok and idioma_ok and seguro,
            "fallos": fallos}


def correr_una_vez(items: list, numero: int) -> list:
    """Evalua todas las preguntas una vez. Devuelve la lista de resultados."""
    resultados = []
    for i, original in enumerate(items, start=1):
        item = resolver_variables(original)
        if item is None:
            print(f"[{i}/{len(items)}] {original['id']}  OMITIDA (la consulta de variables no devolvió datos)")
            continue

        ref_filas, error_ref = None, None
        if item.get("sql_referencia"):
            ref = ejecutar_consulta(item["sql_referencia"])
            if ref.ok:
                ref_filas = ref.filas
            else:
                error_ref = ref.error

        espera_inicial = llm.espera_acumulada_s
        inicio = time.monotonic()
        try:
            estado = responder(item["pregunta"], [tuple(t) for t in item.get("historial", [])])
            error = None
        except Exception as e:                                  # p. ej. cuota agotada
            estado, error = {}, str(e)[:200]
        latencia = round(time.monotonic() - inicio, 1)
        neta = round(max(0.0, latencia - (llm.espera_acumulada_s - espera_inicial)), 1)

        if error:
            evaluacion = {"ruta_ok": False, "respuesta_ok": False, "idioma_ok": False, "seguro": True,
                          "aprobada": False, "fallos": [f"error del agente: {error}"]}
        elif error_ref:
            evaluacion = evaluar({**item, "sql_referencia": None}, estado, None)
            evaluacion["respuesta_ok"], evaluacion["aprobada"] = False, False
            evaluacion["fallos"].append(f"la consulta de referencia falló: {error_ref}")
        else:
            evaluacion = evaluar(item, estado, ref_filas)

        fuentes = estado.get("fuentes") or {}
        resultado = {
            "corrida": numero, "id": item["id"], "tipo": item["tipo"], "pregunta": item["pregunta"],
            "ruta_esperada": "/".join(_rutas(item)), "ruta_obtenida": estado.get("ruta"),
            "conjunto": item.get("conjunto", "independiente"),
            "latencia_s": latencia, "latencia_neta_s": neta, "intentos_sql": fuentes.get("intentos_sql"),
            "sql": fuentes.get("sql"), "respuesta": (estado.get("respuesta") or "")[:400],
            **evaluacion,
        }
        resultados.append(resultado)
        marca = "OK " if resultado["aprobada"] else "FALLA"
        print(f"[{i}/{len(items)}] {marca} {item['id']:<7} ruta={resultado['ruta_obtenida']} ({latencia} s)")
        for f in resultado["fallos"]:
            print(f"           - {f}")
    return resultados


def _celda(ok):
    return "✔" if ok else "✘"


def escribir_reporte(corridas: list, meta: dict, salida_md: Path = None, salida_json: Path = None) -> None:
    """Escribe el reporte en markdown y json (por defecto docs/eval_resultados.*)."""
    salida_md = salida_md or SALIDA_MD
    salida_json = salida_json or SALIDA_JSON
    salida_md.parent.mkdir(parents=True, exist_ok=True)
    todos = [r for c in corridas for r in c]
    lineas = [
        "# Resultados de la evaluación del agente", "",
        f"- Fecha: {meta['fecha']}", f"- Modelo: {meta['modelo']}",
        f"- Preguntas por corrida: {meta['preguntas']} · corridas: {len(corridas)}",
        f"- Umbral de latencia: {15} s (RNF-03)", "",
        "## Resumen por tipo (todas las corridas)", "",
        "| Tipo | Preguntas | Aprobadas | Ruta | Respuesta | Idioma | Seguro | Latencia media | Latencia neta | ≤ 15 s |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for tipo, m in resumir(todos).items():
        lineas.append(f"| {tipo} | {m['n']} | {m['aprobadas']} ({m['pct_aprobadas']} %) | {m['pct_ruta']} % | "
                      f"{m['pct_respuesta']} % | {m['pct_idioma']} % | {m['pct_seguro']} % | "
                      f"{m['latencia_media_s']} s | {m['latencia_neta_media_s']} s | {m['pct_bajo_limite']} % |")

    lineas += ["", "La latencia total incluye las pausas que impone el nivel gratuito del LLM "
               "(LLM_PAUSA_SEGUNDOS entre llamadas). La latencia neta las descuenta.", "",
               "## Generalización: preguntas parecidas a los ejemplos del prompt vs. independientes", "",
               "| Conjunto | Preguntas | Aprobadas |", "|---|---|---|"]
    for conjunto in ("ejemplo", "independiente"):
        grupo = [r for r in todos if r.get("conjunto") == conjunto]
        if grupo:
            ap = sum(r["aprobada"] for r in grupo)
            lineas.append(f"| {conjunto} | {len(grupo)} | {ap} ({round(100 * ap / len(grupo))} %) |")

    if len(corridas) > 1:
        lineas += ["", "## Variación entre corridas", "",
                   "| Corrida | Aprobadas | % |", "|---|---|---|"]
        for c in corridas:
            m = resumir(c)["TOTAL"]
            lineas.append(f"| {c[0]['corrida'] if c else '-'} | {m['aprobadas']} de {m['n']} | {m['pct_aprobadas']} % |")
        por_id = {}
        for r in todos:
            por_id.setdefault(r["id"], []).append(r)
        inestables = [i for i, rs in por_id.items()
                      if len({x["aprobada"] for x in rs}) > 1 or len({x["ruta_obtenida"] for x in rs}) > 1]
        lineas.append("")
        lineas.append("Preguntas con resultado distinto entre corridas: "
                      + (", ".join(inestables) if inestables else "ninguna") + ".")

    ultima = corridas[-1]
    lineas += ["", f"## Detalle de la última corrida (n.º {ultima[0]['corrida'] if ultima else '-'})", "",
               "| ID | Ruta esperada → obtenida | Ruta | Resp. | Idioma | Seguro | Latencia | Intentos SQL |",
               "|---|---|---|---|---|---|---|---|"]
    for r in ultima:
        lineas.append(f"| {r['id']} | {r['ruta_esperada']} → {r['ruta_obtenida']} | {_celda(r['ruta_ok'])} | "
                      f"{_celda(r['respuesta_ok'])} | {_celda(r['idioma_ok'])} | {_celda(r['seguro'])} | "
                      f"{r['latencia_s']} s | {r['intentos_sql'] or '-'} |")
    fallas = [r for r in ultima if not r["aprobada"]]
    lineas += ["", "## Fallos de la última corrida", ""]
    if not fallas:
        lineas.append("Sin fallos.")
    for r in fallas:
        lineas.append(f"- **{r['id']}** — {r['pregunta']}")
        for f in r["fallos"]:
            lineas.append(f"  - {f}")
    salida_md.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    salida_json.write_text(json.dumps({"meta": meta, "corridas": corridas}, ensure_ascii=False, indent=2),
                           encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Evalua el agente con eval_questions.yaml")
    ap.add_argument("--repeticiones", type=int, default=1)
    ap.add_argument("--tipos", help="tipos separados por coma (sql,rag,hibrida,fuera_de_alcance,maliciosa)")
    ap.add_argument("--ids", help="ids separados por coma (SQL-01,RAG-02)")
    args = ap.parse_args()

    items = cargar_preguntas()
    if args.tipos:
        items = [i for i in items if i["tipo"] in args.tipos.split(",")]
    if args.ids:
        items = [i for i in items if i["id"] in args.ids.split(",")]

    print("Cargando modelos...")          # evita que la primera pregunta incluya la carga (~30 s)
    from src.agent.graph import _grafo
    from src.rag.retriever import precalentar
    precalentar()
    _grafo()

    corridas = []
    for n in range(1, args.repeticiones + 1):
        print(f"\n=== Corrida {n} de {args.repeticiones} ({len(items)} preguntas) ===")
        corridas.append(correr_una_vez(items, n))

    meta = {"fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "modelo": config.LLM_MODEL,
            "preguntas": len(items)}
    if args.ids or args.tipos:      # corrida parcial: no pisa el reporte completo
        marca = datetime.now().strftime("%Y%m%d_%H%M")
        salida_md = RAIZ / "docs" / f"eval_parcial_{marca}.md"
        salida_json = RAIZ / "docs" / f"eval_parcial_{marca}.json"
    else:
        salida_md, salida_json = SALIDA_MD, SALIDA_JSON
    escribir_reporte(corridas, meta, salida_md, salida_json)

    print("\n=== Resumen ===")
    for tipo, m in resumir([r for c in corridas for r in c]).items():
        print(f"{tipo:<18} {m['aprobadas']}/{m['n']} aprobadas ({m['pct_aprobadas']} %)  "
              f"latencia media {m['latencia_media_s']} s (neta {m['latencia_neta_media_s']} s)")
    print(f"\nReporte: {salida_md}")


if __name__ == "__main__":
    main()
