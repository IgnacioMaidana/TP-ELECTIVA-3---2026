# Resultados de la evaluación del agente

- Fecha: 2026-10-12 20:23
- Modelo: gemini-3.5-flash-lite
- Preguntas por corrida: 2 · corridas: 3
- Umbral de latencia: 15 s (RNF-03)

## Resumen por tipo (todas las corridas)

| Tipo | Preguntas | Aprobadas | Ruta | Respuesta | Idioma | Seguro | Latencia media | Latencia neta | ≤ 15 s |
|---|---|---|---|---|---|---|---|---|---|
| rag | 6 | 5 (83 %) | 100 % | 83 % | 100 % | 100 % | 7.5 s | 2.4 s | 100 % |
| TOTAL | 6 | 5 (83 %) | 100 % | 83 % | 100 % | 100 % | 7.5 s | 2.4 s | 100 % |

La latencia total incluye las pausas que impone el nivel gratuito del LLM (LLM_PAUSA_SEGUNDOS entre llamadas). La latencia neta las descuenta.

## Generalización: preguntas parecidas a los ejemplos del prompt vs. independientes

| Conjunto | Preguntas | Aprobadas |
|---|---|---|
| independiente | 6 | 5 (83 %) |

## Variación entre corridas

| Corrida | Aprobadas | % |
|---|---|---|
| 1 | 2 de 2 | 100 % |
| 2 | 2 de 2 | 100 % |
| 3 | 1 de 2 | 50 % |

Preguntas con resultado distinto entre corridas: RAG-09.

## Detalle de la última corrida (n.º 3)

| ID | Ruta esperada → obtenida | Ruta | Resp. | Idioma | Seguro | Latencia | Intentos SQL |
|---|---|---|---|---|---|---|---|
| RAG-08 | rag → rag | ✔ | ✔ | ✔ | ✔ | 7.8 s | - |
| RAG-09 | rag → rag | ✔ | ✘ | ✔ | ✔ | 8.2 s | - |

## Fallos de la última corrida

- **RAG-09** — Which product category has the shortest warranty?
  - la respuesta no contiene ninguna de las expresiones esperadas
