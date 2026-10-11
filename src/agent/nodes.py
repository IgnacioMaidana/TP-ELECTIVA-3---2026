"""Nodos del grafo del agente (T-22, T-23, T-24).

Cada nodo es una funcion estado -> actualizacion del estado, sin dependencia de
LangGraph, por lo que se puede probar de forma aislada.
"""
from src.agent import router
from src.agent.prompts import mensaje, prompt_sintesis
from src.llm import invocar
from src.rag.retriever import buscar, formatear_contexto
from src.sql_tool.generador import generar_y_ejecutar

MAX_FILAS_AL_LLM = 30     # filas que se le muestran al sintetizador (el resto se resume)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
def nodo_router(estado: dict) -> dict:
    """Decide la ruta, el idioma y las reescrituras de la pregunta."""
    return router.decidir(estado["pregunta"], estado.get("historial", []), estado["hoy"])


def decidir_ruta(estado: dict) -> str:
    """Arista condicional posterior al router: que nodo sigue."""
    if estado["ruta"] in ("rag", "hibrida"):
        return "rag"
    if estado["ruta"] == "sql":
        return "sql"
    return "fijo"


def despues_de_rag(estado: dict) -> str:
    """En la ruta hibrida, tras buscar en los documentos se consulta la base."""
    return "sql" if estado["ruta"] == "hibrida" else "sintesis"


# ---------------------------------------------------------------------------
# Herramientas
# ---------------------------------------------------------------------------
def nodo_rag(estado: dict) -> dict:
    """Busca fragmentos en los PDFs usando la consulta reescrita en castellano."""
    consulta = estado.get("consulta_documentos") or estado.get("pregunta_autonoma") or estado["pregunta"]
    return {"fragmentos": buscar(consulta)}


def nodo_sql(estado: dict) -> dict:
    """Genera y ejecuta el SQL. En la ruta hibrida usa el contexto recuperado de los PDFs."""
    contexto = formatear_contexto(estado.get("fragmentos") or []) or None
    pregunta = estado.get("pregunta_autonoma") or estado["pregunta"]
    return {"resultado_sql": generar_y_ejecutar(pregunta, contexto_rag=contexto, hoy=estado["hoy"])}


# ---------------------------------------------------------------------------
# Respuestas sin consultar fuentes
# ---------------------------------------------------------------------------
def nodo_fijo(estado: dict) -> dict:
    """Rutas rechazar, fuera_de_alcance y aclarar: respuesta sin llamar al LLM."""
    idioma = estado.get("idioma", "es")
    if estado["ruta"] == "aclarar" and estado.get("mensaje_aclaracion"):
        texto = estado["mensaje_aclaracion"]
    else:
        texto = mensaje(estado["ruta"], idioma)
    return {"respuesta": texto, "fuentes": {}}


# ---------------------------------------------------------------------------
# Sintetizador
# ---------------------------------------------------------------------------
def _tabla(ejecucion) -> str:
    columnas = ejecucion.columnas
    lineas = [" | ".join(columnas)]
    for fila in ejecucion.filas[:MAX_FILAS_AL_LLM]:
        lineas.append(" | ".join(str(fila[c]) for c in columnas))
    return "\n".join(lineas)


def _fuentes(estado: dict) -> dict:
    fuentes = {}
    r = estado.get("resultado_sql")
    if r is not None:
        fuentes["sql"] = r.sql
        fuentes["intentos_sql"] = r.intentos
        if r.ejecucion is not None and r.ok:
            fuentes["filas"] = r.ejecucion.cantidad
            fuentes["truncado"] = r.ejecucion.truncado
            fuentes["datos"] = r.ejecucion.filas       # para mostrar la tabla en la interfaz
    if estado.get("fragmentos") is not None:
        fuentes["documentos"] = [{"cita": f.cita, "similitud": f.similitud, "texto": f.texto}
                                 for f in estado["fragmentos"]]
    return fuentes


def nodo_sintesis(estado: dict) -> dict:
    """Redacta la respuesta final en el idioma del usuario, citando las fuentes."""
    idioma = estado.get("idioma", "es")
    ruta = estado["ruta"]
    sql = estado.get("resultado_sql")
    fragmentos = estado.get("fragmentos")

    usa_bd = ruta in ("sql", "hibrida")
    usa_docs = ruta in ("rag", "hibrida")
    bd_ok = usa_bd and sql is not None and sql.ok
    docs_ok = usa_docs and bool(fragmentos)
    fuentes = _fuentes(estado)

    # Sin informacion de ninguna fuente aplicable: mensaje fijo, sin gastar una llamada al LLM
    if not bd_ok and not docs_ok:
        if usa_bd and sql is not None and sql.error and not sql.sin_sql:
            texto = mensaje("sql_error", idioma, error=sql.error)
        elif usa_bd and not usa_docs:
            texto = mensaje("sin_datos", idioma)
        else:
            texto = mensaje("sin_docs", idioma)
        return {"respuesta": texto, "fuentes": fuentes}

    partes = [f"Pregunta del usuario: {estado.get('pregunta_autonoma') or estado['pregunta']}"]
    partes.append("### Base de datos")
    if not usa_bd:
        partes.append("Estado: NO CONSULTADA")
    elif not bd_ok:
        motivo = "la pregunta no se puede responder con las tablas" if sql and sql.sin_sql else (sql.error if sql else "")
        partes.append(f"Estado: NO DISPONIBLE ({motivo})")
    else:
        e = sql.ejecucion
        partes.append("Estado: OK")
        partes.append(f"Consulta SQL ejecutada: {sql.sql}")
        partes.append(f"Filas devueltas: {e.cantidad} (truncado: {'sí' if e.truncado else 'no'})")
        if e.cantidad:
            partes.append(f"<datos>\n{_tabla(e)}\n</datos>")
            if e.cantidad > MAX_FILAS_AL_LLM:
                partes.append(f"(Se muestran las primeras {MAX_FILAS_AL_LLM} filas.)")
        else:
            partes.append("La consulta no devolvió filas.")
    partes.append("### Documentos")
    if not usa_docs:
        partes.append("Estado: NO CONSULTADOS")
    elif not docs_ok:
        partes.append("Estado: NINGÚN FRAGMENTO RELEVANTE")
    else:
        partes.append("Estado: ENCONTRADOS")
        partes.append(f"<documentos>\n{formatear_contexto(fragmentos)}\n</documentos>")

    respuesta = invocar([("system", prompt_sintesis(estado["hoy"], idioma)), ("human", "\n".join(partes))])
    return {"respuesta": respuesta, "fuentes": fuentes}
