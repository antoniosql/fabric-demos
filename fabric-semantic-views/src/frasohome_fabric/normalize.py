"""PySpark normalization helpers for the FraSoHome medallion pipeline."""

from __future__ import annotations

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F


def trim_to_null(col: Column) -> Column:
    return F.when(F.trim(col).isin("", "NULL", "null", "N/A", "NA"), F.lit(None)).otherwise(F.trim(col))


def normalize_id(col: Column) -> Column:
    return F.upper(trim_to_null(col))


def normalize_text(col: Column) -> Column:
    return trim_to_null(F.regexp_replace(col, r"\s+", " "))


def normalize_ascii_key(col: Column) -> Column:
    value = F.lower(normalize_text(col))
    value = F.translate(value, "áéíóúÁÉÍÓÚüÜñÑ", "aeiouAEIOUuUnN")
    return F.regexp_replace(value, r"[^a-z0-9]+", "_")


def parse_decimal(col: Column) -> Column:
    cleaned = F.regexp_replace(F.regexp_replace(F.regexp_replace(trim_to_null(col), "€", ""), " ", ""), '"', "")
    comma_decimal = (F.instr(cleaned, ",") > 0) & (F.instr(cleaned, ".") == 0)
    normalized = F.when(comma_decimal, F.regexp_replace(cleaned, ",", ".")).otherwise(cleaned)
    valid = normalized.rlike(r"^-?\d+(\.\d+)?$")
    return F.when(valid, normalized.cast("double"))


def parse_integer(col: Column) -> Column:
    parsed = parse_decimal(col)
    return F.when(parsed.isNotNull(), parsed.cast("int"))


def parse_bool(col: Column) -> Column:
    value = normalize_ascii_key(col)
    return (
        F.when(value.isin("1", "si", "s", "true", "yes", "y"), F.lit(True))
        .when(value.isin("0", "no", "n", "false"), F.lit(False))
    )


def parse_multiformat_timestamp(col: Column) -> Column:
    value = normalize_text(col)

    spanish_months = {
        "enero": "01",
        "febrero": "02",
        "marzo": "03",
        "abril": "04",
        "mayo": "05",
        "junio": "06",
        "julio": "07",
        "agosto": "08",
        "septiembre": "09",
        "setiembre": "09",
        "octubre": "10",
        "noviembre": "11",
        "diciembre": "12",
    }

    spanish = F.lower(value)
    for name, number in spanish_months.items():
        spanish = F.regexp_replace(spanish, name, number)
    spanish = F.regexp_replace(
        spanish,
        r"^(\d{1,2}) de ([a-záéíóú]+|\d{2}) de (\d{4})(.*)$",
        "$1/$2/$3$4",
    )

    def parse_if(source: Column, pattern: str, fmt: str) -> Column:
        return F.when(source.rlike(pattern), F.to_timestamp(source, fmt))

    return F.coalesce(
        parse_if(value, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", "yyyy-MM-dd HH:mm:ss"),
        parse_if(value, r"^\d{4}-\d{2}-\d{2}$", "yyyy-MM-dd"),
        parse_if(value, r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}$", "yyyy/MM/dd HH:mm:ss"),
        parse_if(value, r"^\d{4}/\d{2}/\d{2}$", "yyyy/MM/dd"),
        parse_if(value, r"^\d{1,2}/\d{1,2}/\d{4} \d{2}:\d{2}:\d{2}$", "d/M/yyyy HH:mm:ss"),
        parse_if(value, r"^\d{1,2}/\d{1,2}/\d{4} \d{2}:\d{2}$", "d/M/yyyy HH:mm"),
        parse_if(value, r"^\d{1,2}/\d{1,2}/\d{4}$", "d/M/yyyy"),
        parse_if(value, r"^\d{1,2}/\d{1,2}/\d{2} \d{2}:\d{2}$", "d/M/yy HH:mm"),
        parse_if(value, r"^\d{1,2}/\d{1,2}/\d{2}$", "d/M/yy"),
        parse_if(spanish, r"^\d{1,2}/\d{1,2}/\d{4} \d{2}:\d{2}$", "d/M/yyyy HH:mm"),
        parse_if(spanish, r"^\d{1,2}/\d{1,2}/\d{4}$", "d/M/yyyy"),
    )


def normalize_category(col: Column) -> Column:
    key = normalize_ascii_key(col)
    return (
        F.when(key == "decoracion", F.lit("Decoracion"))
        .when(key == "iluminacion", F.lit("Iluminacion"))
        .when(key == "muebles", F.lit("Muebles"))
        .when(key == "textil_hogar", F.lit("Textil hogar"))
    )


def normalize_tier_rule_based(col: Column) -> Column:
    """Deterministic fallback after AI classification for known finite values."""
    key = normalize_ascii_key(col)
    return (
        F.when(key.isin("bronce", "bronze"), F.lit("Bronce"))
        .when(key.isin("plata", "silver"), F.lit("Plata"))
        .when(key.isin("oro", "gold"), F.lit("Oro"))
        .when(key.isin("platino", "platinum", "vip"), F.lit("Platino"))
    )


def normalize_payment_method(col: Column) -> Column:
    key = normalize_ascii_key(col)
    return (
        F.when(key.isin("visa_mastercard", "tarjeta_credito", "credit_card", "cc"), F.lit("Tarjeta credito"))
        .when(key.isin("tarjeta_debito", "debit_card", "dc", "debito"), F.lit("Tarjeta debito"))
        .when(key.isin("efectivo", "cash", "contado"), F.lit("Efectivo"))
        .when(key.isin("tarjeta_regalo", "giftcard", "gift_card"), F.lit("Tarjeta regalo"))
        .when(key.isin("vale", "vale_devolucion", "voucher", "cupon"), F.lit("Vale o cupon"))
        .when(key == "bizum", F.lit("Bizum"))
        .when(key.isin("financiacion", "financing", "aplazado"), F.lit("Financiacion"))
    )


def with_parse_flag(df: DataFrame, raw_col: str, parsed_col: str, flag_col: str) -> DataFrame:
    return df.withColumn(flag_col, F.col(raw_col).isNull() | F.col(parsed_col).isNotNull())

