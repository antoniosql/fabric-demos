# Fabric notebook — NB_Transform_Bronze_To_Silver
# Capa: SILVER. Workspace: WS_Retail_Silver. Lakehouse: LH_Silver (destino), lee de LH_Bronze.
#
# Tipado explicito, normalizacion de los problemas de calidad de FraSoHome, reglas de calidad
# (_is_valid / _dq_reasons) y deduplicacion por clave de negocio. Dirigido por config/ingestion/*.json.
#
# Idempotente: overwrite por tabla.
#
# RUTAS ONELAKE EXPLICITAS: igual que NB_Load_Bronze_Retail, sin lakehouse por defecto adjunto.
# Ademas LH_Bronze vive en OTRO workspace (WS_Retail_Bronze) que este notebook (WS_Retail_Silver)
# en el diseño "separated" -> hace falta el nombre de ese workspace de origen explicito, no se
# puede derivar del contexto de ejecucion actual. Si usas el diseño "collapsed" de
# config/workspaces.json (un unico WS_Retail), cambia UPSTREAM_WORKSPACE por el mismo valor que
# WORKSPACE.

import json
import re
import unicodedata
from datetime import datetime

from pyspark.sql import Window
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, TimestampType, StringType

# ---------------- Parsers (UDFs) — mismos criterios que el runner local ----------------
_MESES = {"enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,"julio":7,
          "agosto":8,"septiembre":9,"setiembre":9,"octubre":10,"noviembre":11,"diciembre":12}
_ISO = ("%Y-%m-%d %H:%M:%S","%Y-%m-%d %H:%M","%Y-%m-%d")
_SLASH = ("%d/%m/%Y %H:%M:%S","%d/%m/%Y %H:%M","%d/%m/%Y","%d/%m/%y %H:%M:%S","%d/%m/%y %H:%M","%d/%m/%y")

def _accents(s): return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def _parse_dt(v):
    if v is None: return None
    s = str(v).strip()
    if s == "" or s.lower() in ("nan","none","null"): return None
    for fmt in _ISO + _SLASH:
        try: return datetime.strptime(s, fmt)
        except ValueError: pass
    m = re.match(r"(\d{1,2})\s+de\s+([A-Za-zñÑáéíóú]+)\s+de\s+(\d{4})(?:\s+(\d{1,2}):(\d{2}))?", s, re.I)
    if m:
        d, mes, y, hh, mm = m.groups()
        n = _MESES.get(_accents(mes.lower()))
        if n: return datetime(int(y), n, int(d), int(hh or 0), int(mm or 0))
    return None

def _parse_dec(v):
    if v is None: return None
    s = re.sub(r"[€$£\s]", "", str(v).strip())
    if s == "" or s.lower() in ("nan","none","null"): return None
    if "." in s and "," in s: s = s.replace(".", "").replace(",", ".")
    elif "," in s: s = s.replace(",", ".")
    try: return float(s)
    except ValueError: return None

def _norm_id(v):
    if v is None: return None
    s = re.sub(r"\s+", "", str(v).strip()).upper()
    return s or None

udf_dt = F.udf(_parse_dt, TimestampType())
udf_dec = F.udf(_parse_dec, DoubleType())
udf_id = F.udf(_norm_id, StringType())

# ---------------- Rutas OneLake ----------------
UPSTREAM_WORKSPACE = "WS_Retail_Bronze"  # workspace de la capa Bronze (ver nota arriba)
ONELAKE = "onelake.dfs.fabric.microsoft.com"
WORKSPACE = notebookutils.runtime.context["currentWorkspaceName"]


def lakehouse_uri(workspace: str, lakehouse: str) -> str:
    return f"abfss://{workspace}@{ONELAKE}/{lakehouse}.Lakehouse"


LANDING = lakehouse_uri(UPSTREAM_WORKSPACE, "LH_Landing")
BRONZE = lakehouse_uri(UPSTREAM_WORKSPACE, "LH_Bronze")
SILVER = lakehouse_uri(WORKSPACE, "LH_Silver")

# ---------------- Proceso ----------------
config_paths = [r.path for r in mssparkutils.fs.ls(f"{LANDING}/Files/config/ingestion")
                if r.path.endswith(".json")]

for cfg_path in config_paths:
    cfg = json.loads("".join(mssparkutils.fs.head(cfg_path, 1024 * 1024)))
    schema, table = cfg["target_schema"], cfg["target_table"]
    s = cfg.get("silver", {})
    df = spark.read.format("delta").load(f"{BRONZE}/Tables/{schema}/{table}")

    for c in s.get("id_normalize_columns", []):
        if c in df.columns: df = df.withColumn(c, udf_id(F.col(c)))
    for c in s.get("date_columns", []):
        if c in df.columns: df = df.withColumn(c, udf_dt(F.col(c)))
    for c in s.get("decimal_columns", []):
        if c in df.columns: df = df.withColumn(c, udf_dec(F.col(c)))
    for c in df.columns:                     # limpieza de texto restante
        if c.startswith("_") or c in set(s.get("date_columns",[])) | set(s.get("decimal_columns",[])):
            continue
        df = df.withColumn(c, F.trim(F.regexp_replace(F.col(c).cast("string"), r"\s+", " ")))

    df = df.withColumn("_source_system", F.lit(cfg["source_system"]))

    # Reglas de calidad
    bk = cfg["business_key"]
    reasons = F.array()
    key_null = None
    for k in bk:
        cond = F.col(k).isNull() | (F.col(k) == "")
        key_null = cond if key_null is None else (key_null | cond)
    reasons = F.when(key_null, F.array(F.lit("clave_negocio_nula"))).otherwise(F.array())
    for c in s.get("decimal_columns", []):
        if "descuento" in c: continue
        reasons = F.when(F.col(c) < 0, F.array_union(reasons, F.array(F.lit(f"{c}_negativo")))).otherwise(reasons)
    df = (df.withColumn("_dq_reasons", F.array_join(reasons, "; "))
            .withColumn("_is_valid", F.col("_dq_reasons") == ""))

    # Deduplicacion por clave de negocio (conserva el mas reciente)
    order_cols = [c for c in s.get("dedup_order_by", []) if c in df.columns]
    if order_cols:
        w = Window.partitionBy(*bk).orderBy(*[F.col(c).desc_nulls_last() for c in order_cols])
        df = df.withColumn("_rn", F.row_number().over(w)).filter(F.col("_rn") == 1).drop("_rn")

    target = f"{SILVER}/Tables/{schema}/{table}"
    df.write.mode("overwrite").format("delta").option("overwriteSchema", "true").save(target)
    print(f"[SILVER] LH_Silver.{schema}.{table}: {df.count()} filas")

print("Silver completado.")
