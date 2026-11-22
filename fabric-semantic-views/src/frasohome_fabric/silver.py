"""Silver-layer transformations for FraSoHome."""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from frasohome_fabric.normalize import (
    normalize_category,
    normalize_id,
    normalize_payment_method,
    normalize_text,
    parse_bool,
    parse_decimal,
    parse_integer,
    parse_multiformat_timestamp,
)


def silver_crm(df: DataFrame) -> DataFrame:
    return (
        df.withColumnRenamed("tier_fidelizacion", "tier_fidelizacion_raw")
        .select(
            normalize_id(F.col("customer_id")).alias("customer_id"),
            normalize_text(F.col("nombre")).alias("nombre"),
            normalize_text(F.col("apellidos")).alias("apellidos"),
            F.lower(normalize_text(F.col("email"))).alias("email"),
            normalize_text(F.col("telefono")).alias("telefono"),
            parse_multiformat_timestamp(F.col("fecha_alta_programa")).cast("date").alias("fecha_alta_programa"),
            F.col("tier_fidelizacion_raw"),
            parse_integer(F.col("puntos_acumulados")).alias("puntos_acumulados"),
            parse_multiformat_timestamp(F.col("fecha_nacimiento")).cast("date").alias("fecha_nacimiento"),
            normalize_text(F.col("genero")).alias("genero"),
            normalize_text(F.col("ciudad")).alias("ciudad"),
            normalize_text(F.col("provincia")).alias("provincia"),
            normalize_text(F.col("codigo_postal")).alias("codigo_postal"),
            normalize_text(F.col("pais")).alias("pais"),
            parse_bool(F.col("consentimiento_marketing")).alias("consentimiento_marketing"),
            normalize_text(F.col("estado_cliente")).alias("estado_cliente"),
            parse_multiformat_timestamp(F.col("fecha_baja")).cast("date").alias("fecha_baja"),
            normalize_text(F.col("origen_alta")).alias("origen_alta"),
            normalize_text(F.col("canal_preferido_declarado")).alias("canal_preferido_declarado"),
            parse_multiformat_timestamp(F.col("ultima_actualizacion")).alias("ultima_actualizacion"),
        )
        .dropDuplicates(["customer_id"])
    )


def silver_productos(df: DataFrame) -> DataFrame:
    return df.select(
        normalize_id(F.col("product_id")).alias("product_id"),
        normalize_text(F.col("nombre_producto")).alias("nombre_producto"),
        normalize_category(F.col("categoria")).alias("categoria"),
        normalize_text(F.col("subcategoria")).alias("subcategoria"),
        normalize_text(F.col("marca")).alias("marca"),
        normalize_text(F.col("proveedor")).alias("proveedor"),
        parse_decimal(F.col("precio_venta")).alias("precio_venta"),
        parse_decimal(F.col("coste_unitario")).alias("coste_unitario"),
        parse_decimal(F.col("iva_pct")).alias("iva_pct"),
        parse_multiformat_timestamp(F.col("fecha_alta_catalogo")).cast("date").alias("fecha_alta_catalogo"),
        normalize_text(F.col("estado_producto")).alias("estado_producto"),
    ).dropDuplicates(["product_id"])


def silver_tiendas(df: DataFrame) -> DataFrame:
    return (
        df.select(
            normalize_id(F.col("store_id")).alias("store_id"),
            normalize_text(F.col("nombre_tienda")).alias("nombre_tienda"),
            normalize_text(F.col("tipo_ubicacion")).alias("tipo_ubicacion"),
            normalize_text(F.col("canal")).alias("canal"),
            normalize_text(F.col("ciudad")).alias("ciudad"),
            normalize_text(F.col("provincia")).alias("provincia"),
            normalize_text(F.col("region")).alias("region"),
            parse_multiformat_timestamp(F.col("fecha_apertura")).cast("date").alias("fecha_apertura"),
            parse_decimal(F.col("metros_cuadrados")).alias("metros_cuadrados"),
            parse_decimal(F.col("lat")).alias("lat"),
            parse_decimal(F.col("lon")).alias("lon"),
            normalize_text(F.col("estado")).alias("estado"),
            normalize_text(F.col("gerente")).alias("gerente"),
        )
        .dropDuplicates(["store_id"])
    )


def silver_pedidos(df: DataFrame) -> DataFrame:
    return df.select(
        normalize_id(F.col("order_id")).alias("order_id"),
        parse_multiformat_timestamp(F.col("fecha_pedido")).alias("fecha_pedido"),
        normalize_id(F.col("customer_id")).alias("customer_id"),
        normalize_id(F.col("usuario_online_id")).alias("usuario_online_id"),
        parse_decimal(F.col("importe_total")).alias("importe_total"),
        normalize_text(F.col("moneda")).alias("moneda"),
        parse_decimal(F.col("gastos_envio")).alias("gastos_envio"),
        normalize_text(F.col("metodo_pago")).alias("metodo_pago_raw"),
        normalize_payment_method(F.col("metodo_pago")).alias("metodo_pago"),
        normalize_text(F.col("estado_pedido")).alias("estado_pedido"),
        normalize_text(F.col("origen")).alias("origen"),
        parse_multiformat_timestamp(F.col("ultima_actualizacion")).alias("ultima_actualizacion"),
    )


