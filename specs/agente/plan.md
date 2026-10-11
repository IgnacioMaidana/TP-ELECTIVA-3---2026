# Plan 001 — Arquitectura y diseño técnico del agente SQL + RAG

**Estado:** v0.1
**Fecha:** 07/10/2026
**Deriva de:** `spec.md` · **Sujeto a:** `../constitution.md`

> Aquí se define el **cómo**. Cada decisión indica qué requisito de la spec satisface.

---

## 1. Visión general

```
Usuario ──► Streamlit (chat) ──► Agente (LangGraph)
                                    │
                         ┌──────────┴───────────┐
                         ▼                      ▼
                   Router (LLM)        Guardrails de entrada
                         │
      ┌────────┬─────────┼──────────┬────────────┐
      ▼        ▼         ▼          ▼            ▼
     sql      rag     híbrida     ninguna      rechazar
      │        │      (rag→sql)  (fuera de     (modificación,
      │        │         │         alcance /    inyección)
      │        │         │         aclarar)
      ▼        ▼         ▼
  SQL Tool  RAG Tool  ambas
      │        │         │
      └────────┴────┬────┘
                    ▼
            Sintetizador (LLM)
        respuesta + fuentes + SQL usado
                    │
                    ▼
                Usuario
```

El agente es un **grafo de estados en LangGraph**: un nodo router decide la ruta, nodos de herramientas obtienen el contexto y un nodo sintetizador redacta la respuesta final en el idioma del usuario. Esto hace explícita y trazable la decisión de "cuándo obtener contexto de cada fuente" (RF-05, RF-16, CA-10).

## 2. Decisiones técnicas

| # | Decisión | Alternativa descartada | Motivo | Cubre |
|---|---|---|---|---|
| D-01 | Grafo explícito con router (LangGraph) | Agente ReAct libre con 2 herramientas | La ruta queda visible, testeable y registrable; el modelo no puede "olvidarse" de citar fuentes | RF-05, RF-16 |
| D-02 | Router con salida estructurada (JSON): `ruta`, `idioma`, `justificacion` | Reglas por palabras clave | Entiende ambigüedad y dos idiomas | RF-01, RF-02, RF-05 |
| D-03 | Ruta híbrida **secuencial: RAG primero, SQL después** | Paralelo | La regla documental (ej. 30 días) condiciona la consulta SQL | RF-06, RF-17, CA-08 |
| D-04 | Esquema al LLM en texto compacto (tablas, columnas, claves, descripciones, valores válidos de estados) + 5-8 ejemplos pregunta→SQL | Volcar DDL completo | Menos tokens, mayor precisión | RF-03 |
| D-05 | SQL en **T-SQL**: `TOP N`, `GETDATE()`, `DATEADD`, `DATEDIFF` | SQL genérico | El motor es SQL Server | RF-03 |
| D-06 | Validación con `sqlglot` (dialecto `tsql`) + lista de bloqueo + usuario `agente_ro` | Solo confiar en el prompt | Defensa en profundidad | RF-13, RNF-01 |
| D-07 | Auto-corrección: hasta **2 reintentos** pasando el error de SQL Server al LLM | Sin reintentos | Mejora robustez sin bucles infinitos | RF-09 |
| D-08 | Embeddings multilingües `paraphrase-multilingual-MiniLM-L12-v2` (o `multilingual-e5-small`) | Embeddings de API | Gratis, locales, ES/EN, reproducible | RF-01, RF-04 |
| D-09 | ChromaDB persistente en `data/vectorstore/` | FAISS | Guarda metadatos (documento, página) directamente | RF-07 |
| D-10 | Chunking: ~450 caracteres (≈110 tokens, porque el modelo de embeddings admite 128), solape 80 caracteres, cortes en límite de oración sin cruzar páginas; metadatos `documento`, `pagina` | Chunks por caracteres fijos | Citas exactas | RF-07 |
| D-11 | Recuperación top-k = 5, con umbral mínimo de similitud (provisorio 0.30, calibrado con `scripts/calibrar_rag.py`); si nada supera el umbral → "no encontré en los documentos" | Siempre responder con lo recuperado | Evita inventar | RF-11, RNF-02 |
| D-12 | Fecha actual inyectada al prompt (`SYSDATE` del servidor) | Que el LLM la suponga | Cálculos de plazo y "mes anterior" correctos | RF-17, CA-16 |
| D-13 | Memoria de sesión: últimos N mensajes en el estado del grafo | Sin memoria | Preguntas de seguimiento | RF-15 |
| D-14 | Contenido de PDF y filas de BD se pasan al LLM dentro de delimitadores marcados como **datos no confiables** | Mezclar con instrucciones | Mitiga inyección indirecta | CA-13 |
| D-15 | Logging estructurado JSON por pregunta: ruta, justificación, SQL, intentos, chunks (doc/página), latencia | `print` | Evidencia para el informe | RF-16, RNF-05 |
| D-16 | PDFs sintéticos generados con script (`fpdf2` o `reportlab`) a partir de las categorías y productos reales de la BD | PDFs escritos a mano | Coherencia BD–PDF y reproducibilidad | §3.2 spec |
| D-20 | Cada fragmento lleva como prefijo el título de su sección; el router reescribe la pregunta en castellano (`consulta_documentos`) antes de buscar | Buscar con la pregunta tal cual | Prueba real: una pregunta en inglés recuperaba fragmentos poco relevantes porque los PDFs están en castellano y el modelo multilingüe pierde precisión entre idiomas | RF-01, RF-04 |
| D-18 | LLM accedido solo desde `src/llm.py` (fábrica de modelo de chat de LangChain) con proveedor por variable de entorno; **Gemini gratuito** por defecto | Llamar al SDK de un proveedor en cada módulo | Costo cero y cambio de proveedor sin tocar el grafo | constitution §2 |
| D-19 | Control de límites del nivel gratuito: reintentos con espera creciente ante error 429 y pausa entre preguntas en la suite de evaluación | Ignorar los límites | El nivel gratuito limita solicitudes por minuto y por día | RNF-03 |
| D-17 | Datos sintéticos con `Faker (es_AR)` y semilla fija; consistencia forzada entre tablas | Datos aleatorios sueltos | Consultas con sentido | RNF-04, CA-17 |

