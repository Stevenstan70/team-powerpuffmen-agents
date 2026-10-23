import { useRef, useState } from "react";
import { ApiError, runResearch, type ResearchResult, type RuleStatus } from "./api";

// Editable starting universe. Plain US common stocks only; ETFs, ADRs and
// class shares are rejected by the lookup by design.
const DEFAULT_UNIVERSE =
  "AAPL, MSFT, NVDA, AMZN, META, TSLA, AMD, MU, INTC, NFLX, ORCL, CRM";

const LABEL: Record<RuleStatus, string> = {
  pass: "PASS",
  fail: "FAIL",
  unknown: "UNVERIFIED",
};

type Row =
  | { ticker: string; state: "queued" | "running" }
  | { ticker: string; state: "error"; message: string }
  | { ticker: string; state: "done"; result: ResearchResult };

type Filter = "All" | "Meets checkable rules" | "Fails a rule" | "Errors";
const FILTERS: Filter[] = ["All", "Meets checkable rules", "Fails a rule", "Errors"];

function volumeRule(r: ResearchResult) {
  return r.evaluation.criteria.find((c) => c.id === "min_snapshot_volume");
}

// Only rules that can be checked with validated data: snapshot volume and the
// price-trend check. Market cap, previous close and profit stay UNVERIFIED.
function meetsCheckable(r: ResearchResult) {
  return volumeRule(r)?.status === "pass" && r.trend?.trend_check_status === "PASS";
}

function failsOne(r: ResearchResult) {
  return volumeRule(r)?.status === "fail" || r.trend?.trend_check_status === "FAIL";
}

function pct(value: number | null | undefined, ref: number | null | undefined) {
  if (value == null || ref == null || ref === 0) return "Unavailable";
  const p = ((value - ref) / ref) * 100;
  const shown = p.toFixed(1);
  if (Number(shown) === 0) return "0.0%";
  return `${p > 0 ? "+" : ""}${shown}%`;
}

const RULE_TEXT: Record<string, string> = {
  above_12m_average: "12-month avg",
  above_sma_200: "200-day avg",
  above_sma_150: "150-day avg",
};

// Names the trend rules that did not pass, so a FAIL is never unexplained.
function trendDetail(r: ResearchResult) {
  const notPassing = (r.trend?.rules ?? []).filter((x) => x.status !== "PASS");
  if (!r.trend) return "Unavailable";
  if (notPassing.length === 0) return "above all 3 averages";
  if (notPassing.every((x) => x.status === "UNVERIFIED")) {
    return r.technicals?.reliability.ok === false
      ? "averages withheld: price data check failed"
      : "averages unavailable";
  }
  return notPassing
    .map((x) => `${x.status === "FAIL" ? "below" : "no data:"} ${RULE_TEXT[x.rule_name] ?? x.rule_name}`)
    .join(", ");
}

function parseTickers(text: string) {
  return Array.from(
    new Set(
      text
        .split(/[\s,]+/)
        .map((t) => t.trim().toUpperCase())
        .filter(Boolean),
    ),
  );
}

