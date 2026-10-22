import csv

from frontend.csv_snapshot import read_csv_snapshot


FIELDS = [
    "code",
    "name",
    "stock_type",
    "total_market_val",
    "prev_close_price",
    "update_time",
]


def write_snapshot(tmp_path, rows):
    path = tmp_path / "snapshot.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def stock_row(**changes):
    row = {
        "code": "US.EXAMPLE",
        "name": "Synthetic Test Company",
        "stock_type": "STOCK",
        "total_market_val": "5000000000",
        "prev_close_price": "25",
        "update_time": "2026-10-20 16:00:00",
    }
    row.update(changes)
    return row


def test_exact_match_and_provenance(tmp_path):
    path = write_snapshot(tmp_path, [stock_row()])
    result = read_csv_snapshot("example", path)

    assert result["found"] is True
    assert result["moomoo_code"] == "US.EXAMPLE"
    assert result["is_live"] is False
    assert result["provider_currency"] is None
    assert result["market_cap_raw"] == 5000000000
    assert result["previous_close_raw"] == 25
    assert len(result["dataset_sha256"]) == 64
    assert result["error"] is None


def test_missing_ticker_has_no_fallback(tmp_path):
    path = write_snapshot(tmp_path, [stock_row()])
    result = read_csv_snapshot("MISSING", path)

    assert result["found"] is False
    assert "not found in this dataset" in result["error"]
    assert result["company_name"] is None


def test_duplicates_are_rejected(tmp_path):
    path = write_snapshot(tmp_path, [stock_row(), stock_row()])
    result = read_csv_snapshot("EXAMPLE", path)

    assert result["found"] is False
    assert "Multiple rows" in result["error"]


def test_invalid_numbers_remain_unknown(tmp_path):
    path = write_snapshot(
        tmp_path,
        [stock_row(total_market_val="nan", prev_close_price="-1")],
    )
    result = read_csv_snapshot("EXAMPLE", path)

    assert result["found"] is True
    assert result["market_cap_raw"] is None
    assert result["previous_close_raw"] is None


def test_non_stock_is_rejected(tmp_path):
    path = write_snapshot(tmp_path, [stock_row(stock_type="ETF")])
    result = read_csv_snapshot("EXAMPLE", path)

    assert result["found"] is False
    assert result["error"] is not None


def test_missing_file_returns_error(tmp_path):
    result = read_csv_snapshot("EXAMPLE", tmp_path / "absent.csv")

    assert result["found"] is False
    assert result["error"] is not None