## 3. Flujo del agente (nodos LangGraph)

**Estado compartido:** `pregunta`, `historial`, `idioma`, `ruta`, `justificacion`, `contexto_rag`, `sql`, `filas`, `error_sql`, `intentos`, `respuesta`, `fuentes`.

| Nodo | Responsabilidad |
|---|---|
| `router` | Clasifica en: `sql`, `rag`, `hibrida`, `aclarar`, `fuera_de_alcance`, `rechazar`. Detecta idioma. Considera el historial |
| `rechazar` / `fuera_de_alcance` / `aclarar` | Respuesta directa sin consultar fuentes (RF-11, RF-12, RF-13) |
| `rag_node` | Embebe la pregunta, recupera top-k, aplica umbral, guarda chunks con metadatos |
| `sql_gen` | Genera T-SQL usando esquema + ejemplos + (si es híbrida) el contexto RAG |
| `sql_validate` | `sqlglot` + reglas; si falla, vuelve a `sql_gen` con el motivo |
| `sql_exec` | Ejecuta con `agente_ro`, timeout y tope de filas; si hay error, vuelve a `sql_gen` (máx. 2 veces) |
| `synthesize` | Redacta en el idioma del usuario, cita documento/página, declara cero filas o truncado (RF-07, RF-10, RF-14) |

**Aristas:** `router → {rag_node | sql_gen | rag_node→sql_gen | rechazar | ...}` · `sql_gen → sql_validate → sql_exec → synthesize` · `rag_node → synthesize` (si solo RAG).

## 4. Seguridad del SQL (detalle)

Reglas de `sql_validate`, aplicadas en orden:

1. Parsear con `sqlglot.parse(sql, dialect="tsql")`; debe resultar **exactamente 1 sentencia** de tipo `SELECT` (se admiten CTE con `WITH`).
2. Rechazar si contiene nodos: `Insert`, `Update`, `Delete`, `Drop`, `Alter`, `Create`, `Merge`, `Command` (`EXEC`), `TRUNCATE`, `INTO` (SELECT INTO).
3. Rechazar referencias a objetos fuera de las 7 tablas permitidas (incluye `sys.*`, `INFORMATION_SCHEMA`, `master`).
4. Si no hay `TOP`, **inyectar** `TOP 100` (o envolver en subconsulta).
5. Ejecutar con timeout (ej. 15 s) y usuario `agente_ro` sin permisos de escritura.

## 5. Pipeline RAG

**Ingesta (offline, `python -m src.rag.ingest`)**
1. Leer cada PDF de `data/pdfs/` página por página.
2. Dividir en chunks de ~600 tokens con solape ~100, sin cruzar páginas.
3. Generar embeddings y guardar en ChromaDB con metadatos `{documento, pagina, chunk_id}`.
4. Operación idempotente: reindexar borra y recrea la colección.

**Consulta (online)**
1. Embeber la pregunta (funciona en ES y EN gracias al modelo multilingüe).
2. Recuperar top-4; descartar bajo el umbral.
3. Pasar chunks al sintetizador con su `documento` y `pagina`; el sintetizador debe citar `[Documento, p. N]`.

**Contenido de los PDFs**

| PDF | Secciones |
|---|---|
| `politica_devoluciones_garantias.pdf` | Plazo (**30 días corridos desde la entrega real**), condiciones, excepciones, proceso de reclamo, reembolsos, garantía por categoría (coherente con `productos.garantia_meses`) |
| `catalogo_especificaciones.pdf` | Una ficha por categoría y por producto destacado: especificaciones técnicas, compatibilidad, contenido de la caja |

(Se puede sumar un tercero —envíos y plazos de entrega— si sobra tiempo.)

## 6. Datos sintéticos

