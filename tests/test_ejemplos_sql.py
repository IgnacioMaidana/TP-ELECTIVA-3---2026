"""Cada ejemplo del prompt debe ser SQL valido y ejecutable (T-11).

- test_..._pasa_el_validador: no necesita base de datos.
- test_..._se_ejecuta: de INTEGRACION (necesita SQL Server y los datos cargados).
"""
import pytest

from src.sql_tool.ejemplos import EJEMPLOS
from src.sql_tool.executor import ejecutar_consulta
from src.sql_tool.validator import validar_sql

IDS = [e["pregunta"][:45] for e in EJEMPLOS]


@pytest.mark.parametrize("ejemplo", EJEMPLOS, ids=IDS)
def test_ejemplo_pasa_el_validador(ejemplo):
    resultado = validar_sql(ejemplo["sql"])
    assert resultado.ok, f"{ejemplo['pregunta']} -> {resultado.motivo}"


@pytest.mark.parametrize("ejemplo", EJEMPLOS, ids=IDS)
def test_ejemplo_se_ejecuta_sin_error(ejemplo):
    resultado = ejecutar_consulta(ejemplo["sql"])
    assert resultado.ok, f"{ejemplo['pregunta']} -> {resultado.error}"
