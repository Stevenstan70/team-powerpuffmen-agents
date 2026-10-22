# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- Self-directed retail investors managing their own stock portfolios.
- Evidence-based researchers conducting initial company screens and ongoing monitoring.

## Product Purpose

PPM Finance helps investors assess a stock against explicit screening criteria and monitor changes over time. Success means users can understand each result and its evidence without relying on a black-box recommendation.

## Positioning

Explainable, per-criterion pass/fail/unknown results with a review workflow, rather than automated trading or discretionary portfolio management.

## Operating Context

Users enter a ticker, review available screening results, save a baseline, check for changes, and may approve a move to a needs-review list.

## Capabilities and Constraints

- The existing Streamlit app supports screening, tracked companies, approval, and demo scenarios.
- Moomoo can provide company lookup and some current financial inputs when its local service is connected.
- Demo fixtures are synthetic and must remain visibly labeled as demo data.
- Tracked companies and approvals are stored in session state and are lost on refresh.
- AI analysis, continuous monitoring, scheduled monitoring, and brokerage actions are not connected or implemented.
- Historical growth charts are a requested design goal, but no historical time-series data source or retrieval capability is currently established. Charts must not imply real historical performance unless verified data is available; synthetic examples must be clearly labeled.
- Keep existing screening and monitoring behavior while making the interface more visual and easier to learn.

## Brand Commitments

- Product name: PPM Finance.

## Evidence on Hand

- Screening rules and result handling: `tools/powerpuffmen_basic_screen.py`.
- Synthetic demo fixtures and adapter behavior: `frontend/adapter.py`.
- Existing Streamlit workflows and labels: `app.py`.
- No historical growth series, performance claims, or investment recommendations are established by the repository.

## Product Principles

- Make each screening result and its underlying criterion understandable.
- Distinguish verified data, unavailable data, and synthetic demo data.
- Preserve investor control; the app does not trade or make decisions for users.
- Never present missing information as zero or as a confirmed failure.
- Use visuals to clarify evidence, comparisons, and trends without inventing data.

## Accessibility & Inclusion

- Make the interface easy to understand and use, with clear labels and readable visual distinctions.
