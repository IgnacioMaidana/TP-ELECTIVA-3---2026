# Tasks 001 — Agente SQL + RAG para e-commerce

**Deriva de:** `plan.md` · **Entrega:** 16/10/2026, 23:59

Cada tarea es pequeña, verificable y referencia los requisitos que cubre. Marcar `[x]` al terminar y commitear con el ID (`T-xx`).

**Estado (v0.2):** Fases 0, 1 y 2 completas; Fase 3 en curso (PDFs generados, falta el RAG).
**Cambios respecto de la versión inicial:** el LLM pasó de Claude a Gemini en nivel gratuito (constitution, 08/10); el esquema tiene 16 categorías y 48 productos para cumplir "más de 15 registros por tabla"; se agregaron las tareas T-41 a T-43.

---

## Fase 0 — Base del proyecto (hoy, 07/10)

- [x] **T-01** Crear repositorio, `.gitignore`, `.env.example`, entorno virtual. *(RNF-04)*
- [x] **T-02** Escribir constitution, spec, plan y tasks en `specs/`. *(SDD)*
- [x] **T-03** Ejecutar `01_crear_esquema_ecommerce.sql` en SSMS y verificar las 7 tablas. *(CA-17)*

## Fase 1 — Datos (08/10)

- [x] **T-04** Crear `requirements.txt` con dependencias fijadas e instalar. *(RNF-04)*
- [x] **T-05** `src/config.py` y `src/db.py`: cargar `.env` y conectar con `pyodbc`. **Verificar:** una consulta `SELECT 1` responde. *(RNF-04)*
- [x] **T-06** `scripts/generar_datos.py` con Faker y semilla fija: puebla las 7 tablas con las cantidades y reglas del plan §6. *(CA-17, RNF-07)*
- [x] **T-07** Incluir los casos límite de entrega (5, 29, 30, 31 y 60 días atrás) y pedidos sin entrega. *(RF-17, CA-08, CA-20)*
- [x] **T-08** Script de comprobación: más de 15 filas por tabla, `pedidos.total` igual a la suma de subtotales, sin huérfanos. **Verificar** que pasa. *(CA-17)*
- [x] **T-09** Crear usuario `agente_ro` (descomentar sección del script SQL) y probar que `INSERT` y `DELETE` fallan con él. *(RNF-01, RF-13)*

## Fase 2 — Herramienta SQL (09/10)

- [x] **T-10** `schema_prompt.py`: generar el texto compacto del esquema (tablas, columnas, claves, descripciones, valores válidos). *(RF-03)*
- [x] **T-11** Redactar 6-8 ejemplos pregunta→T-SQL (ES y EN), incluyendo joins y regla de 30 días. *(RF-03, RF-17)*
- [x] **T-12** `validator.py` con `sqlglot` (dialecto `tsql`) según plan §4. *(RF-13, RNF-01)*
- [x] **T-13** `tests/test_validator.py`: casos válidos y maliciosos (`DROP`, `;` múltiple, `EXEC`, `SELECT INTO`, tablas `sys.*`, comentarios ocultos, `UPDATE`). **Verificar** que todos pasan. *(CA-11)*
- [x] **T-14** `executor.py`: ejecución con timeout, tope de filas e inyección de `TOP`. *(RF-14, RNF-01)*
- [x] **T-15** Función `pregunta → SQL → filas` con auto-corrección (2 reintentos). **Verificar** con 5 preguntas reales. *(RF-03, RF-09, CA-01 a CA-04)*

- [ ] **T-41** Evidencia de seguridad para el informe: ejecutar `ejecutar_consulta("DELETE FROM clientes")` (debe fallar en la etapa `validacion`) y probar una inyección contra el LLM; guardar capturas. *(RF-13, CA-11, CA-12)*

## Fase 3 — PDFs y RAG (10/10)

- [x] **T-16** `scripts/generar_pdfs.py`: crea `politica_devoluciones_garantias.pdf` (con la regla de 30 días desde la entrega, garantías por categoría coherentes con la BD) y `catalogo_especificaciones.pdf` (productos reales de la BD). *(§3.2, RF-17, CA-18)*
- [ ] **T-17** `rag/ingest.py`: lectura por página, chunking, embeddings, ChromaDB con metadatos. Idempotente. *(RF-04, RF-07)*
- [ ] **T-18** `tests/test_ingest.py`: cada chunk tiene `documento` y `pagina`; los 2 PDFs están indexados. *(CA-18)*
- [ ] **T-19** `rag/retriever.py`: top-k con umbral y mensaje de "sin resultados". **Verificar** con 3 preguntas en ES y 3 en EN. *(RF-04, RF-11, CA-05 a CA-07)*

## Fase 4 — Agente con LangGraph (11-12/10)

