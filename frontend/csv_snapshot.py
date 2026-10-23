"""Read an exact security observation from a saved Moomoo CSV.

No network calls, screening, currency conversion, or demo fallback.
"""

from __future__ import annotations

import csv
import hashlib
import io
import math
from pathlib import Path


DEFAULT_CSV = (
    Path(__file__).resolve().parent.parent
    / "local_data"
    / "us_market_full.csv"
)

REQUIRED_COLUMNS = {
    "code",
    "name",
    "total_market_val",
    "prev_close_price",
    "update_time",
}


def _text(value):
    text = str(value or "").strip()
    return None if text.lower() in {"", "nan", "none", "nat", "<na>"} else text


def _positive_number(value):
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError, OverflowError):
        return None

    return number if math.isfinite(number) and number > 0 else None


def read_csv_snapshot(ticker, path=None):
    """Return one exact CSV match, with provenance and raw source fields."""
    result = {
        "found": False,
        "source": "moomoo_csv",
        "is_live": False,
        "source_file": None,
        "dataset_sha256": None,
        "moomoo_code": None,
        "company_name": None,
        "data_timestamp": None,
        "provider_currency": None,
        "market_cap_raw": None,
        "previous_close_raw": None,
        "error": None,
    }

    if not isinstance(ticker, str):
        result["error"] = "Ticker must be text."
        return result

    symbol = ticker.strip().upper()
    if symbol.startswith("US."):
        symbol = symbol[3:]

    if not symbol or any(char.isspace() for char in symbol):
        result["error"] = "Enter one exact US ticker."
        return result

    code = f"US.{symbol}"
    result["moomoo_code"] = code
    source_path = Path(path) if path is not None else DEFAULT_CSV
    result["source_file"] = source_path.name

    try:
        payload = source_path.read_bytes()
        result["dataset_sha256"] = hashlib.sha256(payload).hexdigest()

        reader = csv.DictReader(
            io.StringIO(payload.decode("utf-8-sig"), newline="")
        )
        columns = reader.fieldnames or []

        if len(columns) != len(set(columns)):
            raise ValueError("CSV contains duplicate column names.")

        missing = REQUIRED_COLUMNS - set(columns)
        if missing:
            raise ValueError(
                "CSV is missing required columns: "
                + ", ".join(sorted(missing))
            )

        matches = [
            row for row in reader
            if str(row.get("code", "")).strip().upper() == code
        ]

        if not matches:
            raise ValueError(f"{code} was not found in this dataset.")

        if len(matches) != 1:
            raise ValueError(f"Multiple rows match {code}; no row selected.")

        row = matches[0]
        security_type = _text(row.get("stock_type") or row.get("sec_type"))

        if security_type is None or security_type.upper() != "STOCK":
            raise ValueError(
                "The row does not explicitly identify a STOCK security."
            )

        name = _text(row.get("name"))
        if name is None:
            raise ValueError("The matching row has no company name.")

        result.update(
            found=True,
            company_name=name,
            data_timestamp=_text(row.get("update_time")),
            provider_currency=_text(row.get("currency")),
            market_cap_raw=_positive_number(row.get("total_market_val")),
            previous_close_raw=_positive_number(row.get("prev_close_price")),
        )

    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        result["error"] = f"CSV read failed: {exc}"

    return result