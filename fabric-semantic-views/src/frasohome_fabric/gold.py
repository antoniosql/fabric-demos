"""Gold-layer fact, feature, and scoring builders."""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import Window
from pyspark.sql import functions as F


def build_gold_fact(
    ventas_pos: DataFrame,
    pedidos: DataFrame,
    lineas_pedido: DataFrame,
    devoluciones_online: DataFrame,
    devoluciones_tienda: DataFrame,
    crm: DataFrame,
    productos: DataFrame,
) -> DataFrame:
    crm_ids = crm.select("customer_id").withColumn("flag_customer_in_crm", F.lit(True))
    product_dim = productos.select(
        "product_id",
        F.col("nombre_producto").alias("producto_nombre_master"),
        F.col("categoria").alias("categoria_master"),
        F.col("subcategoria").alias("subcategoria_master"),
        "precio_venta",
        "coste_unitario",
        F.col("estado_producto").alias("estado_producto_master"),
    ).withColumn("flag_product_in_master", F.lit(True))

    pos = (
        ventas_pos.alias("v")
        .join(product_dim.alias("p"), "product_id", "left")
        .select(
            F.lit("POS").alias("source_system"),
            F.lit("ventas_pos.csv").alias("source_file"),
            F.lit("POS").alias("canal_origen"),
            F.lit("POS").alias("canal_movimiento"),
            F.lit("VENTA").alias("tipo_movimiento"),
            F.lit(False).alias("es_devolucion"),
            F.col("fecha_hora").alias("fecha_movimiento"),
            F.col("store_id"),
            F.lit("TICKET").alias("doc_tipo"),
            F.col("ticket_id").alias("doc_id"),
            F.col("ticket_line_id").alias("line_id"),
            F.lit(None).cast("string").alias("return_id"),
            F.col("customer_id"),
            F.col("product_id"),
            F.coalesce(F.col("descripcion_producto"), F.col("producto_nombre_master")).alias("descripcion_producto"),
            F.coalesce(F.col("categoria"), F.col("categoria_master")).alias("categoria"),
            F.coalesce(F.col("subcategoria"), F.col("subcategoria_master")).alias("subcategoria"),
            F.col("cantidad").alias("cantidad_abs"),
            F.col("precio_unitario"),
            F.col("descuento_pct"),
            F.col("descuento_importe"),
            F.col("importe_linea").alias("importe_abs"),
            F.col("moneda"),
            F.col("coste_unitario"),
            F.lit(None).cast("string").alias("estado_pedido"),
            F.lit(None).cast("string").alias("origen"),
            F.lit(None).cast("string").alias("motivo_devolucion_norm"),
            F.col("caja_id"),
            F.col("cajero_id"),
        )
    )

    online = (
        lineas_pedido.alias("l")
        .join(pedidos.alias("o"), "order_id", "left")
        .join(product_dim.alias("p"), "product_id", "left")
        .select(
            F.lit("ECOM").alias("source_system"),
            F.lit("lineas_pedido.csv").alias("source_file"),
            F.lit("ONLINE").alias("canal_origen"),
            F.lit("ONLINE").alias("canal_movimiento"),
            F.lit("VENTA").alias("tipo_movimiento"),
            F.lit(False).alias("es_devolucion"),
            F.col("fecha_pedido").alias("fecha_movimiento"),
            F.lit("ONLINE").alias("store_id"),
            F.lit("ORDER").alias("doc_tipo"),
            F.col("order_id").alias("doc_id"),
            F.col("order_line_id").alias("line_id"),
            F.lit(None).cast("string").alias("return_id"),
            F.col("customer_id"),
            F.col("product_id"),
            F.coalesce(F.col("descripcion_producto"), F.col("producto_nombre_master")).alias("descripcion_producto"),
            F.coalesce(F.col("categoria"), F.col("categoria_master")).alias("categoria"),
            F.coalesce(F.col("subcategoria"), F.col("subcategoria_master")).alias("subcategoria"),
            F.col("cantidad").alias("cantidad_abs"),
            F.col("precio_unitario"),
            F.col("descuento_pct"),
            F.col("descuento_importe"),
            F.col("importe_linea").alias("importe_abs"),
            F.col("moneda"),
            F.col("coste_unitario"),
            F.col("estado_pedido"),
            F.col("origen"),
            F.lit(None).cast("string").alias("motivo_devolucion_norm"),
            F.lit(None).cast("string").alias("caja_id"),
            F.lit(None).cast("string").alias("cajero_id"),
        )
    )

    dev_online = (
        devoluciones_online.alias("d")
        .join(lineas_pedido.alias("l"), "order_line_id", "left")
        .join(pedidos.alias("o"), F.coalesce(F.col("d.order_id"), F.col("l.order_id")) == F.col("o.order_id"), "left")
        .join(product_dim.alias("p"), F.coalesce(F.col("d.product_id"), F.col("l.product_id")) == F.col("p.product_id"), "left")
        .select(
            F.lit("ECOM").alias("source_system"),
            F.lit("devoluciones_online.csv").alias("source_file"),
            F.lit("ONLINE").alias("canal_origen"),
            F.lit("ONLINE").alias("canal_movimiento"),
            F.lit("DEVOLUCION").alias("tipo_movimiento"),
            F.lit(True).alias("es_devolucion"),
            F.col("fecha_devolucion").alias("fecha_movimiento"),
            F.lit("ONLINE").alias("store_id"),
            F.lit("RETURN").alias("doc_tipo"),
            F.coalesce(F.col("d.order_id"), F.col("l.order_id")).alias("doc_id"),
            F.col("d.order_line_id").alias("line_id"),
            F.col("d.return_id"),
            F.col("o.customer_id"),
            F.coalesce(F.col("d.product_id"), F.col("l.product_id")).alias("product_id"),
            F.coalesce(F.col("l.descripcion_producto"), F.col("p.producto_nombre_master")).alias("descripcion_producto"),
            F.coalesce(F.col("l.categoria"), F.col("p.categoria_master")).alias("categoria"),
            F.coalesce(F.col("l.subcategoria"), F.col("p.subcategoria_master")).alias("subcategoria"),
            F.col("d.cantidad_devuelta").alias("cantidad_abs"),
            F.col("l.precio_unitario"),
            F.lit(None).cast("double").alias("descuento_pct"),
            F.lit(None).cast("double").alias("descuento_importe"),
            F.col("d.importe_reembolsado").alias("importe_abs"),
            F.col("d.moneda").alias("moneda"),
            F.col("p.coste_unitario"),
            F.col("d.estado_devolucion").alias("estado_pedido"),
            F.lit(None).cast("string").alias("origen"),
            F.col("d.motivo_devolucion_norm"),
            F.lit(None).cast("string").alias("caja_id"),
            F.lit(None).cast("string").alias("cajero_id"),
        )
    )

    dev_tienda = (
        devoluciones_tienda.alias("d")
        .join(ventas_pos.alias("v"), F.col("d.ticket_line_id_original") == F.col("v.ticket_line_id"), "left")
        .join(product_dim.alias("p"), F.coalesce(F.col("d.product_id"), F.col("v.product_id")) == F.col("p.product_id"), "left")
        .select(
            F.lit("POS").alias("source_system"),
            F.lit("devoluciones_tienda.csv").alias("source_file"),
            F.coalesce(F.col("canal_origen_venta"), F.lit("POS")).alias("canal_origen"),
            F.lit("POS").alias("canal_movimiento"),
            F.lit("DEVOLUCION").alias("tipo_movimiento"),
            F.lit(True).alias("es_devolucion"),
            F.col("d.fecha_devolucion").alias("fecha_movimiento"),
            F.coalesce(F.col("d.store_id"), F.col("v.store_id")).alias("store_id"),
            F.lit("RETURN").alias("doc_tipo"),
            F.coalesce(F.col("d.ticket_id_original"), F.col("d.order_id_original")).alias("doc_id"),
            F.col("d.ticket_line_id_original").alias("line_id"),
            F.col("d.return_id"),
            F.coalesce(F.col("d.customer_id"), F.col("v.customer_id")).alias("customer_id"),
            F.coalesce(F.col("d.product_id"), F.col("v.product_id")).alias("product_id"),
            F.coalesce(F.col("v.descripcion_producto"), F.col("p.producto_nombre_master")).alias("descripcion_producto"),
            F.coalesce(F.col("v.categoria"), F.col("p.categoria_master")).alias("categoria"),
            F.coalesce(F.col("v.subcategoria"), F.col("p.subcategoria_master")).alias("subcategoria"),
            F.col("d.cantidad_devuelta").alias("cantidad_abs"),
            F.col("v.precio_unitario").alias("precio_unitario"),
            F.lit(None).cast("double").alias("descuento_pct"),
            F.lit(None).cast("double").alias("descuento_importe"),
            F.col("d.importe_reembolsado").alias("importe_abs"),
            F.col("d.moneda").alias("moneda"),
            F.col("p.coste_unitario"),
            F.col("d.estado_devolucion").alias("estado_pedido"),
            F.lit(None).cast("string").alias("origen"),
            F.col("d.motivo_devolucion_norm"),
            F.lit(None).cast("string").alias("caja_id"),
            F.lit(None).cast("string").alias("cajero_id"),
        )
    )

    fact = pos.unionByName(online).unionByName(dev_online).unionByName(dev_tienda)
    fact = (
        fact.join(crm_ids, "customer_id", "left")
        .withColumn("flag_customer_in_crm", F.coalesce(F.col("flag_customer_in_crm"), F.lit(False)))
        .join(product_dim.select("product_id", "flag_product_in_master", "estado_producto_master"), "product_id", "left")
        .withColumn("flag_product_in_master", F.coalesce(F.col("flag_product_in_master"), F.lit(False)))
        .withColumn("cantidad_signed", F.when(F.col("es_devolucion"), -F.col("cantidad_abs")).otherwise(F.col("cantidad_abs")))
        .withColumn("importe_signed", F.when(F.col("es_devolucion"), -F.col("importe_abs")).otherwise(F.col("importe_abs")))
        .withColumn("coste_total", F.col("coste_unitario") * F.col("cantidad_abs"))
        .withColumn("margen_bruto", F.when(~F.col("es_devolucion"), F.col("importe_abs") - F.col("coste_total")).otherwise(F.lit(0.0)))
        .withColumn("flag_fecha_parseada", F.col("fecha_movimiento").isNotNull())
        .withColumn("flag_importe_parseado", F.col("importe_abs").isNotNull())
        .withColumn("fact_id", F.format_string("F%06d", F.row_number().over(Window.orderBy("source_file", "doc_id", "line_id", "return_id"))))
    )
    return fact


