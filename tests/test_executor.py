"""Pruebas del ejecutor (T-14). Son de INTEGRACION: necesitan SQL Server
levantado, el .env completo y los datos cargados (scripts.generar_datos)."""
from src.sql_tool.executor import ejecutar_consulta


def test_cuenta_clientes():
    r = ejecutar_consulta("SELECT COUNT(*) AS n FROM clientes")
    assert r.ok, r.error
    assert r.columnas == ["n"]
    assert r.filas[0]["n"] == 60


def test_devuelve_filas_como_diccionarios():
    r = ejecutar_consulta("SELECT TOP 3 id_producto, nombre, precio FROM productos ORDER BY id_producto")
    assert r.ok, r.error
    assert r.cantidad == 3
    assert set(r.filas[0]) == {"id_producto", "nombre", "precio"}
    assert isinstance(r.filas[0]["precio"], float)      # Decimal -> float


def test_agrega_top_automaticamente():
    r = ejecutar_consulta("SELECT * FROM pedidos", max_filas=10)
    assert r.ok, r.error
    assert r.cantidad == 10
    assert "TOP" in r.sql.upper()


def test_marca_truncado_si_el_sql_pide_mas_filas_que_el_limite():
    r = ejecutar_consulta("SELECT TOP 50 * FROM productos", max_filas=10)
    assert r.ok, r.error
    assert r.cantidad == 10
    assert r.truncado is True


def test_consulta_sin_resultados_no_es_error():
    r = ejecutar_consulta("SELECT * FROM pedidos WHERE id_cliente = 999999")
    assert r.ok, r.error
    assert r.cantidad == 0


def test_rechaza_sql_peligroso_antes_de_ejecutar():
    r = ejecutar_consulta("DROP TABLE clientes")
    assert not r.ok
    assert r.etapa == "validacion"
    assert r.error


def test_error_de_sql_server_se_devuelve_sin_lanzar_excepcion():
    r = ejecutar_consulta("SELECT columna_inexistente FROM clientes")
    assert not r.ok
    assert r.etapa == "ejecucion"
    assert r.error
