from fabric_sessions.dataset import normalize_id, parse_date, parse_money


def test_parse_money_handles_symbols_and_decimal_comma():
    assert parse_money("€1342.89") == 1342.89
    assert parse_money("127,74") == 127.74
    assert parse_money("1.234,56") == 1234.56


def test_parse_date_handles_mixed_formats():
    assert parse_date("2025-05-11 15:46:46").year == 2025
    assert parse_date("20/03/2024 09:20").month == 3
    assert parse_date("13/12/25 11:42").day == 13


def test_normalize_id_uppercases_customer_ids():
    assert normalize_id(" c0030 ") == "C0030"