| Tabla | Cantidad objetivo | Reglas de consistencia |
|---|---|---|
| `categorias` | 16 | Nombres fijos (Notebooks, Smartphones, Tablets, Monitores, Teclados, Mouses, Auriculares, Parlantes, Almacenamiento, Routers y redes, Impresoras, Cámaras web, Consolas, Micrófonos, Smartwatches, Cables y accesorios). Son 16 porque el enunciado exige más de 15 registros por tabla |
| `productos` | 48 (3 por categoría) | Marcas ficticias; precio en USD; garantía fija por categoría (6, 12, 24 o 36 meses), igual a la que dirá el PDF; 3 agotados y 2 discontinuados |
| `clientes` | 60 | Países mayormente AR, con algunos de otros países |
| `pedidos` | 250 | Fechas en los últimos 12 meses; estados en proporción realista |
| `detalle_pedidos` | ~520 | 1 a 4 líneas por pedido; `precio_unitario` = precio vigente del producto |
| `envios` | ~210 (uno por cada pedido enviado, entregado o devuelto) | Estado de envío coherente con el del pedido; `fecha_entrega_real` solo si entregado |
| `resenas` | ~120 | Solo de clientes que compraron ese producto; una por cliente y producto |

Reglas globales: `pedidos.total` = suma de `detalle_pedidos.subtotal`; pedidos `cancelado` y `pendiente` sin envío; el **cliente 12** concentra los **casos límite** de la regla de 30 días (entregas hace 5, 29, 30, 31 y 60 días, más un pedido devuelto, uno en tránsito y uno cancelado). Moneda: USD. Semilla fija (42); las fechas son relativas a la fecha de generación.

## 7. Estructura del repositorio

```
proyecto/
├── specs/
│   ├── constitution.md
│   └── agente/        spec.md · plan.md · tasks.md
├── db/
│   ├── 01_crear_esquema_ecommerce.sql
│   └── 02_usuario_solo_lectura.sql   (opcional, extraído del anterior)
├── data/
│   ├── pdfs/                  (los 2+ PDFs generados)
│   └── vectorstore/           (ChromaDB, ignorado en git)
├── scripts/
│   ├── generar_datos.py       (puebla la BD)
│   └── generar_pdfs.py
├── src/
│   ├── config.py              (carga .env)
│   ├── db.py                  (conexión pyodbc)
│   ├── sql_tool/  schema_prompt.py · validator.py · executor.py
│   ├── rag/       ingest.py · retriever.py
│   ├── agent/     state.py · router.py · nodes.py · graph.py · prompts.py
│   ├── logging_utils.py
│   └── app.py                 (Streamlit)
├── tests/
│   ├── test_validator.py
│   ├── test_router.py
│   ├── test_ingest.py
│   ├── eval_questions.yaml
│   └── run_eval.py
├── docs/                      (informe, capturas, logs)
├── .env.example
├── requirements.txt
└── README.md
```

## 8. Configuración (`.env.example`)

```
LLM_PROVIDER=gemini
GOOGLE_API_KEY=
LLM_MODEL=
LLM_PAUSA_SEGUNDOS=4
DB_SERVER=localhost
DB_NAME=EcommerceTech
DB_USER=agente_ro
DB_PASSWORD=
DB_DRIVER=ODBC Driver 18 for SQL Server
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
RAG_TOP_K=4
SQL_MAX_ROWS=100
SQL_RETRIES=2
LANGSMITH_TRACING=false
```

El valor de `LLM_MODEL` (un modelo Flash) debe consultarse en Google AI Studio al momento de implementar, porque los modelos con nivel gratuito cambian con el tiempo.

## 9. Estrategia de pruebas

| Nivel | Qué | Herramienta |
|---|---|---|
| Unitarias | Validador SQL (casos permitidos y maliciosos), chunking, umbral RAG | `pytest` |
| Router | Clasificación de las preguntas de la suite | `pytest` (llama al LLM) |
| Evaluación | `run_eval.py` recorre `eval_questions.yaml`, compara ruta esperada y criterio de respuesta, genera tabla de resultados para el informe | script propio |
| Manual | Capturas de la interfaz con ejemplos de cada tipo | Streamlit |

Métricas a reportar: % de rutas correctas, % de respuestas correctas por tipo, % de rechazos correctos en preguntas maliciosas, latencia media.

## 10. Riesgos

| Riesgo | Mitigación |
|---|---|
| SQL generado incorrecto en uniones complejas | Ejemplos few-shot, reintentos con el error, consultas de referencia en la suite |
| Límites del nivel gratuito (solicitudes por minuto y por día) | Reintentos con espera, pausa en la evaluación, esquema compacto; plan B: modelo local con Ollama |
| Latencia alta (router + SQL + síntesis = 3 llamadas) | Esquema compacto, modelo rápido para el router si hace falta |
| Descargar el modelo de embeddings en una máquina limpia | Documentarlo en el README (primera ejecución con internet) |
| Driver ODBC distinto entre equipos | Documentar versión y probar la cadena de conexión primero |
| Plazo de 9 días | Priorizar camino de aprobación; LangSmith y nube solo si sobra tiempo |

## 11. Fuera de este plan

Despliegue en la nube y LangSmith: decisiones pendientes (ver spec §10). El diseño es compatible: LangSmith se activa con variables de entorno al usar LangGraph.
