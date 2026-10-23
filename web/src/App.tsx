import { useEffect, useState } from "react";
import HomeView from "./HomeView";
import ResearchView from "./ResearchView";
import ScenariosView from "./ScenariosView";
import ScreenerView from "./ScreenerView";
import StatusView from "./StatusView";
import { useWorkspace } from "./workspace";

// Hash routes, so direct links and browser back/forward work without a server.
const NAV = [
  { route: "/", label: "Home" },
  { route: "/screener", label: "Screener" },
  { route: "/research", label: "Research" },
  { route: "/scenarios", label: "Scenarios" },
  { route: "/status", label: "Build status" },
] as const;

const HEADING: Record<string, { title: string; blurb: string }> = {
  "/": { title: "Overview", blurb: "The companies you follow and how they screen today." },
  "/screener": { title: "Screener", blurb: "Find companies, save them, and compare their screening results." },
  "/research": { title: "Company research", blurb: "The short answer first. The evidence is one click away." },
  "/scenarios": {
    title: "How it handles each case",
    blurb: "Four fictional companies: a pass, a fail, missing data, and a change that needs your approval.",
  },
  "/status": { title: "What works today", blurb: "Verified functionality, separated from planned work." },
};

function currentPath() {
  const raw = window.location.hash.replace(/^#/, "");
  return raw === "" ? "/" : raw;
}

export default function App() {
  const [path, setPath] = useState(currentPath);
  const ws = useWorkspace();

  useEffect(() => {
    const onHash = () => {
      setPath(currentPath());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const go = (route: string) => {
    window.location.hash = route;
  };
  const openResearch = (code: string) => go(`/research/${encodeURIComponent(code)}`);

  const [base, param] = (() => {
    const m = path.match(/^\/research\/(.+)$/);
    return m ? ["/research", decodeURIComponent(m[1])] : [path, null];
  })();
  const known = NAV.some((n) => n.route === base);
  const section = known ? base : "/";
  const h = HEADING[section];
  const label = NAV.find((n) => n.route === section)!.label;

  // A research link reuses that company's latest screen, if there is one.
  const screened = param ? ws.screens[param] : undefined;
  const initialResult = screened?.state === "done" ? screened.result : undefined;
  const savedTicker = param ? ws.saved.find((c) => c.code === param)?.ticker : undefined;
  const initialTicker = savedTicker ?? (param?.startsWith("US.") ? param.slice(3) : param) ?? "AAPL";

  return (
    <div className="shell">
      <aside className="sidebar">
        <a className="brand" href="#/">
          <span className="brand-icon">iq</span>
          <span>
            INVEST
            <br />
            <b>IQ</b>
          </span>
        </a>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          {NAV.map((n) => (
            <a
              key={n.route}
              href={`#${n.route}`}
              className={section === n.route ? "nav active" : "nav"}
              aria-current={section === n.route ? "page" : undefined}
            >
              <span>{n.label}</span>
            </a>
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
            Workspace <span>/</span> <b>{label}</b>
            {param && (
              <>
                {" "}
                <span>/</span> <b>{initialTicker}</b>
              </>
            )}
          </div>
          <span className="top-status">Requires local Moomoo OpenD</span>
        </header>
        <div className="content">
          <div className="page-heading">
            <div>
              <h1>{h.title}</h1>
              <p>{h.blurb}</p>
            </div>
          </div>
          {section === "/" && <HomeView ws={ws} onOpen={openResearch} go={go} />}
          {section === "/screener" && <ScreenerView ws={ws} onOpen={openResearch} />}
          {section === "/research" && (
            <ResearchView
              key={param ?? "new"}
              initialTicker={initialTicker}
              initialResult={initialResult}
            />
          )}
          {section === "/scenarios" && <ScenariosView />}
          {section === "/status" && <StatusView />}
        </div>
      </main>
    </div>
  );
}
