# Fabric Retail Sessions

Repositorio para preparar dos sesiones sobre Microsoft Fabric usando el dataset retail omnicanal de FraSoHome:

- Gobierno end-to-end: calidad, linaje, SQL database in Fabric y Fabric App.
- IA aplicada: features, scoring de clientes, ontologia y Data Agent.



## Arranque Rapido

1. Crear entorno Python e instalar dependencias:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

2. Configurar variables:

```powershell
Copy-Item .env.example .env
notepad .env
```

3. Validar prerequisitos, dataset y estado de artefactos Fabric:

```powershell
pwsh ./scripts/00_check_prereqs.ps1
python -m fabric_sessions validate-demo
```

4. Desplegar en Fabric:

```powershell
az login
python -m fabric_sessions deploy
python -m fabric_sessions upload-data
python -m fabric_sessions run-notebooks
npm install
npm --prefix app install
npm run app:deploy
```

## Comandos Publicos

- `pwsh ./scripts/00_check_prereqs.ps1`: valida herramientas, Rayfin y contrato del dataset.
- `python -m fabric_sessions deploy`: crea workspace, Lakehouse, SQL database, Data Agent, carpeta de notebooks y notebooks Fabric.
- `python -m fabric_sessions upload-data`: sube los 11 CSV a OneLake y ejecuta `00_ingest_raw` para crear tablas Delta `raw.*`.
- `python -m fabric_sessions run-notebooks`: ejecuta en Fabric la cadena completa de notebooks, espera cada job y falla si un notebook falla.
- `python -m fabric_sessions validate-demo`: valida dataset, artefactos Fabric y estado de ejecuciones de notebooks. No ejecuta pipeline local.
- `npm run app:deploy`: despliega la Fabric App con Rayfin.

## Estructura

- `fabric_sessions/`: CLI, validacion del dataset y cliente Fabric/OneLake REST.
- `notebooks/fabric_workspace/`: notebooks `.ipynb` que se suben y ejecutan en Fabric.
- `sql/`: DDL operacional para `gov_*` y `ml_*`.
- `agent/`: instrucciones, ontologia y preguntas prevalidas del Data Agent.
- `semantic-model/`: contrato TMDL minimo.
- `app/`: Fabric App Rayfin/React con vistas de gobierno e inteligencia.
- `docs/`: runbooks, checklist, troubleshooting y decks de apoyo.

## Notas De Implementacion

El comando `deploy` usa Azure CLI para obtener token interactivo contra Fabric. Algunos tenants restringen creacion de items como semantic model mediante flujos especializados. En ese caso el repo deja contrato, nombres, definiciones y runbooks listos para crear el item manualmente.

La ejecucion de la demo ocurre en Fabric: los CSV se cargan en OneLake, `00_ingest_raw` crea tablas `raw.*`, los notebooks generan curated/calidad/features/scoring, `03_features_scoring` crea experimento y modelo con MLflow, y `04_app_seed_export` publica `Files/generated/app_seed.json`.
