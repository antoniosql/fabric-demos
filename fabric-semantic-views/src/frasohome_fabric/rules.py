"""Limpieza semántica determinista (sustituye a las Fabric AI Functions de la sesión de Tenerife).

En Tenerife los tiers de fidelización y los motivos de devolución se normalizan con `df.ai.classify`.
Aquí se hace con reglas para que la demo se reproduzca sin capacidad de IA, sin coste de CU y con el
mismo resultado en cada ejecución. Ninguna de las métricas de la vista semántica depende de estas dos
columnas; solo aparecen como atributos de `clientes`.
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from frasohome_fabric.normalize import normalize_ascii_key, normalize_tier_rule_based


def classify_tier_rules(df: DataFrame, input_col: str = "tier_fidelizacion_raw") -> DataFrame:
    """Añade `tier_fidelizacion` (Bronce, Plata, Oro, Platino o NULL si el valor no es reconocible)."""
    return df.withColumn("tier_fidelizacion", normalize_tier_rule_based(F.col(input_col)))


def classify_return_reason_rules(df: DataFrame, input_col: str = "motivo_devolucion_raw") -> DataFrame:
    """Añade `motivo_devolucion_norm` con las seis categorías del caso, o NULL si no encaja en ninguna."""
    key = normalize_ascii_key(F.col(input_col))
    motivo = (
        F.when(key.rlike("medida|encaja|talla"), F.lit("Talla o medidas"))
        .when(key.rlike("defect|pieza|incompleto|dano|danos"), F.lit("Defecto o producto incompleto"))
        .when(key.rlike("gusto|color|expectativa"), F.lit("No cumple expectativa"))
        .when(key.rlike("opinion"), F.lit("Cambio de opinion"))
        .when(key.rlike("tarde|transporte|envio|logistica"), F.lit("Logistica o transporte"))
        .when(key.rlike("fraude|otro"), F.lit("Fraude o excepcion"))
    )
    return df.withColumn("motivo_devolucion_norm", motivo)
