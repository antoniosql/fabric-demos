# Fabric notebook — NB_Build_Gold_Star
# Capa: GOLD. Workspace: WS_Retail_Gold. Lakehouse: LH_Gold (destino), lee de LH_Silver.
#
# Construye el modelo en estrella: dim_cliente, dim_producto, dim_tienda, dim_fecha y
# fact_ventas (lineas online + POS unificadas). Listo para Direct Lake sobre SM_Retail_Sales.
#
# Idempotente: overwrite por tabla.

from pyspark.sql import functions as F

def save(df, name):
    df.write.mode("overwrite").format("delta").option("overwriteSchema", "true").saveAsTable(f"LH_Gold.gold.{name}")
    print(f"[GOLD] gold.{name}: {df.count()} filas")

# -------- Dimensiones --------
clientes = spark.read.table("LH_Silver.crm.clientes")
save(clientes.select("customer_id","nombre","apellidos","email","ciudad","provincia",
                     "pais","tier_fidelizacion","estado_cliente"), "dim_cliente")

productos = spark.read.table("LH_Silver.erp.productos")
save(productos.select("product_id","nombre_producto","categoria","subcategoria","marca",
                      "precio_venta","coste_unitario"), "dim_producto")

tiendas = spark.read.table("LH_Silver.erp.tiendas")
save(tiendas.select("store_id","nombre_tienda","canal","ciudad","provincia","region"), "dim_tienda")

# -------- Hecho: online + POS --------
lp = spark.read.table("LH_Silver.retail.lineas_pedido")
ped = spark.read.table("LH_Silver.retail.pedidos").select("order_id","customer_id","fecha_pedido")
online = (lp.join(ped, "order_id", "left")
          .select(F.col("order_line_id").alias("venta_id"),
                  F.col("fecha_pedido").alias("fecha"),
                  "customer_id", "product_id",
                  F.lit(None).cast("string").alias("store_id"),
                  F.lit("ONLINE").alias("canal"),
                  F.col("cantidad").cast("int").alias("cantidad"),
                  F.col("importe_linea").cast("double").alias("importe_linea")))

pos = spark.read.table("LH_Silver.pos.ventas").select(
        F.col("ticket_line_id").alias("venta_id"),
        F.col("fecha_hora").alias("fecha"),
        "customer_id", "product_id", "store_id",
        F.lit("POS").alias("canal"),
        F.col("cantidad").cast("int").alias("cantidad"),
        F.col("importe_linea").cast("double").alias("importe_linea"))

fact = (online.unionByName(pos)
        .withColumn("fecha_key", F.date_format("fecha", "yyyyMMdd")))
save(fact, "fact_ventas")

# -------- dim_fecha --------
fechas = (fact.select(F.to_date("fecha").alias("fecha")).where(F.col("fecha").isNotNull()).distinct())
dim_fecha = fechas.select(
    F.date_format("fecha", "yyyyMMdd").alias("fecha_key"), "fecha",
    F.year("fecha").alias("anio"), F.month("fecha").alias("mes"), F.dayofmonth("fecha").alias("dia"))
save(dim_fecha, "dim_fecha")

# -------- Integridad referencial (informe) --------
prod_ids = productos.select("product_id")
orphans = fact.join(prod_ids, "product_id", "left_anti").count()
print(f"[GOLD] fact_ventas: {orphans} lineas con product_id huerfano (revisar crosswalks)")

print("Gold completado. Exponer via Direct Lake en SM_Retail_Sales.")
