# Fabric notebook — NB_Load_Bronze_Retail
# Capa: BRONZE. Workspace: WS_Retail_Bronze. Lakehouses: LH_Landing (fuente) + LH_Bronze (destino).
#
# Ingesta FIEL al origen (todo string) de las fuentes retail de FraSoHome que aterrizan en
# LH_Landing/Files/landing/retail/<tabla>/, añadiendo las columnas de trazabilidad obligatorias.
# Dirigido por metadatos: config/ingestion/*.json (subidos a LH_Bronze/Files/config/).
#
# Idempotente: escribe cada tabla Delta en modo overwrite.

import json
import uuid
from datetime import datetime, timezone

from pyspark.sql import functions as F

BATCH_ID = f"fabric-{uuid.uuid4().hex[:8]}"
INGEST_TS = datetime.now(timezone.utc)

# Rutas dentro del lakehouse (ajusta si usas el diseño "collapsed" de config/workspaces.json)
CONFIG_GLOB = "Files/config/ingestion/*.json"
LANDING_ROOT = "Files/landing"

config_paths = [r.path for r in mssparkutils.fs.ls(CONFIG_GLOB.rsplit("/", 1)[0])
                if r.path.endswith(".json")]

for cfg_path in config_paths:
    cfg = json.loads("".join(mssparkutils.fs.head(cfg_path, 1024 * 1024)))
    schema, table = cfg["target_schema"], cfg["target_table"]
    src = f"{LANDING_ROOT}/{cfg['source_system']}/{table}" if False else cfg["landing_path"]

    df = (spark.read
          .option("header", cfg["csv_options"].get("header", True))
          .option("sep", cfg["csv_options"].get("delimiter", ","))
          .option("encoding", cfg["csv_options"].get("encoding", "utf-8"))
          # Bronze fiel: todo como string, sin inferencia de tipos
          .option("inferSchema", "false")
          .csv(cfg["landing_path"]))

    df = (df
          .withColumn("_input_file_name", F.input_file_name())
          .withColumn("_ingestion_timestamp", F.lit(INGEST_TS).cast("timestamp"))
          .withColumn("_batch_id", F.lit(BATCH_ID)))

    target = f"LH_Bronze.{schema}.{table}"
    (df.write.mode("overwrite").format("delta")
        .option("overwriteSchema", "true")
        .saveAsTable(target))
    print(f"[BRONZE] {target}: {df.count()} filas · batch={BATCH_ID}")

print("Bronze completado.")
