# Checklist De Preparacion

## Comun

- [ ] `.env` contiene `FABRIC_TENANT_ID` y `FABRIC_CAPACITY_ID`.
- [ ] Usuario interactivo tiene permisos sobre la capacidad Fabric.
- [ ] Los 11 CSV existen en `SOURCE_DATA_PATH`.
- [ ] Workspace creado y asignado a la capacidad.
- [ ] `python -m fabric_sessions deploy` sube notebooks a la carpeta `Fabric Workspace Notebooks`.
- [ ] `python -m fabric_sessions upload-data` sube ficheros raw y ejecuta `00_ingest_raw`.
- [ ] `python -m fabric_sessions run-notebooks` termina sin jobs fallidos.
- [ ] `python -m fabric_sessions validate-demo` pasa contra artefactos Fabric.
- [ ] Capturas preparadas por si falla conectividad.

## Gobierno

- [ ] Lakehouse contiene tablas `raw.*`, `curated_fact_transactions` y `gov_*`.
- [ ] SQL database in Fabric esta creado para la parte operacional/app.
- [ ] Hay reglas fallidas controladas.
- [ ] Hay acciones abiertas.
- [ ] Consulta de calidad de `sql/003_demo_queries.sql` devuelve resultados.
- [ ] Fabric App muestra ruta Gobierno.

## IA Y Scoring

- [ ] `customer_features` existe.
- [ ] `ml_customer_score_current` contiene clientes ordenables por score.
- [ ] Experimento `exp_retail_customer_scoring` existe.
- [ ] Modelo `retail_customer_repurchase_model` esta registrado.
- [ ] Data Agent tiene instrucciones y preguntas cargadas.
- [ ] Las preguntas prevalidas responden sin exponer PII.
- [ ] Fabric App muestra ruta Inteligencia.
