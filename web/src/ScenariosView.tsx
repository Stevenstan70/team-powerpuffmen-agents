import { useEffect, useState } from "react";
import { ApiError, fetchScenarios, type Evaluation, type RuleStatus, type Scenario } from "./api";

const LABEL: Record<RuleStatus, string> = {
  pass: "PASS",
  fail: "FAIL",
  unknown: "UNVERIFIED",
};

// What each case demonstrates, in plain words for the walkthrough.
const STORY: Record<string, { title: string; what: string }> = {
  ACME: {
    title: "Everything checks out",
    what: "All four inputs are present and every rule passes, so the screen passes.",
  },
  BLUE: {
    title: "A rule fails",
    what: "Net profit is negative. The screen fails and says exactly which rule and why.",
  },
  CRST: {
    title: "Evidence is missing",
    what: "Net profit is unavailable. Nothing is guessed or filled with zero: the rule stays UNVERIFIED and the screen cannot pass.",
  },
  SMCHG: {
    title: "Something changes: you decide",
    what: "A later check finds profit has turned negative. InvestIQ proposes updating the accepted result, but only you can accept or reject it.",
  },
};

function Rules({ e }: { e: Evaluation }) {
  return (
    <table>
      <tbody>
        {e.criteria.map((c) => (
          <tr key={c.label}>
            <td>{c.label}</td>
            <td>{c.observed_fmt}</td>
            <td>
              <span className={`badge state-${LABEL[c.status]}`}>{LABEL[c.status]}</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Approval({ s }: { s: Scenario }) {
  const [decision, setDecision] = useState<null | { kind: "Accepted" | "Rejected"; at: string }>(null);
  const accepted = decision?.kind === "Accepted" ? s.updated! : s.evaluation;
  return (
    <div className="approval">
      <b>Proposed change</b>
      <table>
        <thead>
          <tr>
            <th>Rule</th>
            <th>Before</th>
            <th>Now</th>
          </tr>
        </thead>
        <tbody>
          {s.changes!.map((c) => (
            <tr key={c.label}>
              <td>{c.label}</td>
              <td>
                {c.old_value}{" "}
                <span className={`badge state-${LABEL[c.old_status]}`}>{LABEL[c.old_status]}</span>
              </td>
              <td>
                {c.new_value}{" "}
                <span className={`badge state-${LABEL[c.new_status]}`}>{LABEL[c.new_status]}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {decision ? (
        <p className="decision">
          {decision.kind} by you at {decision.at}. Accepted result is now{" "}
          <span className={`badge state-${LABEL[accepted.aggregate_status]}`}>
            {LABEL[accepted.aggregate_status]}
          </span>{" "}
          <button className="text-button" type="button" onClick={() => setDecision(null)}>
            Undo
          </button>
        </p>
      ) : (
        <div className="approval-actions">
          <button
            className="button primary"
            type="button"
            onClick={() => setDecision({ kind: "Accepted", at: new Date().toLocaleTimeString() })}
          >
            Accept change
          </button>
          <button
            className="button"
            type="button"
            onClick={() => setDecision({ kind: "Rejected", at: new Date().toLocaleTimeString() })}
          >
            Reject, keep previous
          </button>
        </div>
      )}
    </div>
  );
}

export default function ScenariosView() {
  const [data, setData] = useState<Scenario[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchScenarios()
      .then(setData)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : (err as Error).message),
      );
  }, []);

  return (
    <>
      <div className="notice warn">
        <b>Synthetic companies</b>
        <p>
          These four companies are fictional, with made-up numbers, built to show
          how InvestIQ handles each situation. They run through the same
          screening rules as real companies.
        </p>
      </div>
      {error && (
        <div className="notice error" role="alert">
          <b>Could not load the scenarios</b>
          <p>{error}</p>
        </div>
      )}
      <div className="scenario-grid">
        {data?.map((s, i) => (
          <section className="card scenario" key={s.ticker}>
            <div className="section-top">
              <div>
                <div className="eyebrow">CASE {i + 1} · {s.ticker}</div>
                <h2>{STORY[s.ticker]?.title ?? s.name}</h2>
              </div>
              <span className={`badge state-${LABEL[s.evaluation.aggregate_status]}`}>
                {LABEL[s.evaluation.aggregate_status]}
              </span>
            </div>
            <p className="lead">{STORY[s.ticker]?.what}</p>
            <div className="table-wrap">
              <Rules e={s.evaluation} />
            </div>
            {s.changes && s.changes.length > 0 && <Approval s={s} />}
          </section>
        ))}
      </div>
    </>
  );
}
