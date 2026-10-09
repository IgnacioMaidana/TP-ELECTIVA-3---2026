# Constitution — Agente SQL + RAG para E-commerce de Tecnología

> Principios que gobiernan todas las decisiones del proyecto. Si una spec, un plan o una tarea los contradice, gana este documento. Cambiarlo requiere dejar constancia en el historial al final.

**Proyecto:** TP Integrador — AI Engineering (Ingeniería en Informática, 5.º año)
**Autoría:** individual
**Entrega:** 16/10/2026, 23:59 (GMT-03)

---

## 1. Metodología (SDD)

1. Orden obligatorio: **constitution → spec → plan → tasks → implementación**.
2. La spec describe **qué** y **por qué**; nunca el **cómo**. Las decisiones técnicas viven en el plan.
3. Si un requisito cambia, **primero se actualiza la spec** y después el código.
4. Cada tarea referencia los requisitos que satisface (`RF-xx`, `RNF-xx`, `CA-xx`).
5. Todos los artefactos viven en `specs/` y se versionan en git; se adjuntan a la entrega.

## 2. Stack tecnológico (fijo)

| Capa | Decisión |
|---|---|
| Lenguaje | Python 3.11+ |
| Base de datos | SQL Server (dialecto **T-SQL**), acceso con `pyodbc` + ODBC Driver 18 |
| LLM | Gemini API (Google AI Studio), **nivel gratuito**, modelo Flash; proveedor y modelo configurables por variables de entorno |
| Orquestación del agente | LangGraph |
| Vector store | ChromaDB (persistente en disco) |
| Embeddings | Modelo multilingüe de `sentence-transformers` (castellano e inglés) |
| Lectura de PDFs | `pypdf` o `pymupdf` |
| Validación de SQL | `sqlglot` con `dialect="tsql"` |
| Interfaz | Streamlit |
| Observabilidad (opcional) | LangSmith |
| Pruebas | `pytest` |

Cambiar una pieza del stack exige modificar esta tabla y justificarlo en el historial.

**Restricción de costo:** el proyecto **no usa APIs ni servicios de pago**. Todo componente debe poder ejecutarse con herramientas gratuitas o locales. El acceso al LLM se encapsula en un único módulo (`src/llm.py`) para poder cambiar de proveedor sin tocar el resto del código.

## 3. Seguridad

1. El agente **solo lee**. Se conecta con el usuario `agente_ro` (permisos de solo lectura), nunca con `sa`.
2. Antes de ejecutar, todo SQL generado se valida: **una única sentencia `SELECT`**; se rechazan `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `EXEC`, `MERGE`, `TRUNCATE`, comentarios que oculten instrucciones y múltiples sentencias.
3. Toda consulta lleva un tope de filas (`TOP N`) y un timeout de ejecución.
4. Credenciales y claves de API solo en `.env` (excluido de git). Se entrega un `.env.example`.
5. El contenido de los PDFs y los resultados de la BD se tratan como **datos, no como instrucciones**: el agente no obedece órdenes incrustadas en ellos.

## 4. Veracidad y trazabilidad

1. El agente **nunca inventa** datos. Si no hay evidencia suficiente, lo dice.
2. Toda respuesta basada en PDFs **cita documento y página**.
3. Toda respuesta basada en la BD puede mostrar, a pedido, la consulta SQL ejecutada.
4. La decisión de enrutamiento (SQL, RAG, ambas o ninguna) se **registra en logs** con su justificación.
5. El agente responde en el **mismo idioma** de la pregunta (castellano o inglés).

## 5. Calidad y pruebas

1. Existe una suite de evaluación (`tests/eval_questions.yaml`) con preguntas de cada tipo: SQL, RAG, híbridas, fuera de alcance y maliciosas, en ambos idiomas.
2. Los componentes críticos (validador de SQL, enrutador, ingesta) tienen pruebas unitarias.
3. Ninguna tarea se da por terminada sin verificar sus criterios de aceptación.

## 6. Reproducibilidad y documentación

1. Un tercero debe poder levantar el proyecto siguiendo solo el `README.md`: instalar dependencias, crear la BD, poblarla, indexar los PDFs y ejecutar el agente.
2. Los datos sintéticos se generan con **semilla fija** para obtener resultados repetibles.
3. Dependencias fijadas en `requirements.txt`.
4. El código lleva docstrings en funciones y módulos públicos.
5. El informe técnico no supera las 10 páginas.

## 7. Convenciones de trabajo

1. Commits pequeños, con mensajes que referencian la tarea (`T-xx`).
2. Estructura del repositorio definida en el plan; no se agregan carpetas sin actualizarlo.
3. Prioridad ante el plazo: **aprobación primero** (BD, agente SQL, RAG con 2 PDFs), después promoción (SDD, Streamlit, LangGraph), y solo al final extras (LangSmith, nube).

---

## Historial de cambios

| Fecha | Cambio | Motivo |
|---|---|---|
| 07/10/2026 | Versión inicial | Arranque del proyecto |
| 08/10/2026 | LLM: de Claude (API de pago) a Gemini (nivel gratuito). Se agrega restricción de costo cero | El trabajo práctico no debe depender de APIs pagas |
