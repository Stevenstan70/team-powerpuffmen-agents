"""Build the searchable company directory from Moomoo OpenD.

Runs in its own process, like api/worker.py:
    python -m api.directory OUTPUT_JSON_PATH

Writes only fields the provider returns: code, name, and listing date and
exchange type when present. Nothing is added or inferred.
"""
import json
import sys


def build_directory():
    import moomoo as mm
    import pandas as pd

    ctx = mm.OpenQuoteContext(host="127.0.0.1", port=11111)
    try:
        ret, basic = ctx.get_stock_basicinfo(mm.Market.US, stock_type=mm.SecurityType.STOCK)
    finally:
        ctx.close()
    if ret != mm.RET_OK:
        raise RuntimeError(f"Company directory request failed: {basic}")
    if not {"code", "name", "stock_type"}.issubset(basic.columns):
        raise ValueError("Unexpected company-information schema.")
    rows = basic[basic["stock_type"].astype(str).str.upper().eq("STOCK")]
    optional = [c for c in ("exchange_type", "listing_date", "delisting") if c in rows.columns]
    out = []
    for _, r in rows.iterrows():
        if pd.isna(r["name"]) or not str(r["code"]).startswith("US."):
            continue
        if "delisting" in optional and bool(r["delisting"]):
            continue
        item = {"code": str(r["code"]), "ticker": str(r["code"])[3:], "name": str(r["name"])}
        for c in ("exchange_type", "listing_date"):
            if c in optional and not pd.isna(r[c]) and str(r[c]).strip() not in ("", "N/A"):
                item[c] = str(r[c])
        out.append(item)
    return out


def main(argv):
    out_path = argv[1]
    try:
        payload = {"ok": True, "companies": build_directory()}
    except Exception as exc:  # reported to the API, never replaced with a sample list
        payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)


if __name__ == "__main__":
    main(sys.argv)
