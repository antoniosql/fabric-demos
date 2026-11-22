# FraSoHome · preparación de la demo de vistas semánticas (celda de notebook de Fabric, PySpark)
# Requisito: lakehouse con las tablas de los notebooks 00-03 de tenerife-summer-sessions-2026.
# Crea dos tablas Delta porque una vista semántica no admite consultas como origen ni columnas calculadas:
#   - gold_fact_movimientos: la tabla de hechos con una columna `fecha` sin hora
#   - gold_dim_fecha: calendario diario 2024-2026
# [verificar en el ensayo] los nombres de columna de gold_fact_transacciones (ver semantic_measures.dax).
from pyspark.sql import functions as F

fact = spark.table("gold_fact_transacciones")

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
movimientos.write.mode("overwrite").format("delta").saveAsTable("gold_fact_movimientos")

calendario = (
    spark.sql("SELECT explode(sequence(to_date('2024-01-01'), to_date('2026-12-31'), interval 1 day)) AS fecha")
    .withColumn("anio", F.year("fecha"))
    .withColumn("trimestre", F.quarter("fecha"))
    .withColumn("mes", F.month("fecha"))
    .withColumn("anio_mes", F.date_format("fecha", "yyyy-MM"))
)
calendario.write.mode("overwrite").format("delta").saveAsTable("gold_dim_fecha")

# Control: filas con fecha vacía o fuera del calendario (el caso trae fechas de 2017, 2030 y 2031).
fuera = movimientos.filter(F.col("fecha").isNull() | (F.col("fecha") < "2024-01-01") | (F.col("fecha") > "2026-12-31"))
print("Movimientos:", movimientos.count(), "· fuera del calendario o sin fecha:", fuera.count())

# Cifras de referencia para el gancho y el acto 1 (deben coincidir con la vista publicada).
spark.sql("""
SELECT
  ROUND(SUM(CASE WHEN tipo_movimiento = 'VENTA' THEN importe_abs ELSE 0 END), 2)       AS ventas_brutas,
  ROUND(SUM(CASE WHEN tipo_movimiento = 'DEVOLUCION' THEN importe_abs ELSE 0 END), 2)  AS devoluciones,
  ROUND(SUM(CASE WHEN tipo_movimiento = 'VENTA' THEN importe_abs ELSE 0 END)
      - SUM(CASE WHEN tipo_movimiento = 'DEVOLUCION' THEN importe_abs ELSE 0 END), 2)  AS ventas_netas,
  ROUND(SUM(importe_signed), 2)                                                        AS suma_con_signo
FROM gold_fact_movimientos
""").show()

# Control: la relación movimientos → tiendas exige store_id único en silver_tiendas.
spark.sql("SELECT store_id, COUNT(*) n FROM silver_tiendas GROUP BY store_id HAVING COUNT(*) > 1").show()
