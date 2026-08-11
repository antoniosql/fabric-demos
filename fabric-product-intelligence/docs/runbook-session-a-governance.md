# Runbook Sesion A: Gobierno De Principio A Fin

## Preparacion

1. Validar prerequisitos y artefactos Fabric:

```powershell
python -m fabric_sessions validate-demo
```

2. Desplegar artefactos, subir datos y ejecutar notebooks en Fabric:

```powershell
python -m fabric_sessions deploy
python -m fabric_sessions upload-data
python -m fabric_sessions run-notebooks
```

3. Ejecutar consultas de `sql/003_demo_queries.sql`.

## Demo

- Mostrar Lakehouse con ficheros `Files/raw`, tablas `raw.*` y `curated_fact_transactions`.
- Abrir `curated_fact_transactions` y resaltar normalizacion de fechas, importes, IDs y flags.
- Abrir el notebook `02_quality_governance` y mostrar reglas fallidas ya ejecutadas como job Fabric.
- Abrir SQL database in Fabric y consultar reglas con `score < 95`.
- Abrir Fabric App en la ruta Gobierno:
  - Score global.
  - Quality cockpit.
  - Action board.
  - Linaje operativo.

## Mensaje Clave

El gobierno no termina en catalogar un activo. Termina cuando una persona responsable ve el problema, entiende el impacto, prioriza y actua.
