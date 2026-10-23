import type { Criterion, RuleStatus } from "./api";
import type { SavedCompany, Workspace } from "./workspace";

const LABEL: Record<RuleStatus, string> = {
  pass: "PASS",
  fail: "FAIL",
  unknown: "UNVERIFIED",
};

// The four policy-v2 checks, in policy order.
const CHECKS: { id: string; head: string }[] = [
  { id: "market_cap_range", head: "Market cap" },
  { id: "min_close_price", head: "Previous close" },
  { id: "positive_net_profit", head: "Net profit" },
  { id: "min_snapshot_volume", head: "Snapshot volume" },
];

function Check({ c }: { c: Criterion | undefined }) {
  if (!c) return <span className="count">Not returned</span>;
  return (
    <>
      <span className={`badge state-${LABEL[c.status]}`}>{LABEL[c.status]}</span>
      <small>{c.status === "unknown" ? "withheld / unavailable" : c.observed_fmt}</small>
    </>
  );
}

function when(iso: string) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export default function CompareTable({
  ws,
  companies,
  onOpen,
}: {
  ws: Workspace;
  companies: SavedCompany[];
  onOpen: (code: string) => void;
}) {
  return (
    <div className="table-wrap">
      <table className="compare">
        <thead>
          <tr>
            <th>COMPANY</th>
            {CHECKS.map((c) => (
              <th key={c.id}>{c.head.toUpperCase()}</th>
            ))}
            <th>OVERALL</th>
            <th>PRICE TREND</th>
            <th>EVIDENCE</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {companies.map((co) => {
            const s = ws.screens[co.code];
            const r = s?.state === "done" ? s.result : null;
            const byId = (id: string) => r?.evaluation.criteria.find((c) => c.id === id);
            return (
              <tr key={co.code}>
                <td>
                  <b>{co.ticker}</b>
                  <small>{co.name}</small>
                </td>
                {!s ? (
                  <td colSpan={7} className="count">
                    Not screened yet
                  </td>
                ) : s.state === "running" ? (
                  <td colSpan={7} className="count">
                    Screening…
                  </td>
                ) : s.state === "error" ? (
                  <td colSpan={7}>
                    <span className="badge state-FAIL">ERROR</span>
                    <small>{s.message} Nothing was substituted.</small>
                  </td>
                ) : (
                  <>
                    {CHECKS.map((c) => (
                      <td key={c.id}>
                        <Check c={byId(c.id)} />
                      </td>
                    ))}
                    <td>
                      <span className={`badge state-${LABEL[r!.evaluation.aggregate_status]} strong`}>
                        {LABEL[r!.evaluation.aggregate_status]}
                      </span>
                    </td>
                    <td>
                      <span className={`badge state-${r!.trend?.trend_check_status ?? "UNVERIFIED"}`}>
                        {r!.trend?.trend_check_status ?? "UNVERIFIED"}
                      </span>
                      <small>separate price check</small>
                    </td>
                    <td>
                      <small>Provider snapshot: {r!.evaluation.data_timestamp ?? "unavailable"}</small>
                      <small>Screened: {when(s.at)}</small>
                    </td>
                  </>
                )}
                <td className="row-actions">
                  <button className="button" type="button" onClick={() => onOpen(co.code)}>
                    Research →
                  </button>
                  <button
                    className="text-button"
                    type="button"
                    disabled={s?.state === "running"}
                    onClick={() => ws.screen([co])}
                  >
                    {s ? "Refresh" : "Screen"}
                  </button>
                  <button
                    className="text-button danger"
                    type="button"
                    disabled={s?.state === "running"}
                    onClick={() => ws.remove(co.code)}
                    aria-label={`Remove ${co.ticker} from saved companies`}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
