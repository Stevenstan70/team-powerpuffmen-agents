import { useEffect, useRef, useState } from "react";
import { ApiError, searchCompanies, type CompanyHit, type CompanySearch as SearchResult } from "./api";
import type { Workspace } from "./workspace";

type State =
  | { name: "idle" }
  | { name: "loading" }
  | { name: "error"; message: string }
  | { name: "done"; data: SearchResult };

const EXCHANGE: Record<string, string> = {
  US_NASDAQ: "NASDAQ",
  US_NYSE: "NYSE",
  US_AMEX: "NYSE American",
  US_PINK: "OTC Pink",
};

function exchange(hit: CompanyHit) {
  if (!hit.exchange_type) return null;
  return EXCHANGE[hit.exchange_type] ?? hit.exchange_type;
}

export default function CompanySearch({ ws }: { ws: Workspace }) {
  const [q, setQ] = useState("");
  const [state, setState] = useState<State>({ name: "idle" });
  const [selected, setSelected] = useState<CompanyHit | null>(null);
  const seq = useRef(0);

  // Debounced search; responses from older queries are ignored.
  useEffect(() => {
    const query = q.trim();
    if (!query) {
      setState({ name: "idle" });
      return;
    }
    const id = ++seq.current;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setState({ name: "loading" });
      searchCompanies(query, controller.signal)
        .then((data) => {
          if (id === seq.current) setState({ name: "done", data });
        })
        .catch((err) => {
          if ((err as Error).name === "AbortError" || id !== seq.current) return;
          setState({ name: "error", message: err instanceof ApiError ? err.message : (err as Error).message });
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [q]);

  const added = selected ? ws.isSaved(selected.code) : false;

  return (
    <section className="card">
      <div className="eyebrow">FIND COMPANIES</div>
      <h2>Search by company name or ticker</h2>
      <div className="search-row">
        <input
          className="search-input"
          type="search"
          placeholder="e.g. Microsoft or MSFT"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Search companies by name or ticker"
          spellCheck={false}
        />
      </div>

      <div className="search-layout">
        <div className="search-results" aria-live="polite">
          {state.name === "idle" && (
            <p className="fineprint">Type a name or ticker. Searching does not run any screening.</p>
          )}
          {state.name === "loading" && (
            <p className="fineprint">Searching… (the first search loads the company list from Moomoo, a few seconds)</p>
          )}
          {state.name === "error" && (
            <div className="notice error" role="alert">
              <b>Search failed</b>
              <p>{state.message}</p>
            </div>
          )}
          {state.name === "done" && state.data.results.length === 0 && (
            <p className="fineprint">No companies match “{state.data.query}”.</p>
          )}
          {state.name === "done" && state.data.results.length > 0 && (
            <>
              <ul className="hits">
                {state.data.results.map((hit) => (
                  <li key={hit.code}>
                    <button
                      type="button"
                      className={selected?.code === hit.code ? "hit selected" : "hit"}
                      onClick={() => setSelected(hit)}
                    >
                      <b>{hit.ticker}</b>
                      <span>{hit.name}</span>
                      {exchange(hit) && <small>{exchange(hit)}</small>}
                      {ws.isSaved(hit.code) && <small className="saved-tag">Saved</small>}
                    </button>
                  </li>
                ))}
              </ul>
              <p className="fineprint">
                Showing {state.data.results.length} of {state.data.total_matches} matches from the{" "}
                {state.data.source} ({state.data.directory_size?.toLocaleString()} listings, which can
                include OTC and other securities that screening will reject).
              </p>
            </>
          )}
        </div>

        <aside className="preview" aria-label="Company preview">
          {!selected ? (
            <p className="fineprint">Select a company to preview it.</p>
          ) : (
            <>
              <div className="eyebrow">{selected.ticker}</div>
              <h3 className="preview-name">{selected.name}</h3>
              <dl>
                <dt>Ticker</dt>
                <dd>{selected.ticker}</dd>
                <dt>Exchange</dt>
                <dd>{exchange(selected) ?? "Not provided"}</dd>
                {selected.listing_date && (
                  <>
                    <dt>Listed</dt>
                    <dd>{selected.listing_date}</dd>
                  </>
                )}
                <dt>Description</dt>
                <dd>No company description is available from the data source.</dd>
              </dl>
              <button
                className="button primary"
                type="button"
                disabled={added}
                onClick={() => ws.add(selected)}
              >
                {added ? "Added ✓" : "Add to saved companies"}
              </button>
              <p className="fineprint">
                Adding does not screen the company. Whether it is an eligible US common stock is
                checked when you screen it.
              </p>
            </>
          )}
        </aside>
      </div>
    </section>
  );
}
