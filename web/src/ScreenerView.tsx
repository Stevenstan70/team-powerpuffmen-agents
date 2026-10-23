import CompanySearch from "./CompanySearch";
import CompareTable from "./CompareTable";
import type { Workspace } from "./workspace";

export function SavedCompaniesCard({
  ws,
  onOpen,
  title,
  emptyHint,
}: {
  ws: Workspace;
  onOpen: (code: string) => void;
  title: string;
  emptyHint: React.ReactNode;
}) {
  return (
    <section className="card">
      <div className="section-top">
        <div>
          <div className="eyebrow">SAVED COMPANIES · {ws.saved.length}</div>
          <h2>{title}</h2>
        </div>
        {ws.saved.length > 0 && (
          <div className="approval-actions">
            {ws.running ? (
              <button className="button" type="button" onClick={ws.stop}>
                Stop
              </button>
            ) : (
              <button className="button primary" type="button" onClick={() => ws.screen(ws.saved)}>
                Screen saved companies
              </button>
            )}
          </div>
        )}
      </div>
      {ws.saved.length === 0 ? (
        <div className="empty">
          <h3>No saved companies yet</h3>
          <p>{emptyHint}</p>
        </div>
      ) : (
        <>
          <CompareTable ws={ws} companies={ws.saved} onOpen={onOpen} />
          <p className="fineprint">
            Screening looks each company up live from your local Moomoo OpenD, one at a time
            (about 7 seconds each). Market cap and previous close are withheld until their USD
            mapping is verified, so the overall result for a real company is at best UNVERIFIED.
            Price trend is a separate check and is not part of the overall result.
          </p>
        </>
      )}
    </section>
  );
}

export default function ScreenerView({
  ws,
  onOpen,
}: {
  ws: Workspace;
  onOpen: (code: string) => void;
}) {
  return (
    <>
      <CompanySearch ws={ws} />
      <SavedCompaniesCard
        ws={ws}
        onOpen={onOpen}
        title="Compare saved companies"
        emptyHint="Search above, open a company and choose “Add to saved companies”."
      />
    </>
  );
}
