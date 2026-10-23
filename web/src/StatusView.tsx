const WORKS = [
  "Four-rule snapshot screen (policy snapshot-net-profit-volume-v2) with PASS / FAIL / UNVERIFIED and missing inputs preserved.",
  "Real US company lookup through local Moomoo OpenD: exact security check and market snapshot with validation.",
  "Optional statement-reported USD net profit, validated; if it fails, the screen continues and the failure is recorded.",
  "Price-trend measures from real daily candles (50/150/200-session and 12-month averages, 52-week range), computed in Python; a split-like jump withholds the averages.",
  "Preliminary research brief assembled deterministically from that evidence, downloadable as Markdown.",
  "Each lookup runs in its own process with a timeout, so a Moomoo SDK failure cannot take the API down.",
];

const BUILT_UNVERIFIED = [
  "IBM Orchestrate agent for real companies (two tools: snapshot screen and trend check). The code, agent definition and tests exist, but it has not been run against your Orchestrate instance. Import it, run it, then confirm both tool calls in the Orchestrate trace.",
];

const NOT_YET = [
  "Market capitalisation and previous close for real companies (USD mapping unverified).",
  "News retrieval, cross-source conflict checking and valuation scenarios.",
  "Accepted-scenario approval for real companies (the existing approval flow is synthetic only).",
  "VCP detection, entry/exit levels and any price targets.",
  "Measured time saved versus manual research.",
];

function Section({ eyebrow, title, items }: { eyebrow: string; title: string; items: string[] }) {
  return (
    <section className="card">
      <div className="eyebrow">{eyebrow}</div>
      <h2>{title}</h2>
      <ul className="plain-list">
        {items.map((t) => (
          <li key={t}>{t}</li>
        ))}
      </ul>
    </section>
  );
}

export default function StatusView() {
  return (
    <>
      <Section eyebrow="VERIFIED IN TESTS" title="Working" items={WORKS} />
      <Section eyebrow="BUILT, NOT YET VERIFIED LIVE" title="Needs a live check" items={BUILT_UNVERIFIED} />
      <Section eyebrow="NOT IMPLEMENTED" title="Not yet working" items={NOT_YET} />
      <p className="fineprint">
        Planned capabilities are not described as working anywhere in this
        interface. Tests use a simulated Moomoo SDK; live behaviour depends on
        your OpenD session.
      </p>
    </>
  );
}
