"""Local HTTP API for the InvestIQ web UI.

Thin wrapper over the existing, tested Python functions. It never substitutes
sample data after a failure: any error is returned to the caller as an error.

Each lookup runs in its own worker process (api/worker.py) with a timeout, so a
crash or hang in the Moomoo SDK cannot take this server down.

Run from the project root with the project's interpreter:
    python -m uvicorn api.server:app --host 127.0.0.1 --port 8000

It binds to localhost only and talks to the local Moomoo OpenD gateway through
frontend.real_screen. Secrets stay in the server environment.
"""
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
WORKER_TIMEOUT_SECONDS = 90

logger = logging.getLogger("investiq.api")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    file_handler = logging.FileHandler(ROOT / "api_errors.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)

app = FastAPI(title="InvestIQ local API", docs_url=None, redoc_url=None)

# One OpenD request at a time; the gateway is a single local process.
_opend_lock = threading.Lock()

# Recent research results, so the agent analyses exactly the evidence the user
# saw rather than anything the browser sends back. In memory only; lost on restart.
_MAX_STORED = 20
_results = OrderedDict()
_results_lock = threading.Lock()


def _store(result):
    research_id = uuid.uuid4().hex
    with _results_lock:
        _results[research_id] = result
        while len(_results) > _MAX_STORED:
            _results.popitem(last=False)
    return research_id


class ResearchRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    include_statement_profit: bool = False


def _worker_command(ticker, include_statement_profit, out_path):
    return [
        sys.executable, "-m", "api.worker",
        ticker, "1" if include_statement_profit else "0", str(out_path),
    ]


def _run_worker(ticker, include_statement_profit):
    """Run one lookup in a child process; return its outcome dict.

    Raises HTTPException for a crashed or timed-out worker.
    """
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "outcome.json"
        try:
            proc = subprocess.run(
                _worker_command(ticker, include_statement_profit, out_path),
                cwd=ROOT, capture_output=True, text=True,
                timeout=WORKER_TIMEOUT_SECONDS,
                # This API is local-only and talks to the local OpenD gateway,
                # which is what the chart guard flag exists to confirm.
                env={**os.environ, "ENABLE_MOOMOO_CHART": "1"},
            )
        except subprocess.TimeoutExpired:
            logger.error("Lookup for %s timed out after %ss", ticker, WORKER_TIMEOUT_SECONDS)
            raise HTTPException(
                status_code=504,
                detail=(
                    f"The lookup timed out after {WORKER_TIMEOUT_SECONDS} seconds. "
                    "Moomoo OpenD may be unresponsive or logged out."
                ),
            )
        if not out_path.exists():
            tail = (proc.stderr or proc.stdout or "").strip()[-600:]
            logger.error(
                "Worker for %s exited with code %s and no result:\n%s",
                ticker, proc.returncode, proc.stderr,
            )
            raise HTTPException(
                status_code=502,
                detail=(
                    f"The lookup process stopped unexpectedly (exit code "
                    f"{proc.returncode}). {tail}"
                ).strip(),
            )
        return json.loads(out_path.read_text(encoding="utf-8"))


@app.get("/api/health")
def health():
    # Reports that this API process is up. It does not test OpenD.
    return {"status": "ok", "opend_checked": False}


@app.post("/api/research")
def research(req: ResearchRequest):
    """Real ticker -> evidence, screen result, warnings and preliminary brief."""
    started = time.monotonic()
    with _opend_lock:
        outcome = _run_worker(req.ticker, req.include_statement_profit)

    if not outcome.get("ok"):
        kind = outcome.get("kind")
        logger.warning("Lookup for %s failed (%s): %s",
                       req.ticker, kind, outcome.get("error"))
        status = {"validation": 422, "dependency": 503}.get(kind, 502)
        raise HTTPException(status_code=status, detail=outcome.get("error"))

    result = outcome["result"]
    research_id = _store(result)
    return {
        **result,
        "research_id": research_id,
        "brief_markdown": outcome["brief"],
        "server_elapsed_seconds": round(time.monotonic() - started, 2),
    }


@app.post("/api/research/{research_id}/agent")
def research_agent(research_id: str):
    """Send one stored research result to the IBM Orchestrate agent.

    Only runs on an explicit request. Sends the validated evidence summary
    (returned in the response as evidence_sent) to the configured agent.
    """
    from frontend.agent_research import analyse_research

    with _results_lock:
        result = _results.get(research_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="That research result is no longer available. Run the lookup again.",
        )
    started = time.monotonic()
    outcome = analyse_research(result)
    if not outcome["connected"]:
        logger.warning("Agent analysis failed (%s): %s", outcome["kind"], outcome["error"])
        status = {"config": 503, "input": 422}.get(outcome["kind"], 502)
        raise HTTPException(status_code=status, detail=outcome["error"])
    return {**outcome, "elapsed_seconds": round(time.monotonic() - started, 2)}


# The four synthetic scenarios from the original demo (app.py), evaluated by the
# same policy-v2 function. Fictional inputs, labelled synthetic; no OpenD involved.
_SCENARIO_BASE = {"market_cap_usd": 8_000_000_000, "close_price_usd": 45.20,
                  "net_profit_usd": 620_000_000, "snapshot_volume_shares": 100_000}
_SCENARIOS = [
    ("ACME", "Synthetic All-Pass Company", {}, None),
    ("BLUE", "Synthetic Negative-Profit Company", {"net_profit_usd": -1_000_000}, None),
    ("CRST", "Synthetic Missing-Profit Company", {"net_profit_usd": None}, None),
    ("SMCHG", "Synthetic Monitoring Company", {}, {"net_profit_usd": -1_000_000}),
]


@app.get("/api/scenarios")
def scenarios():
    from frontend.snapshot_adapter import evaluate_snapshot

    out = []
    for ticker, name, overrides, later in _SCENARIOS:
        inputs = {**_SCENARIO_BASE, **overrides}
        evaluation = evaluate_snapshot(ticker, inputs, source_mode="demo", company_name=name)
        item = {"ticker": ticker, "name": name, "evaluation": evaluation}
        if later is not None:
            # Monitoring: a later check of the same company finds changed data.
            updated = evaluate_snapshot(ticker, {**inputs, **later},
                                        source_mode="demo", company_name=name)
            before = {c["id"]: c for c in evaluation["criteria"]}
            item["updated"] = updated
            item["changes"] = [
                {"label": c["label"], "old_value": before[c["id"]]["observed_fmt"],
                 "new_value": c["observed_fmt"], "old_status": before[c["id"]]["status"],
                 "new_status": c["status"]}
                for c in updated["criteria"]
                if c["status"] != before[c["id"]]["status"]
                or c["observed_value"] != before[c["id"]]["observed_value"]
            ]
        out.append(item)
    return out
