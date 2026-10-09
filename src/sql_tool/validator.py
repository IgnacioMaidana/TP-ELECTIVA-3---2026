"""Validador del SQL generado por el LLM

Decide si una consulta se puede ejecutar contra la base y, si es seguro,
devuelve la version final con un limite de filas (TOP).

Defensa en profundidad: cada consulta debe superar TODAS estas capas.

  Capa 1  Texto: no vacia, tamano maximo, comillas cerradas, SIN comentarios.
  Capa 2  Una sola sentencia (se tolera un unico ';' al final).
  Capa 3  Palabras prohibidas en el CODIGO (los textos entre comillas se
          ignoran, porque son datos y no instrucciones).
  Capa 4  Parser (sqlglot, dialecto T-SQL): debe ser exactamente un SELECT.
  Capa 5  Estructura: sin SELECT INTO, solo las 7 tablas del dominio (esquema
          dbo, sin otras bases ni tablas del sistema), sin funciones de acceso
          externo y sin condiciones constantes (OR 1=1).
  Capa 6  Limite de filas: se agrega TOP si falta.

Decisiones de diseno (documentadas en spec/plan):
  - Se acepta un unico ';' final ("SELECT 1;").
  - Se rechaza cualquier comentario (-- o /* */), aunque sea inocente.
  - "WHERE nombre = 'DROP TABLE'" se ACEPTA: la palabra esta dentro de un
    texto, es un dato. Un filtro por palabras la rechazaria por error; separar
    codigo de datos es justamente para lo que sirve analizar la sintaxis.
  - Se rechazan UNION/INTERSECT/EXCEPT (patron tipico de inyeccion).
  - Se rechazan comparaciones entre constantes (1=1, 'a'='a').

Complemento: el ejecutor debe usar el usuario de solo lectura y limitar las
filas leidas (fetchmany); este modulo no reemplaza esos controles.
"""
import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

TABLAS_PERMITIDAS = frozenset({
    "categorias", "clientes", "productos", "pedidos",
    "detalle_pedidos", "envios", "resenas",
})

LONGITUD_MAXIMA = 4000

# Palabras que nunca deben aparecer en el codigo (fuera de textos entre comillas)
_PROHIBIDAS = re.compile(
    r"\b(?:insert|update|delete|drop|alter|truncate|create|merge|grant|revoke|deny|"
    r"exec|execute|declare|union|intersect|except|into|waitfor|"
    r"openrowset|openquery|opendatasource|openxml|bulk|backup|restore|"
    r"shutdown|dbcc|kill|reconfigure|outfile|infile|program|copy|load|"
    r"xp_\w*|sp_\w*)\b"
)

_FUNCIONES_PROHIBIDAS = frozenset({"openrowset", "openquery", "opendatasource", "openxml"})

_COMPARACIONES = (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Like)


@dataclass(frozen=True)
class ResultadoValidacion:
    """Resultado de validar una consulta."""

    ok: bool
    motivo: str = ""   # por que se rechazo (vacio si ok)
    sql: str = ""      # SQL final listo para ejecutar (vacio si se rechazo)


def _rechazo(motivo: str) -> ResultadoValidacion:
    return ResultadoValidacion(ok=False, motivo=motivo, sql="")


def _analizar_texto(sql: str):
    """Recorre el SQL caracter a caracter.

    Devuelve (codigo, hay_comentario, sin_cerrar) donde `codigo` es el SQL con
    el CONTENIDO de textos ('...'), identificadores "..." y [...] eliminado.
    Un '--' o '/*' dentro de un texto NO cuenta como comentario.
    """
    codigo = []
    cierre = None            # caracter que cerrara el texto/identificador actual
    hay_comentario = False
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if cierre:
            if c == cierre:
                if cierre in ("'", '"') and sql[i + 1:i + 2] == cierre:
                    i += 2           # comilla duplicada dentro del texto ('')
                    continue
                cierre = None
                codigo.append(c)
            # el contenido del texto se descarta
        else:
            if c in ("'", '"'):
                cierre = c
                codigo.append(c)
            elif c == "[":
                cierre = "]"
                codigo.append(c)
            else:
                if sql.startswith("--", i) or sql.startswith("/*", i):
                    hay_comentario = True
                codigo.append(c)
        i += 1
    return "".join(codigo), hay_comentario, cierre is not None


