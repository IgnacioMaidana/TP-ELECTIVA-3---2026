"""De la pregunta a las filas: LLM -> SQL -> validacion -> ejecucion (T-15).

Flujo de `generar_y_ejecutar`:
  1. Arma el prompt (esquema + reglas + ejemplos) y le pasa la pregunta al LLM.
  2. Limpia la respuesta para quedarse solo con el SQL.
  3. Ejecuta con el ejecutor (que valida antes de tocar la base).
  4. Si falla (validacion o SQL Server), le devuelve el error al LLM y reintenta,
     hasta SQL_RETRIES veces (RF-09).

Este modulo no redacta la respuesta final para el usuario: eso lo hace el
nodo "sintetizador" del agente.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

from src import config
from src.llm import invocar
from src.sql_tool.executor import ResultadoEjecucion, ejecutar_consulta
from src.sql_tool.schema_prompt import construir_prompt_sql

NO_SQL = "NO_SQL"


@dataclass
class ResultadoSQL:
    """Resultado completo de responder una pregunta con SQL."""

    ok: bool
    sql: str = ""                                   # ultimo SQL ejecutado o intentado
    ejecucion: Optional[ResultadoEjecucion] = None  # filas, columnas, truncado
    intentos: int = 0
    sin_sql: bool = False                           # el LLM dijo que no se puede con SQL
    error: str = ""
    historial: list = field(default_factory=list)   # un dict por intento: sql, etapa, error


def extraer_sql(texto: str) -> str:
    """Quita bloques de codigo markdown y prefijos ("SQL:") de la respuesta del LLM."""
    t = texto.strip()
    bloque = re.search(r"```(?:sql|tsql|t-sql)?\s*(.*?)```", t, flags=re.S | re.I)
    if bloque:
        t = bloque.group(1).strip()
    t = re.sub(r"^\s*(?:sql|t-sql)\s*:\s*", "", t, flags=re.I)
    return t.strip()


def generar_y_ejecutar(pregunta: str,
                       historial_chat: list = None,
                       contexto_rag: str = None,
                       hoy=None) -> ResultadoSQL:
    """Responde `pregunta` consultando la base.

    Args:
        pregunta: pregunta del usuario (castellano o ingles).
        historial_chat: mensajes previos como tuplas (rol, texto) para preguntas
            de seguimiento ("¿y el mes anterior?").
        contexto_rag: fragmentos de documentos (ruta hibrida), por ejemplo el plazo.
        hoy: fecha de referencia para el prompt (por defecto, hoy).
    """
    mensajes = [("system", construir_prompt_sql(hoy=hoy, contexto_rag=contexto_rag))]
    mensajes += list(historial_chat or [])
    mensajes.append(("human", pregunta))

    resultado = ResultadoSQL(ok=False)
    for intento in range(1, config.SQL_RETRIES + 2):       # 1 intento + N reintentos
        respuesta = invocar(mensajes)
        sql = extraer_sql(respuesta)
        resultado.intentos = intento

        if sql.upper().startswith(NO_SQL):
            resultado.sin_sql = True
            resultado.error = "La pregunta no se puede responder con las tablas disponibles."
            return resultado

        ejecucion = ejecutar_consulta(sql)
        resultado.sql = ejecucion.sql or sql
        resultado.ejecucion = ejecucion
        resultado.historial.append({"intento": intento, "sql": sql,
                                    "etapa": ejecucion.etapa, "error": ejecucion.error})
        if ejecucion.ok:
            resultado.ok = True
            resultado.error = ""
            return resultado

        resultado.error = ejecucion.error
        mensajes.append(("ai", sql))
        mensajes.append(("human",
                         f"Esa consulta falló ({ejecucion.etapa}): {ejecucion.error}\n"
                         "Corrígela y responde solo con el SQL corregido."))
    return resultado
