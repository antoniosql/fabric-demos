# Fabric notebook — NB_Load_Bronze_Retail
# Capa: BRONZE. Workspace: WS_Retail_Bronze. Lakehouses: LH_Landing (fuente) + LH_Bronze (destino).
#
# Ingesta FIEL al origen (todo string) de las fuentes retail de FraSoHome que aterrizan en
# LH_Landing/Files/landing/retail/<tabla>/, añadiendo las columnas de trazabilidad obligatorias.
# Dirigido por metadatos: config/ingestion/*.json (subidos a LH_Landing/Files/config/ingestion/).
#
# Idempotente: escribe cada tabla Delta en modo overwrite.
#
# RUTAS ONELAKE EXPLICITAS: el notebook se publica sin lakehouse por defecto adjunto (no lo
# configura infra/publish_notebooks.py), y LH_Bronze no es el mismo lakehouse que LH_Landing.
# Por eso leemos y escribimos siempre con la ruta OneLake completa (abfss://...) en vez de rutas
# relativas "Files/..." o `saveAsTable` sin cualificar — evita depender de un adjunto implícito
# y funciona igual crea el notebook el lakehouse que crea. LH_Landing y LH_Bronze viven en el
# mismo workspace que este notebook (WS_Retail_Bronze), así que basta con el workspace actual.

import json
import uuid
from datetime import datetime, timezone

from pyspark.sql import functions as F

BATCH_ID = f"fabric-{uuid.uuid4().hex[:8]}"
INGEST_TS = datetime.now(timezone.utc)

ONELAKE = "onelake.dfs.fabric.microsoft.com"
WORKSPACE = notebookutils.runtime.context["currentWorkspaceName"]


def lakehouse_uri(lakehouse: str) -> str:
    return f"abfss://{WORKSPACE}@{ONELAKE}/{lakehouse}.Lakehouse"


LANDING = lakehouse_uri("LH_Landing")
BRONZE = lakehouse_uri("LH_Bronze")

config_paths = [r.path for r in mssparkutils.fs.ls(f"{LANDING}/Files/config/ingestion")
                if r.path.endswith(".json")]

for cfg_path in config_paths:
    cfg = json.loads("".join(mssparkutils.fs.head(cfg_path, 1024 * 1024)))
    schema, table = cfg["target_schema"], cfg["target_table"]

    df = (spark.read
          .option("header", cfg["csv_options"].get("header", True))
          .option("sep", cfg["csv_options"].get("delimiter", ","))
          .option("encoding", cfg["csv_options"].get("encoding", "utf-8"))
          # Bronze fiel: todo como string, sin inferencia de tipos
          .option("inferSchema", "false")
          .csv(f"{LANDING}/{cfg['landing_path']}"))

    df = (df
          .withColumn("_input_file_name", F.input_file_name())
          .withColumn("_ingestion_timestamp", F.lit(INGEST_TS).cast("timestamp"))
          .withColumn("_batch_id", F.lit(BATCH_ID)))

    (df.write
        .mode("overwrite")
        .format("delta")
        .option("overwriteSchema", "true")
        .save(f"{BRONZE}/Tables/{schema}/{table}"))

    print(f"[BRONZE] LH_Bronze.{schema}.{table}: {df.count()} filas · batch={BATCH_ID}")

print("Bronze completado.")