import { useState } from "react";
import type { ResearchResult } from "./api";
import ResearchView from "./ResearchView";
import ScreenerView from "./ScreenerView";
import StatusView from "./StatusView";

const NAV = ["Screener", "Research", "Build status"] as const;
type Tab = (typeof NAV)[number];

const HEADING: Record<Tab, { title: string; blurb: string }> = {
  Screener: {
    title: "Screener",
    blurb: "Real companies checked against the screening rules. Unverified data stays labelled.",
  },
  Research: {
    title: "Company research",
    blurb: "Evidence you can inspect. Decisions you control.",
  },
  "Build status": {
    title: "What works today",
    blurb: "Verified functionality, separated from planned work.",
  },
};

export default function App() {
  const [tab, setTab] = useState<Tab>("Screener");
  const [opened, setOpened] = useState<ResearchResult | null>(null);
  const h = HEADING[tab];

  function openResearch(result: ResearchResult) {
    setOpened(result);
    setTab("Research");
    window.scrollTo(0, 0);
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <a className="brand" href="/">
          <span className="brand-icon">↗</span>
          <span>
            INVEST
            <br />
            <b>IQ</b>
          </span>
        </a>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          {NAV.map((n) => (
            <button
              key={n}
              className={tab === n ? "nav active" : "nav"}
              onClick={() => setTab(n)}
            >
              <span>{n}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="dot" />
          Research mode
          <p>No orders. Changes to accepted assumptions need your approval.</p>
        </div>
        <div className="private-label">◈ Local workspace</div>
      </aside>
      <main>
        <header className="topbar">
          <div className="crumb">
            Workspace <span>/</span> <b>{tab}</b>
          </div>
          <span className="top-status">Requires local Moomoo OpenD</span>
        </header>
        <div className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">PATIENT CAPITAL. VISIBLE EVIDENCE.</div>
              <h1>{h.title}</h1>
              <p>{h.blurb}</p>
            </div>
          </div>
          {/* Screener stays mounted so its results survive a trip to Research. */}
          <div hidden={tab !== "Screener"}>
            <ScreenerView onOpen={openResearch} />
          </div>
          {tab === "Research" && (
            <ResearchView
              key={opened?.research_id ?? "new"}
              initialTicker={opened?.evaluation.ticker ?? "AAPL"}
              initialResult={opened ?? undefined}
            />
          )}
          {tab === "Build status" && <StatusView />}
        </div>
      </main>
    </div>
  );
}
