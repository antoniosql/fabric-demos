# %% [markdown]
# # 01 · Preparar la vista semántica
#
# Una vista semántica no admite consultas como origen ni columnas calculadas, así que se materializan dos tablas Delta:
# - `gold_fact_movimientos`: la tabla de hechos con una columna `fecha` sin hora.
# - `gold_dim_fecha`: calendario diario 2024-2026.
#
# Requisito: haber ejecutado `00_build_lakehouse`. Al final saca las cifras de referencia del acto 1.

# %%
from pyspark.sql import functions as F

fact = spark.table("gold_fact_transacciones")

columnas = [
    "fact_id", "fecha_movimiento", "tipo_movimiento", "canal_movimiento", "customer_id", "product_id",
    "store_id", "doc_id", "cantidad_abs", "importe_abs", "importe_signed", "margen_bruto",
]
faltan = [c for c in columnas if c not in fact.columns]
assert not faltan, f"gold_fact_transacciones no tiene las columnas {faltan}; revisa el notebook 00."

# %%
movimientos = fact.select(
    "fact_id",
    F.to_date("fecha_movimiento").alias("fecha"),
    "tipo_movimiento",
    "canal_movimiento",
    "customer_id",
    "product_id",
    "store_id",
    "doc_id",
    "cantidad_abs",
    "importe_abs",
    "importe_signed",
    "margen_bruto",
)
movimientos.write.mode("overwrite").format("delta").option("overwriteSchema", "true").saveAsTable("gold_fact_movimientos")

calendario = (
    spark.sql("SELECT explode(sequence(to_date('2024-01-01'), to_date('2026-12-31'), interval 1 day)) AS fecha")
    .withColumn("anio", F.year("fecha"))
    .withColumn("trimestre", F.quarter("fecha"))
    .withColumn("mes", F.month("fecha"))
    .withColumn("anio_mes", F.date_format("fecha", "yyyy-MM"))
)
calendario.write.mode("overwrite").format("delta").option("overwriteSchema", "true").saveAsTable("gold_dim_fecha")

# Control: filas con fecha vacía o fuera del calendario (el caso trae fechas de 2017, 2030 y 2031).
movimientos = spark.table("gold_fact_movimientos")
fuera = movimientos.filter(F.col("fecha").isNull() | (F.col("fecha") < "2024-01-01") | (F.col("fecha") > "2026-12-31"))
print("Movimientos:", movimientos.count(), "· fuera del calendario o sin fecha:", fuera.count())

# %% [markdown]
# ## Cifras de referencia (deben coincidir con la vista publicada)

# %%
spark.sql("""
SELECT
  ROUND(SUM(CASE WHEN tipo_movimiento = 'VENTA' THEN importe_abs ELSE 0 END), 2)       AS ventas_brutas,
  ROUND(SUM(CASE WHEN tipo_movimiento = 'DEVOLUCION' THEN importe_abs ELSE 0 END), 2)  AS devoluciones,
  ROUND(SUM(CASE WHEN tipo_movimiento = 'VENTA' THEN importe_abs ELSE 0 END)
      - SUM(CASE WHEN tipo_movimiento = 'DEVOLUCION' THEN importe_abs ELSE 0 END), 2)  AS ventas_netas,
  ROUND(SUM(importe_signed), 2)                                                        AS suma_con_signo
FROM gold_fact_movimientos
""").show()

# %% [markdown]
# ## Control: `store_id` único en `silver_tiendas`
#
# La relación `movimientos_a_tiendas` exige `store_id` único. Si devuelve filas, hay que deduplicar en silver o quitar la relación.

# %%
spark.sql("SELECT store_id, COUNT(*) n FROM silver_tiendas GROUP BY store_id HAVING COUNT(*) > 1").show()
