import type { ResearchResult } from "./api";
import PriceChart from "./PriceChart";

const num = (v: number | null, digits = 2) =>
  v == null ? "Unavailable" : v.toLocaleString("en-US", { maximumFractionDigits: digits });

export default function TechnicalCard({ result }: { result: ResearchResult }) {
  const t = result.technicals;
  if (result.technicals_status !== "computed" || !t) {
    return (
      <section className="card">
        <div className="eyebrow">TECHNICAL MEASURES</div>
        <h2>Price history unavailable</h2>
        <p className="fineprint">
          Daily candles could not be retrieved, so no technical indicator is
          shown or estimated. See the recovery note above.
        </p>
      </section>
    );
  }
  const trend = result.trend;
  const rows: [string, string][] = [
    ["Last close", `${num(t.last_close)} (${t.last_date})`],
    ["50 / 150 / 200-session average", `${num(t.sma_50)} / ${num(t.sma_150)} / ${num(t.sma_200)}`],
    ["12-month (252-session) average", num(t.avg_close_12m)],
    ["52-week high / low", `${num(t.high_52w)} / ${num(t.low_52w)}`],
    ["Below 52-week high / above low", `${num(t.pct_below_52w_high)}% / ${num(t.pct_above_52w_low)}%`],
    ["50-session average volume", `${num(t.avg_volume_50d, 0)} shares`],
    ["Sessions used", `${t.sessions} (${t.first_date} to ${t.last_date})`],
  ];

  return (
    <section className="card">
      <div className="section-top">
        <div>
          <div className="eyebrow">TECHNICAL MEASURES</div>
          <h2>Price trend</h2>
        </div>
        {trend && (
          <span className={`badge state-${trend.trend_check_status}`}>
            {trend.trend_check_status}
          </span>
        )}
      </div>
      {!t.reliability.ok && (
        <div className="notice warn">
          <b>Averages withheld</b>
          <p>{t.reliability.reason}</p>
        </div>
      )}
      <PriceChart series={result.price_series} />
      <div className="table-wrap">
        <table>
          <tbody>
            {rows.map(([k, v]) => (
              <tr key={k}><td>{k}</td><td>{v}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      {trend && (
        <>
          <h3 className="sub">Trend check ({trend.criteria_version})</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Rule</th><th>Last close</th><th>Reference</th><th>Status</th></tr>
              </thead>
              <tbody>
                {trend.rules.map((r) => (
                  <tr key={r.rule_name}>
                    <td>{r.threshold}</td>
                    <td>{num(r.observed_value)}</td>
                    <td>{num(r.reference_value)}</td>
                    <td><span className={`badge state-${r.status}`}>{r.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="fineprint">{trend.scope_note}</p>
        </>
      )}
      <p className="fineprint">{t.price_basis}. Request-time evidence, not a streaming feed.</p>
    </section>
  );
}