def build_customer_features(spark: SparkSession, fact_table: str = "gold_fact_transacciones") -> DataFrame:
    fact = spark.table(fact_table)
    max_date = fact.where("fecha_movimiento IS NOT NULL").agg(F.max("fecha_movimiento")).first()[0]
    return (
        fact.where("customer_id IS NOT NULL")
        .groupBy("customer_id")
        .agg(
            F.sum(F.when(F.col("tipo_movimiento") == "VENTA", F.col("importe_abs")).otherwise(F.lit(0.0))).alias("gasto_total"),
            F.countDistinct(F.when(F.col("tipo_movimiento") == "VENTA", F.col("doc_id"))).alias("frecuencia"),
            F.max(F.when(F.col("tipo_movimiento") == "VENTA", F.col("fecha_movimiento"))).alias("ultima_compra"),
            F.sum(F.when(F.col("tipo_movimiento") == "DEVOLUCION", F.col("importe_abs")).otherwise(F.lit(0.0))).alias("importe_devoluciones"),
            F.count(F.when(F.col("tipo_movimiento") == "DEVOLUCION", True)).alias("num_devoluciones"),
        )
        .withColumn("ticket_medio", F.when(F.col("frecuencia") > 0, F.col("gasto_total") / F.col("frecuencia")))
        .withColumn("tasa_devolucion_cliente", F.when(F.col("gasto_total") > 0, F.col("importe_devoluciones") / F.col("gasto_total")).otherwise(F.lit(0.0)))
        .withColumn("recencia_dias", F.datediff(F.lit(max_date), F.col("ultima_compra")))
    )