- [ ] **T-20** `agent/state.py` y `agent/prompts.py`: estado, prompts del router, SQL y síntesis (con delimitadores de datos no confiables). *(D-14, CA-13)*
- [ ] **T-21** `agent/router.py`: salida estructurada `ruta`, `idioma`, `justificacion`. *(RF-02, RF-05)*
- [ ] **T-22** Nodos `rag_node`, `sql_gen`, `sql_validate`, `sql_exec`. *(RF-03, RF-04, RF-09)*
- [ ] **T-23** Nodo `synthesize`: idioma correcto, citas `[Documento, p. N]`, cero filas, truncado. *(RF-02, RF-07, RF-10, RF-14)*
- [ ] **T-24** Nodos `rechazar`, `fuera_de_alcance`, `aclarar`. *(RF-11, RF-12, RF-13, CA-11, CA-14, CA-15)*
- [ ] **T-25** `graph.py`: armar el grafo con la ruta híbrida RAG→SQL. **Verificar** CA-08 y CA-20, y la pregunta híbrida del reintegro de envío (regla del PDF §6: más de 2 días de demora + SQL). *(RF-06, RF-17)*
- [ ] **T-26** Inyectar fecha actual y memoria de sesión. **Verificar** CA-16. *(RF-15, D-12)*
- [ ] **T-27** `logging_utils.py`: log JSON por pregunta (ruta, justificación, SQL, chunks, latencia). *(RF-16, RNF-05, CA-10)*

## Fase 5 — Interfaz y evaluación (13/10)

- [ ] **T-28** `app.py` en Streamlit: chat, historial, desplegable "Ver SQL" y "Ver fuentes", indicador de ruta usada. *(RF-08, RF-15)*
- [ ] **T-29** `tests/eval_questions.yaml` con al menos 20 preguntas según spec §8. *(spec §8)*
- [ ] **T-30** `tests/run_eval.py`: ejecuta la suite y genera tabla de resultados (ruta correcta, respuesta correcta, latencia). *(RNF-03)*
- [ ] **T-43** Ejecutar la suite de evaluación al menos 2 veces y reportar la variación entre corridas (el modelo no permite fijar la temperatura). *(RNF-02)*
- [ ] **T-31** Ejecutar la suite, analizar fallos y ajustar prompts o ejemplos. Repetir hasta un resultado aceptable. *(CA-01 a CA-16)*

## Fase 6 — Documentación y entrega (14-15/10)

- [ ] **T-32** README: requisitos, instalación, creación y carga de BD, indexado de PDFs, ejecución, ejecución de tests. **Verificar** siguiéndolo en una carpeta limpia. *(RNF-04, CA-19)*
- [ ] **T-33** Capturas y logs de al menos un ejemplo de cada ruta (SQL, RAG, híbrida, rechazo). *(entregable)*
- [ ] **T-34** Informe técnico (máx. 10 páginas): modelo de datos, arquitectura, decisiones, ejemplos, evidencias, resultados de la suite. *(entregable)*
- [ ] **T-35** Verificar que `specs/` contiene todos los artefactos y que `spec.md` refleja los cambios hechos durante la implementación. *(SDD)*
- [ ] **T-42** Fijar las versiones de las dependencias con `pip freeze > requirements.txt` y verificar que el entorno se recrea. *(RNF-04, constitution §6)*
- [ ] **T-36** Exportar o respaldar la base (script de esquema + script/datos generados) y confirmar que los PDFs están en el repo. *(entregable)*

## Fase 7 — Margen y extras (15-16/10)

- [ ] **T-37** Revisión final del repositorio y entrega **antes de las 23:59 del 16/10**.
- [ ] **T-38** *(opcional)* LangSmith: activar variables de entorno y capturar trazas. *(promoción adicional)*
- [ ] **T-39** *(opcional)* Despliegue en la nube. Solo si todo lo anterior está cerrado.
- [ ] **T-40** Preparar demo y respuestas para el coloquio (23 o 30/10): por qué grafo explícito, cómo se evita el SQL peligroso, límites conocidos.

---

## Cronograma

| Fecha | Fase | Meta del día | Estado |
|---|---|---|---|
| Mié 07/10 | 0 | Spec, plan y tasks listos; esquema creado | Hecho |
| Jue 08/10 | 1 | BD poblada y verificada | Hecho |
| Vie 09/10 | 2 | Pregunta → SQL → respuesta funcionando | Hecho |
| Sáb 10/10 | 3 | 2 PDFs indexados y RAG con citas | En curso (PDFs listos) |
| Dom 11/10 | 4 | Router y grafo (parte 1) | Pendiente |
| Lun 12/10 | 4 | Grafo completo con ruta híbrida y logs | Pendiente |
| Mar 13/10 | 5 | Streamlit y suite de evaluación | Pendiente |
| Mié 14/10 | 6 | README, capturas, ajustes | Pendiente |
| Jue 15/10 | 6 | Informe y revisión | Pendiente |
| **Vie 16/10** | 7 | **Entrega antes de las 23:59** | Pendiente |

## Definición de terminado (por tarea)

1. Cumple lo descrito y su criterio de verificación.
2. Tiene pruebas, o evidencia, cuando corresponde.
3. Está documentada (docstrings) y commiteada con su ID.
4. Si cambió un requisito, la spec se actualizó **antes**.
