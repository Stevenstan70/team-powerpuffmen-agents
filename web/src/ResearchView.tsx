import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import AgentCard from "./AgentCard";
import PriceChart from "./PriceChart";
import TechnicalCard from "./TechnicalCard";
import { ApiError, runResearch, type ResearchResult, type RuleStatus } from "./api";

const LABEL: Record<RuleStatus, string> = {
  pass: "PASS",
  fail: "FAIL",
  unknown: "UNVERIFIED",
};

type Phase =
  | { name: "idle" }
  | { name: "loading" }
  | { name: "error"; message: string }
  | { name: "done"; result: ResearchResult; clientSeconds: number };

function download(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ResearchView({
  initialTicker = "AAPL",
  initialResult,
}: {
  initialTicker?: string;
  // A result the Screener already retrieved, so opening a row needs no new lookup.
  initialResult?: ResearchResult;
}) {
  const [ticker, setTicker] = useState(initialTicker);
  const [statements, setStatements] = useState(false);
  const [phase, setPhase] = useState<Phase>(
    initialResult
      ? { name: "done", result: initialResult, clientSeconds: initialResult.server_elapsed_seconds }
      : { name: "idle" },
  );
  const [elapsed, setElapsed] = useState(0);
  const abort = useRef<AbortController | null>(null);

  // Live stopwatch while a request is running.
  useEffect(() => {
    if (phase.name !== "loading") return;
    const start = performance.now();
    setElapsed(0);
    const id = setInterval(
      () => setElapsed((performance.now() - start) / 1000),
      200,
    );
    return () => clearInterval(id);
  }, [phase.name]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    const started = performance.now();
    setPhase({ name: "loading" });
    try {
      const result = await runResearch(ticker, statements, controller.signal);
      setPhase({
        name: "done",
        result,
        clientSeconds: (performance.now() - started) / 1000,
      });
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setPhase({
        name: "error",
        message:
          err instanceof ApiError
            ? err.message
            : "Unexpected error: " + (err as Error).message,
      });
    }
  }

  const loading = phase.name === "loading";

  return (
    <>
      <section className="card">
        <div className="eyebrow">COMPANY RESEARCH</div>
        <h2>Research one real US company</h2>
        <p className="fineprint">
          Retrieves evidence from your local Moomoo OpenD gateway, applies the
          four-rule snapshot policy, and assembles a preliminary brief. Missing
          inputs stay unverified.
        </p>
        <form className="research-form" onSubmit={submit}>
          <label>
            <span>US ticker</span>
            <input
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              maxLength={10}
              spellCheck={false}
              aria-label="US ticker"
            />
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={statements}
              onChange={(e) => setStatements(e.target.checked)}
            />
            <span>
              Include statement-reported USD net profit
              <small style={{ display: "block", marginTop: 4 }}>
                Most recent report in the provider response; not inferred as
                annual or TTM. If it fails validation the screen continues
                without it.
              </small>
            </span>
          </label>
          <button
            className="button primary"
            type="submit"
            disabled={loading || ticker.trim() === ""}
          >
            {loading ? `Retrieving… ${elapsed.toFixed(1)} s` : "Retrieve and build brief"}
          </button>
        </form>
      </section>

      {phase.name === "error" && (
        <div className="notice error" role="alert">
          <b>Could not complete this research request</b>
          <p>{phase.message}</p>
          <p>No sample data was substituted.</p>
        </div>
      )}

      {phase.name === "done" && <Result phase={phase} />}
    </>
  );
}

function Result({
  phase,
}: {
  phase: Extract<Phase, { name: "done" }>;
}) {
  const { result, clientSeconds } = phase;
  const e = result.evaluation;
  const withProvenance = e.criteria.filter((c) => c.provenance);

  return (
    <>
      <QuickTake result={result} />
      <AgentCard key={result.research_id} researchId={result.research_id} />
      <details className="deep-dive">
        <summary>How this was checked: every rule, raw data and the full brief</summary>
      <section className="card">
        <div className="section-top">
          <div>
            <div className="eyebrow">RESULT</div>
            <h2>
              {e.company_name ?? "Unnamed company"} ({result.code})
            </h2>
          </div>
          <span className={`badge state-${LABEL[e.aggregate_status]}`}>
            {LABEL[e.aggregate_status]}
          </span>
        </div>
        <div className="notice warn">
          <b>Incomplete screen</b>
          <p>
            Market capitalisation and previous close are withheld because their
            USD mapping is unverified, so this is not a complete eligibility
            decision.
          </p>
        </div>
        <p className="fineprint">
          Provider snapshot: {e.data_timestamp ?? "unavailable"} (provider
          timestamp; timezone not independently verified). Retrieved at{" "}
          {result.fetched_at}. Request-time evidence, not a streaming feed.
        </p>
        <p className="fineprint timing">
          Task time: {clientSeconds.toFixed(1)} s measured in this browser (
          {result.server_elapsed_seconds.toFixed(1)} s in the API). This is
          machine time for one lookup, not a measured saving versus manual
          research.
        </p>

        {result.warnings.map((w, i) => (
          <div className="notice warn" key={i}>
            <b>Recovery: {w.stage.replace("_", " ")}</b>
            <p>
              {w.message} ({w.error_type})
            </p>
          </div>
        ))}

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Rule</th>
                <th>Observed</th>
                <th>Threshold</th>
                <th>Status</th>
                <th>Period</th>
                <th>Why</th>
              </tr>
            </thead>
            <tbody>
              {e.criteria.map((c) => (
                <tr key={c.label}>
                  <td>{c.label}</td>
                  <td>{c.observed_fmt}</td>
                  <td>{String(c.threshold)}</td>
                  <td>
                    <span className={`badge state-${LABEL[c.status]}`}>
                      {LABEL[c.status]}
                    </span>
                  </td>
                  <td>{c.reporting_period}</td>
                  <td className="wrap">{c.explanation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="fineprint">Policy {e.criteria_version}. {e.scope_note}</p>
      </section>

      <TechnicalCard result={result} />

      <section className="card">
        <div className="eyebrow">EVIDENCE</div>
        <h2>Raw provider observations</h2>
        <p className="fineprint">
          These are not automatically verified screening inputs.
        </p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Provider field</th>
                <th>Raw value</th>
                <th>Use</th>
              </tr>
            </thead>
            <tbody>
              {result.raw.map((r) => (
                <tr key={r["Provider field"]}>
                  <td>{r["Provider field"]}</td>
                  <td>{r["Raw value"]}</td>
                  <td className="wrap">{r.Use}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {withProvenance.map((c) => (
          <details key={c.label} className="provenance">
            <summary>Statement provenance: {c.label}</summary>
            <pre>{JSON.stringify(c.provenance, null, 2)}</pre>
          </details>
        ))}
      </section>

      <section className="card">
        <div className="section-top">
          <div>
            <div className="eyebrow">PRELIMINARY BRIEF</div>
            <h2>Research brief</h2>
          </div>
          <button
            className="button"
            onClick={() =>
              download(
                `InvestIQ_${e.ticker}_research_brief.md`,
                result.brief_markdown,
              )
            }
          >
            Download brief
          </button>
        </div>
        <p className="fineprint">
          Deterministic evidence report assembled by the application. Not
          agent-generated analysis. News review and scenario-change approval
          are not included yet.
        </p>
        <article className="brief">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {result.brief_markdown}
          </ReactMarkdown>
        </article>
      </section>
      </details>
    </>
  );
}

const AVG_NAME: Record<string, string> = {
  above_12m_average: "12-month",
  above_sma_200: "200-day",
  above_sma_150: "150-day",
};

// The plain-language answer first. Detail stays in "How this was checked".
function QuickTake({ result }: { result: ResearchResult }) {
  const e = result.evaluation;
  const t = result.technicals;
  const vol = e.criteria.find((c) => c.id === "min_snapshot_volume");
  const trend = result.trend;
  const below = (trend?.rules ?? []).filter((r) => r.status === "FAIL").map((r) => AVG_NAME[r.rule_name] ?? r.rule_name);

  const trendRow =
    trend?.trend_check_status === "PASS"
      ? { s: "PASS", head: "Uptrend", text: "Price is above its 12-month, 150-day and 200-day averages." }
      : trend?.trend_check_status === "FAIL"
        ? { s: "FAIL", head: "Weak trend", text: `Price is below its ${below.join(" and ")} average${below.length > 1 ? "s" : ""}.` }
        : { s: "UNVERIFIED", head: "Can't tell", text: t?.reliability.reason ?? "Not enough reliable price history." };
  const volRow =
    vol?.status === "pass"
      ? { s: "PASS", head: "Actively traded", text: `${vol.observed_fmt} traded in the latest snapshot.` }
      : vol?.status === "fail"
        ? { s: "FAIL", head: "Thinly traded", text: `Only ${vol.observed_fmt} in the latest snapshot.` }
        : { s: "UNVERIFIED", head: "Volume unknown", text: "Trading volume was not available." };
  const profit = e.criteria.find((c) => c.id === "positive_net_profit");
  const profitKnown = profit && profit.status !== "unknown";
  const fundRow = {
    s: "UNVERIFIED",
    head: "Fundamentals not verified",
    text: profitKnown
      ? `Profit ${profit.status === "pass" ? "is positive" : "is not positive"}; company size and price in USD still need checking.`
      : "Company size, price and profit could not be verified in USD. Check them before deciding.",
  };
  const passed = [trendRow, volRow].filter((r) => r.s === "PASS").length;

  return (
    <section className="card quick">
      <div className="section-top">
        <div>
          <div className="eyebrow">{e.ticker}</div>
          <h2>{e.company_name ?? "Unnamed company"}</h2>
        </div>
        {t?.last_close != null && (
          <div className="price">
            <b>{t.last_close.toLocaleString()}</b>
            <small>last close · {t.last_date}</small>
          </div>
        )}
      </div>
      <p className="lead">
        {passed === 2
          ? "Passes every check we could verify. Worth a closer look; fundamentals still need checking."
          : passed === 0
            ? "Does not pass the checks we could verify."
            : "Mixed: passes one of the two checks we could verify."}
      </p>
      <div className="verdicts">
        {[trendRow, volRow, fundRow].map((r) => (
          <div className="verdict" key={r.head}>
            <span className={`badge state-${r.s}`}>{r.s}</span>
            <div>
              <b>{r.head}</b>
              <p>{r.text}</p>
            </div>
          </div>
        ))}
      </div>
      {result.warnings.length > 0 && (
        <p className="fineprint">
          Some optional data could not be used ({result.warnings.map((w) => w.stage.replace("_", " ")).join(", ")}).
          Nothing was substituted.
        </p>
      )}
      {result.price_series.length > 1 && <PriceChart series={result.price_series} />}
      <p className="fineprint">Screening aid only, not investment advice.</p>
    </section>
  );
}