def build_product_features(spark: SparkSession, fact_table: str = "gold_fact_transacciones", stock_table: str = "silver_stock_diario") -> DataFrame:
    fact = spark.table(fact_table)
    stock = spark.table(stock_table)
    stock_risk = (
        stock.groupBy("product_id")
        .agg(
            F.avg(F.when(F.col("stock_cierre") < F.col("stock_minimo"), F.lit(1.0)).otherwise(F.lit(0.0))).alias("riesgo_rotura_stock"),
            F.avg("stock_cierre").alias("stock_medio"),
        )
    )
    return (
        fact.groupBy("product_id", "descripcion_producto", "categoria", "subcategoria")
        .agg(
            F.sum(F.when(F.col("tipo_movimiento") == "VENTA", F.col("importe_abs")).otherwise(F.lit(0.0))).alias("ventas"),
            F.sum(F.when(F.col("tipo_movimiento") == "VENTA", F.col("margen_bruto")).otherwise(F.lit(0.0))).alias("margen_bruto"),
            F.sum(F.when(F.col("tipo_movimiento") == "DEVOLUCION", F.col("importe_abs")).otherwise(F.lit(0.0))).alias("devoluciones"),
            F.sum(F.when(F.col("tipo_movimiento") == "VENTA", F.col("cantidad_abs")).otherwise(F.lit(0.0))).alias("unidades_vendidas"),
        )
        .withColumn("tasa_devolucion_producto", F.when(F.col("ventas") > 0, F.col("devoluciones") / F.col("ventas")).otherwise(F.lit(0.0)))
        .join(stock_risk, "product_id", "left")
    )