export default function ScreenerView({
  onOpen,
}: {
  onOpen: (result: ResearchResult) => void;
}) {
  const [universe, setUniverse] = useState(DEFAULT_UNIVERSE);
  const [rows, setRows] = useState<Row[]>([]);
  const [filter, setFilter] = useState<Filter>("All");
  const [running, setRunning] = useState(false);
  const abort = useRef<AbortController | null>(null);

  function update(ticker: string, row: Row) {
    setRows((prev) => prev.map((r) => (r.ticker === ticker ? row : r)));
  }

  async function run(event: React.FormEvent) {
    event.preventDefault();
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    const tickers = parseTickers(universe);
    setRows(tickers.map((ticker) => ({ ticker, state: "queued" })));
    setRunning(true);
    // One at a time: the local OpenD gateway serves one lookup at a time.
    for (const ticker of tickers) {
      if (controller.signal.aborted) break;
      update(ticker, { ticker, state: "running" });
      try {
        const result = await runResearch(ticker, false, controller.signal);
        update(ticker, { ticker, state: "done", result });
      } catch (err) {
        if ((err as Error).name === "AbortError") break;
        update(ticker, {
          ticker,
          state: "error",
          message: err instanceof ApiError ? err.message : (err as Error).message,
        });
      }
    }
    setRunning(false);
  }

  function stop() {
    abort.current?.abort();
    setRunning(false);
    setRows((prev) => prev.filter((r) => r.state === "done" || r.state === "error"));
  }

  const done = rows.filter((r) => r.state === "done") as Extract<Row, { state: "done" }>[];
  const visible = rows.filter((r) => {
    if (filter === "All") return true;
    if (filter === "Errors") return r.state === "error";
    if (r.state !== "done") return false;
    return filter === "Meets checkable rules" ? meetsCheckable(r.result) : failsOne(r.result);
  });

  return (
    <>
      <section className="card">
        <div className="eyebrow">SCREENER</div>
        <h2>Screen a list of real US companies</h2>
        <form className="research-form" onSubmit={run}>
          <label>
            Tickers (comma or space separated)
            <input
              style={{ width: "min(560px, 80vw)", letterSpacing: 0 }}
              value={universe}
              onChange={(e) => setUniverse(e.target.value)}
              disabled={running}
            />
          </label>
          <button className="button primary" type="submit" disabled={running}>
            {running ? "Screening…" : "Run screen"}
          </button>
          {running && (
            <button className="button" type="button" onClick={stop}>
              Stop
            </button>
          )}
        </form>
        <p className="fineprint">
          Each company is looked up live from your local Moomoo OpenD, one at a
          time (about 7 seconds each). "Meets checkable rules" means snapshot
          volume ≥ 100,000 shares and all three price-trend rules pass. Market
          cap, previous close and net profit are withheld as unverified, so no
          company is shown as fully passing the screen.
        </p>
      </section>

      {rows.length > 0 && (
        <section className="card">
          <div className="filters">
            <div className="tabs">
              {FILTERS.map((f) => (
                <button
                  key={f}
                  type="button"
                  className={filter === f ? "selected" : ""}
                  onClick={() => setFilter(f)}
                >
                  {f}
                </button>
              ))}
            </div>
            <span className="count">
              {done.filter((r) => meetsCheckable(r.result)).length} of {rows.length} meet
              checkable rules · {done.length} of {rows.length} looked up
            </span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>COMPANY</th>
                  <th>SNAPSHOT VOLUME</th>
                  <th>PRICE TREND</th>
                  <th>LAST CLOSE</th>
                  <th>VS 200-DAY AVG</th>
                  <th>FROM 52W HIGH</th>
                  <th>FUNDAMENTALS</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => {
                  if (row.state !== "done") {
                    return (
                      <tr key={row.ticker}>
                        <td>
                          <b>{row.ticker}</b>
                        </td>
                        <td colSpan={7}>
                          {row.state === "error" ? (
                            <span className="badge state-FAIL">ERROR</span>
                          ) : (
                            <span className="count">
                              {row.state === "running" ? "Looking up…" : "Queued"}
                            </span>
                          )}
                          {row.state === "error" && <small>{row.message}</small>}
                        </td>
                      </tr>
                    );
                  }
                  const r = row.result;
                  const vol = volumeRule(r);
                  const t = r.technicals;
                  const trend = r.trend?.trend_check_status ?? "UNVERIFIED";
                  return (
                    <tr key={row.ticker}>
                      <td>
                        <b>{r.evaluation.ticker}</b>
                        <small>{r.evaluation.company_name ?? "Name unavailable"}</small>
                      </td>
                      <td>
                        <span className={`badge state-${LABEL[vol?.status ?? "unknown"]}`}>
                          {LABEL[vol?.status ?? "unknown"]}
                        </span>
                        <small>{vol?.observed_fmt ?? "Unavailable"}</small>
                      </td>
                      <td>
                        <span className={`badge state-${trend}`}>{trend}</span>
                        <small>{trendDetail(r)}</small>
                      </td>
                      <td>{t?.last_close ?? "Unavailable"}</td>
                      <td>{pct(t?.last_close, t?.sma_200)}</td>
                      <td>{pct(t?.last_close, t?.high_52w)}</td>
                      <td>
                        <span className="badge state-UNVERIFIED">UNVERIFIED</span>
                        <small>cap, close, profit withheld</small>
                      </td>
                      <td>
                        <button
                          className="button"
                          type="button"
                          onClick={() => onOpen(r)}
                        >
                          Research →
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="fineprint">
            Prices are unadjusted provider-unit daily closes. This list screens
            for further research; it is not a recommendation.
          </p>
        </section>
      )}
    </>
  );
}
