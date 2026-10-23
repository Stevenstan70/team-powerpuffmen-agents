import type { RuleStatus } from "./api";
import { SavedCompaniesCard } from "./ScreenerView";
import type { Workspace } from "./workspace";

export default function HomeView({
  ws,
  onOpen,
  go,
}: {
  ws: Workspace;
  onOpen: (code: string) => void;
  go: (route: string) => void;
}) {
  // Counts come only from screens actually run for saved companies.
  const counts: Record<RuleStatus, number> = { pass: 0, fail: 0, unknown: 0 };
  let screened = 0;
  for (const c of ws.saved) {
    const s = ws.screens[c.code];
    if (s?.state === "done") {
      counts[s.result.evaluation.aggregate_status] += 1;
      screened += 1;
    }
  }

  return (
    <>
      {ws.saved.length > 0 && (
        <div className="metrics">
          <div className="metric">
            <span>Saved companies</span>
            <strong>{ws.saved.length}</strong>
            <small>{screened} screened this session</small>
          </div>
          <div className="metric">
            <span>Overall PASS</span>
            <strong>{counts.pass}</strong>
            <small>all four checks passed</small>
          </div>
          <div className="metric">
            <span>Overall FAIL</span>
            <strong>{counts.fail}</strong>
            <small>at least one check failed</small>
          </div>
          <div className="metric">
            <span>UNVERIFIED</span>
            <strong>{counts.unknown}</strong>
            <small>no failure, but evidence missing</small>
          </div>
        </div>
      )}
      <SavedCompaniesCard
        ws={ws}
        onOpen={onOpen}
        title="Your saved companies"
        emptyHint={
          <>
            Find companies in the{" "}
            <button className="text-button inline" type="button" onClick={() => go("/screener")}>
              Screener
            </button>{" "}
            and save the ones you want to follow.
          </>
        }
      />
    </>
  );
}
