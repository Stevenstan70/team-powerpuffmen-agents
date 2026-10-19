import sys
from importlib.metadata import version, PackageNotFoundError

try:
    import moomoo as ft
except ImportError:
    print("FAIL: moomoo is not installed in this Python environment.")
    print("Python:", sys.executable)
    sys.exit(1)

HOST = "127.0.0.1"
PORT = 11111
SYMBOLS = ["US.AAPL", "US.MSFT"]

print("Python:", sys.executable)

try:
    print("moomoo-api version:", version("moomoo-api"))
except PackageNotFoundError:
    print("moomoo-api version: unavailable")

print("\n=== SDK SCREENING FIELDS ===")
for enum_name in ("StockField", "FinancialField"):
    enum = getattr(ft, enum_name, None)
    if enum is None:
        print(f"{enum_name}: not exposed by this SDK")
        continue

    fields = [
        name for name in dir(enum)
        if name.isupper() and not name.startswith("_")
    ]
    print(f"{enum_name}:")
    print(", ".join(fields))

ctx = None

try:
    print(f"\n=== CONNECTING TO OPEND: {HOST}:{PORT} ===")
    ctx = ft.OpenQuoteContext(host=HOST, port=PORT)

    print("\n=== TEST 1: STOCK BASIC INFORMATION ===")
    ret, data = ctx.get_stock_basicinfo(
        market=ft.Market.US,
        stock_type=ft.SecurityType.STOCK,
        code_list=SYMBOLS,
    )

    if ret == ft.RET_OK:
        print("PASS")
        columns = [
            col for col in ("code", "name", "stock_type")
            if col in data.columns
        ]
        print(data[columns].to_string(index=False))
    else:
        print("FAIL:", data)

    print("\n=== TEST 2: MARKET SNAPSHOT ===")
    ret, data = ctx.get_market_snapshot(SYMBOLS)

    if ret == ft.RET_OK:
        print("PASS")
        print("Returned columns:")
        print(", ".join(data.columns))

        preferred = [
            "code", "name", "update_time",
            "last_price", "prev_close_price",
            "market_cap", "total_market_val",
            "pe_ratio", "turnover_rate", "volume",
        ]
        columns = [col for col in preferred if col in data.columns]
        print("\nSelected values:")
        print(data[columns].to_string(index=False))
    else:
        print("FAIL:", data)

except Exception as exc:
    print(f"\nERROR: {type(exc).__name__}: {exc}")

finally:
    if ctx is not None:
        ctx.close() 