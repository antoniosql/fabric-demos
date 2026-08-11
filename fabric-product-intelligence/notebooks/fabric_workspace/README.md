# Fabric Workspace Notebooks

Sube estos notebooks al workspace de Fabric y adjuntalos al Lakehouse `lh_retail_omnicanal`.

Ejecutalos en este orden despues de `python -m fabric_sessions upload-data`:

1. `00_ingest_raw.ipynb`
2. `01_curated_transactions.ipynb`
3. `02_quality_governance.ipynb`
4. `03_features_scoring.ipynb`
5. `04_app_seed_export.ipynb`

Los notebooks leen los CSV en `Files/raw`, crean tablas Delta en el esquema `raw`, entrenan el scoring con MLflow en Fabric, registran el modelo y exportan resumenes demo en `Files/generated`.

Salidas principales:

- Tablas raw: `raw.*`
- Vistas compatibilidad: `bronze_*`
- Tabla curated: `curated_fact_transactions`
- Gobierno: `gov_quality_rule`, `gov_quality_run`, `gov_quality_result`, `gov_action`
- Scoring: `customer_features`, `ml_customer_score_current`, `ml_customer_score_history`
- MLflow: experimento `exp_retail_customer_scoring`, modelo `retail_customer_repurchase_model`
- Export demo: `Files/generated/quality_summary.json`, `Files/generated/app_seed.json`