def build_customer_score(features: DataFrame) -> DataFrame:
    w_all = Window.rowsBetween(Window.unboundedPreceding, Window.unboundedFollowing)
    scored = (
        features.withColumn("max_gasto", F.max("gasto_total").over(w_all))
        .withColumn("max_frecuencia", F.max("frecuencia").over(w_all))
        .withColumn("max_recencia", F.max("recencia_dias").over(w_all))
        .withColumn("gasto_norm", F.when(F.col("max_gasto") > 0, F.col("gasto_total") / F.col("max_gasto")).otherwise(F.lit(0.0)))
        .withColumn("frecuencia_norm", F.when(F.col("max_frecuencia") > 0, F.col("frecuencia") / F.col("max_frecuencia")).otherwise(F.lit(0.0)))
        .withColumn("recencia_norm", F.when(F.col("max_recencia") > 0, 1 - (F.col("recencia_dias") / F.col("max_recencia"))).otherwise(F.lit(1.0)))
        .withColumn("dev_norm", F.greatest(F.lit(0.0), F.lit(1.0) - F.col("tasa_devolucion_cliente")))
        .withColumn("score", F.round((0.40 * F.col("gasto_norm") + 0.30 * F.col("frecuencia_norm") + 0.20 * F.col("recencia_norm") + 0.10 * F.col("dev_norm")) * 100, 0).cast("int"))
        .withColumn("riesgo_fuga", (F.col("recencia_dias") > 120) & (F.col("score") < 40))
        .drop("max_gasto", "max_frecuencia", "max_recencia")
    )
    return scored
