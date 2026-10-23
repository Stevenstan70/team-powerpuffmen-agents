---
name: PPM Finance
description: Evidence-first investment screening and monitoring workspace.
colors:
  background: "#0b1220"
  surface: "#111c2e"
  raised-surface: "#17243a"
  text: "#e6edf7"
  muted-text: "#a0aec0"
  divider: "#2b3b52"
  terminal-blue: "#35b8ff"
  signal-green: "#35d07f"
  signal-amber: "#f2c66d"
  signal-red: "#ff7185"
  near-white: "#f8fafc"
  badge-background: "#172d2a"
  badge-border: "#285845"
  badge-text: "#86e3b1"
  control-border: "#3b4e68"
  input-placeholder: "#93a4b8"
  input-label: "#d7e1ee"
  primary-deep: "#087db5"
  primary-border: "#1596d0"
  white: "#ffffff"
  input-surface: "#101a2a"
  alert-surface: "#132033"
  chart-label: "#b8c6d8"
  chart-rule: "#52647d"
  panel-heading: "#f1f5fa"
typography:
  display:
    fontSize: "1.35rem"
    fontWeight: 740
    letterSpacing: "-0.03em"
  page-heading:
    fontSize: "1.7rem"
    fontWeight: 680
  value:
    fontSize: "1.25rem"
    fontWeight: 650
  body:
    fontFamily: "sans-serif"
  supporting:
    fontSize: "0.85rem"
  section-heading:
    fontSize: "1rem"
  data-note:
    fontSize: "0.78rem"
  navigation:
    fontSize: "0.9rem"
  micro-label:
    fontSize: "0.7rem"
rounded:
  control: "5px"
  container: "5px"
  badge: "4px"
components:
  button-primary:
    backgroundColor: "#087db5"
    textColor: "#ffffff"
    rounded: "{rounded.control}"
    height: "2.6rem"
  tab-active:
    backgroundColor: "transparent"
    textColor: "#f8fafc"
    underlineColor: "{colors.terminal-blue}"
---

# Design System: PPM Finance

## Overview

**Creative North Star: "Institutional Research Sheet"**

PPM Finance is a restrained, dark research terminal for self-directed investors. It makes explicit screening evidence, company history, and review state easy to scan without implying a recommendation or a trading action. Deep navy surfaces frame high-contrast type, precise cyan navigation, and green, amber, and red result signals.

**Key Characteristics:**
- Evidence-first, explainable screening
- Deep charcoal-navy canvas and lighter raised surfaces
- PPM Finance masthead in normal document flow and direct horizontal primary navigation
- Distinct labels for verified live data, unavailable data, and synthetic demo data
- Familiar Streamlit controls, tuned for legibility rather than decorative density

## Colors

- **Canvas** (#0b1220): Main application background.
- **Surface** (#111c2e): Grouped content and chart surfaces.
- **Raised Surface** (#17243a): Secondary controls and interactive surfaces.
- **Primary Text** (#e6edf7): Main copy and essential data.
- **Muted Text** (#a0aec0): Supporting copy, labels, and metadata.
- **Divider** (#2b3b52): Subtle structural rules and borders.
- **Terminal Blue** (#35b8ff): Focus, chart series, and active navigation.
- **Signal Green** (#35d07f): PASS status.
- **Signal Amber** (#f2c66d): UNKNOWN status and caution.
- **Signal Red** (#ff7185): FAIL status.

## Typography

Use Streamlit's sans-serif theme. Keep the masthead compact and confident, section headings clear, and supporting labels high-contrast. Financial values use tabular numerals where available; status is always expressed in text as well as color.

## Layout

The wide research workspace starts with a masthead in normal document flow, below Streamlit's own toolbar, with the product title, purpose line, and prototype/data-provenance badge. A horizontal tab rail sits directly below as primary navigation: Screen, Tracked Companies, Approval, and About / Demo. A keyboard-only skip link targets the Screen content. The screen opens with a concise purpose line and a single ticker/action row, followed by quick demo fixtures. Once a screen exists, company identity and aggregate state lead into four criterion readouts and a Historical Comparison panel with metric selector and annual values; criteria and monitoring actions remain accessible below.

At widths below 760px, reduce outer gutters, stack the masthead, keep the metric readouts in two columns, and allow the tab rail to scroll horizontally. Preserve readable chart axes and avoid hiding the metric selector.

## Elevation & Shapes

Prefer layered navy surfaces and subtle 1px borders over shadows. Use 5px corners for controls and content groupings, with a small 4px environment badge radius. Keep focus rings visible and blue; use no heavy card nesting or decorative glows.

## Components

- **Masthead:** Fixed dark header with PPM Finance, “Investment research, screening & monitoring,” and “PROTOTYPE · SYNTHETIC DEMO DATA.”
- **Navigation:** Direct horizontal tabs for Screen, Tracked Companies, Approval, and About / Demo; the active tab is marked with a cyan underline.
- **Ticker input:** Deep inset surface, subtle border, readable placeholder, and clear cyan focus treatment.
- **Historical Comparison:** Interactive Altair line chart with year on X and a selector for `market_cap_usd`, `close_price_usd`, `operating_cash_flow_ttm_usd`, or `employee_count` on Y.
- **Demo history:** Synthetic annual examples derive from the selected fixture's snapshot values and are explicitly labeled as generated, not reported history. Missing fixture values remain unavailable; they are never plotted as zero.
- **Live history:** Show actual annual values only when source-provided history exists. The current Moomoo integration supplies snapshot/profile values, not verified annual series, so the live state explains that history is unavailable.
- **Criteria results:** Show PASS, FAIL, or UNKNOWN alongside observed value and threshold. Never rely on color alone.
- **Tracking and approvals:** Label session-only state and pending review. Never imply brokerage execution or continuous monitoring.

## Do's and Don'ts

**Do**
- Keep evidence and provenance beside the view that uses it.
- Use direct navigation and predictable chart controls.
- Retain all existing screening, tracking, approval, and demo behavior.
- Preserve readable contrast and keyboard focus in the dark palette.

**Don't**
- Present synthetic examples as historical financial performance.
- Treat missing metrics as zero or as a confirmed failure.
- Suggest that the app places trades, connects AI analysis, or monitors continuously.
- Use dense dashboard ornament that competes with the actual evidence.
