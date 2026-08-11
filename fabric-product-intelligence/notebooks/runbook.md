# Fabric Notebook Runbook

Run the notebooks in this order in Fabric after `python -m fabric_sessions upload-data`.

For Fabric workspace upload, use the `.ipynb` bundle in `notebooks/fabric_workspace`:

1. `00_ingest_raw.ipynb`
2. `01_curated_transactions.ipynb`
3. `02_quality_governance.ipynb`
4. `03_features_scoring.ipynb`
5. `04_app_seed_export.ipynb`

`00_ingest_raw` materializes the CSV files as Delta tables in schema `raw`. `03_features_scoring` trains and logs the model with MLflow in Fabric, creating experiment `exp_retail_customer_scoring` and registered model `retail_customer_repurchase_model`.

The Python CLI command `python -m fabric_sessions run-notebooks` triggers these notebooks in Fabric and waits for each job to finish. There is no local notebook-equivalent pipeline in the demo path.