def silver_lineas_pedido(df: DataFrame) -> DataFrame:
    return df.select(
        normalize_id(F.col("order_line_id")).alias("order_line_id"),
        normalize_id(F.col("order_id")).alias("order_id"),
        normalize_id(F.col("product_id")).alias("product_id"),
        normalize_text(F.col("descripcion_producto")).alias("descripcion_producto"),
        normalize_category(F.col("categoria")).alias("categoria"),
        normalize_text(F.col("subcategoria")).alias("subcategoria"),
        parse_decimal(F.col("cantidad")).alias("cantidad"),
        parse_decimal(F.col("precio_unitario")).alias("precio_unitario"),
        parse_decimal(F.col("descuento_pct")).alias("descuento_pct"),
        parse_decimal(F.col("descuento_importe")).alias("descuento_importe"),
        parse_decimal(F.col("importe_linea")).alias("importe_linea"),
        parse_decimal(F.col("iva_pct")).alias("iva_pct"),
    )


def silver_ventas_pos(df: DataFrame) -> DataFrame:
    return df.select(
        normalize_id(F.col("ticket_line_id")).alias("ticket_line_id"),
        normalize_id(F.col("ticket_id")).alias("ticket_id"),
        parse_multiformat_timestamp(F.col("fecha_hora")).alias("fecha_hora"),
        normalize_id(F.col("store_id")).alias("store_id"),
        normalize_id(F.col("caja_id")).alias("caja_id"),
        normalize_id(F.col("cajero_id")).alias("cajero_id"),
        normalize_id(F.col("customer_id")).alias("customer_id"),
        normalize_id(F.col("product_id")).alias("product_id"),
        normalize_text(F.col("descripcion_producto")).alias("descripcion_producto"),
        normalize_category(F.col("categoria")).alias("categoria"),
        normalize_text(F.col("subcategoria")).alias("subcategoria"),
        parse_decimal(F.col("cantidad")).alias("cantidad"),
        parse_decimal(F.col("precio_unitario")).alias("precio_unitario"),
        parse_decimal(F.col("descuento_pct")).alias("descuento_pct"),
        parse_decimal(F.col("descuento_importe")).alias("descuento_importe"),
        parse_decimal(F.col("importe_linea")).alias("importe_linea"),
        normalize_text(F.col("moneda")).alias("moneda"),
        normalize_text(F.col("canal")).alias("canal"),
    )


def silver_devoluciones_online(df: DataFrame) -> DataFrame:
    return (
        df.withColumnRenamed("motivo_devolucion", "motivo_devolucion_raw")
        .select(
            normalize_id(F.col("return_id")).alias("return_id"),
            normalize_id(F.col("order_id")).alias("order_id"),
            normalize_id(F.col("order_line_id")).alias("order_line_id"),
            normalize_id(F.col("product_id")).alias("product_id"),
            parse_multiformat_timestamp(F.col("fecha_devolucion")).alias("fecha_devolucion"),
            parse_decimal(F.col("cantidad_devuelta")).alias("cantidad_devuelta"),
            F.col("motivo_devolucion_raw"),
            normalize_text(F.col("metodo_devolucion")).alias("metodo_devolucion"),
            normalize_text(F.col("estado_devolucion")).alias("estado_devolucion"),
            parse_decimal(F.col("importe_reembolsado")).alias("importe_reembolsado"),
            normalize_text(F.col("moneda")).alias("moneda"),
            normalize_text(F.col("comentarios")).alias("comentarios"),
        )
    )


def silver_devoluciones_tienda(df: DataFrame) -> DataFrame:
    return (
        df.withColumnRenamed("motivo_devolucion", "motivo_devolucion_raw")
        .select(
            normalize_id(F.col("return_id")).alias("return_id"),
            parse_multiformat_timestamp(F.col("fecha_devolucion")).alias("fecha_devolucion"),
            normalize_id(F.col("store_id")).alias("store_id"),
            normalize_id(F.col("ticket_id_original")).alias("ticket_id_original"),
            normalize_id(F.col("ticket_line_id_original")).alias("ticket_line_id_original"),
            normalize_id(F.col("order_id_original")).alias("order_id_original"),
            normalize_id(F.col("customer_id")).alias("customer_id"),
            normalize_id(F.col("product_id")).alias("product_id"),
            parse_decimal(F.col("cantidad_devuelta")).alias("cantidad_devuelta"),
            normalize_text(F.col("estado_devolucion")).alias("estado_devolucion"),
            parse_decimal(F.col("importe_reembolsado")).alias("importe_reembolsado"),
            normalize_text(F.col("moneda")).alias("moneda"),
            normalize_text(F.col("metodo_reembolso")).alias("metodo_reembolso"),
            F.col("motivo_devolucion_raw"),
            normalize_text(F.col("canal_origen_venta")).alias("canal_origen_venta"),
            normalize_text(F.col("comentarios")).alias("comentarios"),
        )
    )


def silver_stock(df: DataFrame) -> DataFrame:
    return df.select(
        parse_multiformat_timestamp(F.col("fecha")).cast("date").alias("fecha"),
        normalize_id(F.col("store_id")).alias("store_id"),
        normalize_id(F.col("product_id")).alias("product_id"),
        parse_decimal(F.col("stock_cierre")).alias("stock_cierre"),
        parse_decimal(F.col("stock_reservado")).alias("stock_reservado"),
        parse_decimal(F.col("stock_en_transito")).alias("stock_en_transito"),
        parse_decimal(F.col("stock_minimo")).alias("stock_minimo"),
        normalize_text(F.col("fuente")).alias("fuente"),
    )

