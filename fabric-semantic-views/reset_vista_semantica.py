# FraSoHome · reset de la demo de vistas semánticas (celda de notebook de Fabric, PySpark)
# Antes de ejecutarlo, en el portal (Learn, "Delete a semantic view", 2026-11):
#   1. Borra solo la carpeta Context/Semantic Views/frasohome_ventas (no la carpeta padre).
#   2. Borra el modelo semántico generado `frasohome_ventas` del workspace (borrar la carpeta no lo borra).
#   3. Borra el Data Agent de la demo.
#   4. La salida de SystemContext/Semantic Views/frasohome_ventas solo se limpia al publicar otra vista en el
#      mismo lakehouse; si no hay otra, queda ahí (no estorba para repetir la demo).
spark.sql("DROP TABLE IF EXISTS gold_fact_movimientos")
spark.sql("DROP TABLE IF EXISTS gold_dim_fecha")
print("Tablas de la demo eliminadas. Las tablas de Tenerife no se tocan.")
