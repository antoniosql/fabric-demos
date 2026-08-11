from pathlib import Path

from fabric_sessions.dataset import EXPECTED_FILES, validate_source_dataset


def test_expected_contract_includes_all_session_files():
    assert set(EXPECTED_FILES) == {
        "crm.csv",
        "devoluciones_online.csv",
        "devoluciones_tienda.csv",
        "fact_transacciones.csv",
        "lineas_pedido.csv",
        "pagos_tienda.csv",
        "pedidos.csv",
        "productos.csv",
        "stock_diario.csv",
        "tiendas.csv",
        "ventas_pos.csv",
    }


def test_missing_source_dir_is_error(tmp_path: Path):
    issues = validate_source_dataset(tmp_path / "missing")
    assert issues
    assert issues[0].severity == "error"
