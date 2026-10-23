import api.server as server
from fastapi.testclient import TestClient

DIRECTORY = [
    {"code": "US.NVDA", "ticker": "NVDA", "name": "NVIDIA", "exchange_type": "US_NASDAQ"},
    {"code": "US.NVDL", "ticker": "NVDL", "name": "Some Leveraged Fund"},
    {"code": "US.AAPL", "ticker": "AAPL", "name": "Apple", "exchange_type": "US_NASDAQ"},
    {"code": "US.APLE", "ticker": "APLE", "name": "Apple Hospitality REIT"},
    {"code": "US.MLAA", "ticker": "MLAA", "name": "Big Apple Corp"},
]


def client(monkeypatch, companies=DIRECTORY):
    monkeypatch.setitem(server._directory, "companies", companies)
    monkeypatch.setitem(server._directory, "built_at", "2026-10-23T13:00:00Z")
    return TestClient(server.app)


def test_exact_ticker_ranks_first(monkeypatch):
    body = client(monkeypatch).get("/api/companies", params={"q": "nvda"}).json()
    assert [c["ticker"] for c in body["results"]] == ["NVDA"]
    assert body["source"] == "Moomoo OpenD US stock list"
    assert body["directory_size"] == len(DIRECTORY)


def test_name_search_orders_by_match_quality(monkeypatch):
    body = client(monkeypatch).get("/api/companies", params={"q": "apple"}).json()
    assert [c["ticker"] for c in body["results"]] == ["AAPL", "APLE", "MLAA"]
    assert body["total_matches"] == 3


def test_empty_query_does_not_load_directory(monkeypatch):
    monkeypatch.setitem(server._directory, "companies", None)
    calls = []
    monkeypatch.setattr(server, "_build_directory", lambda: calls.append(1) or [])
    body = TestClient(server.app).get("/api/companies", params={"q": "  "}).json()
    assert body["results"] == [] and calls == []


def test_no_matches_is_empty_not_error(monkeypatch):
    r = client(monkeypatch).get("/api/companies", params={"q": "zzzz"})
    assert r.status_code == 200 and r.json()["results"] == []


def test_directory_failure_is_reported(monkeypatch):
    monkeypatch.setitem(server._directory, "companies", None)

    def fail():
        raise server.HTTPException(status_code=502, detail="The company list could not be loaded: down")

    monkeypatch.setattr(server, "_build_directory", fail)
    r = TestClient(server.app).get("/api/companies", params={"q": "nv"})
    assert r.status_code == 502 and "could not be loaded" in r.json()["detail"]


def test_placeholder_listing_date_is_dropped(monkeypatch, tmp_path):
    import json, subprocess

    def fake_run(cmd, **kw):
        out = cmd[-1]
        with open(out, "w", encoding="utf-8") as fh:
            json.dump({"ok": True, "companies": [
                {"code": "US.X", "ticker": "X", "name": "X Co", "listing_date": "1970-01-01"},
                {"code": "US.Y", "ticker": "Y", "name": "Y Co", "listing_date": "1999-01-22"},
            ]}, fh)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    rows = server._build_directory()
    assert "listing_date" not in rows[0] and rows[1]["listing_date"] == "1999-01-22"