def validar_sql(sql: str, max_filas: int = 100) -> ResultadoValidacion:
    """Valida `sql` y devuelve un ResultadoValidacion.

    Args:
        sql: consulta propuesta por el LLM.
        max_filas: valor de TOP que se agrega cuando la consulta no limita filas.
    """
    # --- Capa 1: texto ---------------------------------------------------
    if sql is None or not sql.strip():
        return _rechazo("La consulta está vacía.")
    sql = sql.strip()
    if sql.endswith(";"):                       # se tolera UN ';' final
        sql = sql[:-1].rstrip()
    if not sql:
        return _rechazo("La consulta está vacía.")
    if len(sql) > LONGITUD_MAXIMA:
        return _rechazo(f"La consulta supera {LONGITUD_MAXIMA} caracteres.")

    codigo, hay_comentario, sin_cerrar = _analizar_texto(sql)
    if sin_cerrar:
        return _rechazo("Hay comillas o corchetes sin cerrar.")
    if hay_comentario:
        return _rechazo("No se permiten comentarios (-- o /* */).")

    # --- Capa 2: una sola sentencia -----------------------------------------
    if ";" in codigo:
        return _rechazo("Solo se permite una sentencia por consulta.")
    if "@" in codigo:
        return _rechazo("No se permiten variables (@) en la consulta.")

    # --- Capa 3: palabras prohibidas (fuera de textos entre comillas) --------
    hallada = _PROHIBIDAS.search(codigo.lower())
    if hallada:
        return _rechazo(f"Instrucción no permitida: '{hallada.group(0).upper()}'. "
                        "Solo se permiten consultas SELECT de lectura.")

    # --- Capa 4: parser --------------------------------------------------
    try:
        sentencias = [s for s in sqlglot.parse(sql, read="tsql") if s is not None]
    except SqlglotError as error:
        return _rechazo(f"No se pudo interpretar la consulta como T-SQL válido: {error}")
    if len(sentencias) != 1:
        return _rechazo("Solo se permite una sentencia por consulta.")
    arbol = sentencias[0]
    if not isinstance(arbol, exp.Select):
        return _rechazo("Solo se permiten consultas SELECT.")

    # --- Capa 5: estructura -------------------------------------------------
    if arbol.find(exp.Into):
        return _rechazo("No se permite SELECT INTO.")

    for funcion in arbol.find_all(exp.Anonymous):
        nombre = str(funcion.name).lower()
        if nombre in _FUNCIONES_PROHIBIDAS or nombre.startswith(("xp_", "sp_")):
            return _rechazo(f"Función no permitida: {nombre.upper()}.")

    nombres_cte = {c.alias.lower() for c in arbol.find_all(exp.CTE) if c.alias}
    for tabla in arbol.find_all(exp.Table):
        if tabla.catalog:
            return _rechazo("No se permite consultar otras bases de datos.")
        if tabla.db and tabla.db.lower() != "dbo":
            return _rechazo(f"No se permite el esquema '{tabla.db}' (tablas del sistema).")
        nombre = (tabla.name or "").lower()
        if not tabla.db and nombre in nombres_cte:
            continue                            # referencia a una CTE
        if nombre not in TABLAS_PERMITIDAS:
            return _rechazo(f"Tabla no permitida: '{nombre or '?'}'. "
                            f"Tablas disponibles: {', '.join(sorted(TABLAS_PERMITIDAS))}.")

    for comparacion in arbol.find_all(*_COMPARACIONES):
        if isinstance(comparacion.this, exp.Literal) and isinstance(comparacion.expression, exp.Literal):
            return _rechazo("Condición constante entre valores literales "
                            "(por ejemplo 1=1), típica de una inyección.")

    # --- Capa 6: limite de filas -------------------------------------------
    tiene_limite = (
        bool(arbol.args.get("limit"))
        or bool(arbol.args.get("offset"))
        or re.search(r"\bselect\s+(?:distinct\s+)?top\b", codigo.lower()) is not None
    )
    if tiene_limite:
        return ResultadoValidacion(ok=True, sql=sql)

    con_top = arbol.copy()
    con_top.set("limit", exp.Limit(expression=exp.Literal.number(max_filas)))
    return ResultadoValidacion(ok=True, sql=con_top.sql(dialect="tsql"))
