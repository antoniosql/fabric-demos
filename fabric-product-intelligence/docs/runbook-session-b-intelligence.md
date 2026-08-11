# Runbook Sesion B: IA, Ontologia Y Scoring

## Preparacion

1. Ejecutar la cadena Fabric de notebooks:

```powershell
python -m fabric_sessions run-notebooks
```

2. Revisar en Fabric:

- Tabla `customer_features`.
- Tabla `ml_customer_score_current`.
- Experimento `exp_retail_customer_scoring`.
- Modelo registrado `retail_customer_repurchase_model`.
- `agent/instructions.md`.
- `agent/questions.md`.
- `agent/ontology.yaml`.

## Demo

- Mostrar tabla de features por cliente.
- Explicar target de recompra y riesgo de leakage temporal.
- Abrir el experimento MLflow y revisar parametros, metricas y modelo registrado.
- Mostrar score actual con banda y recomendacion.
- Abrir Fabric App en la ruta Inteligencia:
  - Ranking de clientes.
  - Ficha conceptual de score.
  - Panel de agente.
  - Ontologia de pedidos.
- Ejecutar preguntas prevalidas del Data Agent en ingles.

## Mensaje Clave

La IA util no empieza en el prompt. Empieza con datos confiables, conceptos compartidos, features gobernadas y modelos versionados.
