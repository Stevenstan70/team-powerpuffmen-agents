---
version: 1
slug: "app-py"
primary_target: "app.py"
related_targets: []
mode: Operate
---

# PPM Finance — Institutional Research Sheet

## Scope

Redesign the full Streamlit app in Operate mode for self-directed retail investors and evidence-based researchers. Preserve screening, demo shortcuts, tracked companies, approval, simulated-change flow, honest integration status, and current non-trading/session-only constraints. The four main work areas stay directly accessible from primary navigation.

## Direction contract

**THESIS:** Make the underlying evidence and its provenance the first things an investor can scan; keep the interface controlled and institutional rather than a generic dashboard.

**OWN-WORLD:** Deep charcoal-navy surfaces, high-contrast white text, cyan interaction and chart accents, and bright but restrained pass/fail/unknown signals. Use a masthead in normal document flow below Streamlit's toolbar, subtle borders, compact controls, and a horizontal tab rail. Keep the familiar Streamlit interaction model.

**STORY:** The investor can screen a ticker, inspect explicit criteria, compare a metric across years when that evidence exists, save a baseline, and review a proposed list change. Nothing suggests a black-box recommendation, brokerage action, or continuous monitoring.

**FIRST VIEWPORT:** Visible PPM Finance header and prototype/synthetic-data badge; accessible skip link; direct Screen, Tracked Companies, Approval, and About / Demo navigation; a concise screen purpose, aligned ticker/Analyse row, and quick demo fixtures. Keep an empty-state Historical Comparison visible before the first run. After screening, show company identity and status, four screening readouts, and the annual Historical Comparison with selector for market cap, closing price, TTM operating cash flow, or employee count. Demo-only history is synthetic and clearly labeled. Live mode must say annual history is unavailable unless verified source data is provided.

**FORM:** Institutional Research Sheet. Use concise labels, precise alignment, tabular financial values, dark surfaces, and small-radius controls. Keep user actions and available evidence obvious without a forced workflow.

**FINISH:** Preserve screen/tracking/approval behavior, verify every chart metric and empty state, keep source provenance visible, and update DESIGN.md to the shipped direction.

## Data contract

- Demo annual points are generated from the selected fixture's current observed value and labeled synthetic, not reported company history.
- An unknown fixture observation remains unknown and must not generate a zero-valued series.
- Live annual points may be rendered only from validated source-provided `historical_data`; the current Moomoo adapter does not populate that field.
- Keep exact metric keys available in the selector: `market_cap_usd`, `close_price_usd`, `operating_cash_flow_ttm_usd`, and `employee_count`.
