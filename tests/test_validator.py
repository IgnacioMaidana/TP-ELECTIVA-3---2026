"""
Contrato que se espera del validador:

    resultado = validar_sql("SELECT ...")
    resultado.ok      -> bool   True si se puede ejecutar
    resultado.motivo  -> str    por que se rechazo (vacio si ok)
    resultado.sql     -> str    SQL final listo para ejecutar (con TOP si faltaba)
"""
import pytest

from src.sql_tool.validator import validar_sql

# ---------------------------------------------------------------------------
# 1) Consultas que SI deben aceptarse
# ---------------------------------------------------------------------------
PERMITIDAS = [
    "SELECT 1;",
    "SELECT COUNT(*) FROM dbo.clientes",
    "SELECT TOP 5 nombre, precio FROM productos ORDER BY precio DESC",
    "SELECT pais, COUNT(*) AS total FROM clientes GROUP BY pais",
    "SELECT * FROM clientes WHERE nombre = 'DROP TABLE'",
    # CTE: empieza con WITH pero sigue siendo una lectura
    "WITH v AS (SELECT id_producto, SUM(cantidad) AS u FROM detalle_pedidos "
    "GROUP BY id_producto) SELECT TOP 3 * FROM v ORDER BY u DESC",
    "SELECT c.nombre, p.id_pedido, e.estado_envio "
    "FROM pedidos AS p "
    "JOIN clientes AS c ON c.id_cliente = p.id_cliente "
    "JOIN envios AS e ON e.id_pedido = p.id_pedido",
    "SELECT nombre FROM clientes "
    "WHERE id_cliente IN (SELECT id_cliente FROM pedidos WHERE estado = 'entregado')",
]


@pytest.mark.parametrize("sql", PERMITIDAS)
def test_consultas_legitimas_se_aceptan(sql):
    assert validar_sql(sql).ok, f"Deberia aceptarse: {sql}"


# ---------------------------------------------------------------------------
# 2) Consultas que DEBEN rechazarse: (sql, por que es peligrosa)
# ---------------------------------------------------------------------------
BLOQUEADAS = [
    ("DROP TABLE clientes", "DDL: borra una tabla"),
    ("DELETE FROM pedidos", "escritura: borra filas"),
    ("UPDATE productos SET precio = 0", "escritura: modifica filas"),
    ("SELECT 1; DROP TABLE clientes", "dos sentencias encadenadas"),
    ("SELECT * FROM sys.sql_logins", "tabla del sistema"),
    ("SELECT * INTO copia FROM clientes", "SELECT INTO crea una tabla"),
    ("EXEC xp_cmdshell 'dir'", "ejecuta comandos"),
    ("SELECT * FROM otra_tabla", "tabla fuera de las 7 permitidas"),
    ("", "consulta vacia"),
    ("SELECT * FROM clientes -- comentario", "comentario al final"),
    ("SELECT * FROM clientes WHERE 1=1", "condicion constante"),
    ("SELECT * FROM clientes WHERE 'a'='a'", "comparacion entre constantes"),
    ("SELECT * FROM clientes WHERE nombre = 'a' OR 1=1", "condicion con OR y constante"),
    ("WAITFOR DELAY '00:00:30'", "puede colgar el servidor"),
    ("SELECT * FROM OPENROWSET('...')", "lee fuentes externas"),
    ("dRoP TABLE clientes", "DDL con mayusculas y minusculas mezcladas"),
    ("SELECT * FROM clientes /* INSERT INTO clientes (nombre) VALUES ('intruso') */",
     "INSERT oculto dentro de un comentario"),
    ("SELECT * FROM clientes -- comentario\nINSERT INTO clientes (nombre) VALUES ('intruso')",
     "INSERT despues de un comentario"),
    ("SELECT * FROM master.dbo.sysdatabases", "consulta a otra base de datos"),
]


@pytest.mark.parametrize("sql,motivo", BLOQUEADAS)
def test_consultas_peligrosas_se_rechazan(sql, motivo):
    resultado = validar_sql(sql)
    assert not resultado.ok, f"Deberia rechazarse ({motivo}): {sql!r}"
    assert resultado.motivo, "Un rechazo debe explicar el motivo"


# ---------------------------------------------------------------------------
# 3) Comportamiento: el validador tambien transforma el SQL
# ---------------------------------------------------------------------------
def test_agrega_top_si_falta():
    resultado = validar_sql("SELECT * FROM productos")
    assert resultado.ok
    assert "TOP" in resultado.sql.upper()


def test_respeta_top_existente():
    resultado = validar_sql("SELECT TOP 5 * FROM productos")
    assert resultado.sql.upper().count("TOP") == 1
