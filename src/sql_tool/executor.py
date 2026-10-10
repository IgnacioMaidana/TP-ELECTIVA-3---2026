"""Ejecutor de consultas SQL de solo lectura (T-14).

Es el UNICO camino por el que el agente toca la base de datos. Garantias:

  1. Valida el SQL con validar_sql() ANTES de ejecutar (no existe forma de
     ejecutar una consulta sin validar).
  2. Se conecta con el usuario de solo lectura (agente_ro), nunca como admin.
  3. Aplica un timeout a la consulta (SQL_TIMEOUT_SEGUNDOS).
  4. Lee como maximo `max_filas` filas (fetchmany), aunque el SQL pida mas.
  5. Nunca lanza excepciones por errores de SQL: devuelve un resultado con el
     motivo, para que el agente pueda reintentar (RF-09).

Uso:
    resultado = ejecutar_consulta("SELECT COUNT(*) AS n FROM clientes")
    if resultado.ok: print(resultado.filas)
    else:            print(resultado.etapa, resultado.error)
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

import pyodbc

from src import config
from src.db import get_connection
from src.sql_tool.validator import validar_sql


@dataclass
class ResultadoEjecucion:
    """Resultado de ejecutar (o intentar ejecutar) una consulta."""

    ok: bool
    etapa: str = ""                 # "validacion" o "ejecucion" si fallo; vacio si ok
    error: str = ""                 # motivo legible, util para que el LLM corrija el SQL
    sql: str = ""                   # SQL que realmente se ejecuto (con TOP)
    columnas: list = field(default_factory=list)
    filas: list = field(default_factory=list)   # lista de diccionarios
    truncado: bool = False          # True si habia mas filas que max_filas

    @property
    def cantidad(self) -> int:
        """Cantidad de filas devueltas."""
        return len(self.filas)


def _normalizar(valor):
    """Convierte valores de la base a tipos simples (texto o numero)."""
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    return valor


def ejecutar_consulta(sql: str,
                      max_filas: int = None,
                      timeout: int = None) -> ResultadoEjecucion:
    """Valida y ejecuta `sql`. Ver el docstring del modulo para las garantias."""
    max_filas = max_filas or config.SQL_MAX_ROWS
    timeout = timeout or config.SQL_TIMEOUT_SEGUNDOS

    validacion = validar_sql(sql, max_filas=max_filas)
    if not validacion.ok:
        return ResultadoEjecucion(ok=False, etapa="validacion", error=validacion.motivo)

    try:
        con = get_connection(admin=False)
    except pyodbc.Error as e:
        return ResultadoEjecucion(ok=False, etapa="ejecucion",
                                  error=f"No se pudo conectar a la base: {e}")
    try:
        con.autocommit = True      # solo lectura: no se deja ninguna transaccion abierta
        con.timeout = timeout      # timeout de cada consulta, en segundos
        cursor = con.cursor()
        cursor.execute(validacion.sql)
        columnas = [c[0] for c in cursor.description] if cursor.description else []
        crudas = cursor.fetchmany(max_filas + 1) if columnas else []
        truncado = len(crudas) > max_filas
        filas = [
            {col: _normalizar(v) for col, v in zip(columnas, fila)}
            for fila in crudas[:max_filas]
        ]
        return ResultadoEjecucion(ok=True, sql=validacion.sql, columnas=columnas,
                                  filas=filas, truncado=truncado)
    except pyodbc.Error as e:
        # Se devuelve el mensaje de SQL Server para que el LLM pueda corregir
        return ResultadoEjecucion(ok=False, etapa="ejecucion", sql=validacion.sql,
                                  error=str(e)[:500])
    finally:
        con.close()
