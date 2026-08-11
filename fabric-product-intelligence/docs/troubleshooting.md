# Troubleshooting

## Azure CLI No Devuelve Token Fabric

Ejecuta:

```powershell
az login
az account get-access-token --resource https://api.fabric.microsoft.com
```

Si falla, confirma tenant activo y permisos.

## Creacion De Items Fabric Restringida

Algunos tenants requieren crear Semantic Model desde la interfaz de Fabric porque no aceptan creacion vacia por REST. Mantener el nombre de `.env`, importar `semantic-model/model.tmdl` manualmente y continuar con `run-notebooks`.

## CapacityNotActive

Si `deploy`, `upload-data` o `run-notebooks` devuelven `CapacityNotActive`, activa o reanuda la capacidad Fabric asociada a `FABRIC_CAPACITY_ID` y relanza el comando. Los notebooks y jobs dependen de una capacidad activa.

## Notebooks No Se Ejecutan En Orden

Usa siempre:

```powershell
python -m fabric_sessions run-notebooks
```

El comando lanza `00_ingest_raw`, `01_curated_transactions`, `02_quality_governance`, `03_features_scoring` y `04_app_seed_export` en Fabric, esperando a que cada job termine antes del siguiente.

## Rayfin No Despliega

Validar:

```powershell
npm view @microsoft/rayfin-cli version
npm --prefix app install
npm run app:build
npm run app:deploy
```

Tambien confirma que Fabric Apps esta habilitado para el tenant y region.

## Las Reglas No Fallan

El dataset original incluye fallos controlados: clientes fuera de CRM, productos fuera de maestro, fechas no parseadas e importes con formatos mixtos. Si el dataset cambia, revisa `fabric_sessions/dataset.py` y el notebook `02_quality_governance`.

## El Agente Responde Con Demasiada Libertad

Reducir fuentes, mantener preguntas prevalidas de `agent/questions.md` y reforzar `agent/instructions.md` con limites de solo lectura y no PII.
