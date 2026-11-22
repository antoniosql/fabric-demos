"""Lakehouse IO helpers for Microsoft Fabric notebooks."""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from frasohome_fabric.config import BRONZE_FILES_PATH, BRONZE_PREFIX, RAW_TABLES


def read_raw_csv(spark: SparkSession, file_name: str, base_path: str = BRONZE_FILES_PATH) -> DataFrame:
    """Read a raw CSV from the attached Lakehouse Files area as all strings."""
    return (
        spark.read.option("header", True)
        .option("multiLine", True)
        .option("escape", '"')
        .option("quote", '"')
        .option("encoding", "UTF-8")
        .csv(f"{base_path}/{file_name}")
    )


def write_delta_table(df: DataFrame, table_name: str, mode: str = "overwrite") -> None:
    """Write a DataFrame as a managed Delta table in the current Lakehouse."""
    (
        df.write.mode(mode)
        .format("delta")
        .option("overwriteSchema", "true")
        .saveAsTable(table_name)
    )


def ingest_bronze_tables(spark: SparkSession, base_path: str = BRONZE_FILES_PATH) -> dict[str, DataFrame]:
    """Load every raw source except the prebuilt reference fact into bronze tables."""
    bronze = {}
    for table_name, file_name in RAW_TABLES.items():
        df = (
            read_raw_csv(spark, file_name, base_path)
            .withColumn("_source_file", F.lit(file_name))
            .withColumn("_ingested_at_utc", F.current_timestamp())
        )
        write_delta_table(df, f"{BRONZE_PREFIX}{table_name}")
        bronze[table_name] = df
    return bronze

