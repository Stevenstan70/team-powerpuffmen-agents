import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ResearchView from "./ResearchView";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const criterion = (label: string, status: string, observed: string) => ({
  label, status, observed_fmt: observed, threshold: ">= x",
  reporting_period: "period", explanation: `${label} explanation`,
});

const series = Array.from({ length: 220 }, (_, i) => ({
  date: `2026-01-${String((i % 28) + 1).padStart(2, "0")}`,
  close: 100 + i * 0.1,
  sma_150: i >= 149 ? 105 + i * 0.05 : null,
  sma_200: i >= 199 ? 108 + i * 0.05 : null,
}));

const technicals = {
  method_version: "technicals-v1", price_basis: "Moomoo daily candles, unadjusted",
  sessions: 270, first_date: "2025-09-01", last_date: "2026-10-22",
  last_close: 125.5, sma_50: 120, sma_150: 115, sma_200: 110, avg_close_12m: 108,
  high_52w: 130, low_52w: 90, pct_below_52w_high: 3.46, pct_above_52w_low: 39.44,
  avg_volume_50d: 1000000, reliability: { ok: true, reason: null }, unavailable: [],
};

const trend = {
  trend_check_status: "PASS", criteria_version: "trend-check-v1",
  scope_note: "Three price-trend conditions were checked.",
  rules: [
    { rule_name: "above_12m_average", observed_value: 125.5, reference_value: 108,
      threshold: "last_close > 12-month average close", status: "PASS", explanation: "" },
  ],
};

const result = (over: Record<string, unknown> = {}) => ({
  research_id: "rid-1",
  technicals_status: "computed", technicals, trend, price_series: series,
  code: "US.AAPL",
  fetched_at: "2026-10-23T10:00:00+00:00",
  statement_status: "unavailable",
  warnings: [{
    stage: "statement_retrieval", error_type: "RuntimeError",
    message: "Optional statement evidence was unavailable. Net profit remains unavailable.",
  }],
  server_elapsed_seconds: 1.2,
  raw: [{ "Provider field": "volume", "Raw value": "150000", Use: "Evaluated as snapshot shares" }],
  brief_markdown: "# InvestIQ preliminary company research brief\n\n| a | b |\n|---|---|\n| 1 | 2 |\n",
  evaluation: {
    ticker: "AAPL", company_name: "Apple", data_timestamp: "2026-10-22 16:00:00",
    criteria_version: "snapshot-net-profit-volume-v2", aggregate_status: "unknown",
    scope_note: "Scope note text.",
    criteria: [
      criterion("Market Cap Range", "unknown", "Unavailable"),
      criterion("Net Profit", "unknown", "Unavailable"),
      criterion("Snapshot Volume", "pass", "150,000 shares"),
    ],
  },
  ...over,
});

function mockFetch(status: number, body: unknown) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(body), { status }),
  );
}

describe("ResearchView", () => {
  it("shows evidence, recovery warning, brief and no sample data", async () => {
    const f = mockFetch(200, result());
    render(<ResearchView />);
    await userEvent.click(screen.getByRole("button", { name: /retrieve and build brief/i }));
    expect(await screen.findByText(/Apple \(US\.AAPL\)/)).toBeInTheDocument();
    expect(screen.getByText(/Incomplete screen/)).toBeInTheDocument();
    expect(screen.getByText(/Recovery: statement retrieval/)).toBeInTheDocument();
    expect(screen.getAllByText("UNVERIFIED").length).toBeGreaterThan(0);
    expect(screen.getByText("150,000 shares")).toBeInTheDocument();
    expect(screen.getByText("InvestIQ preliminary company research brief")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /download brief/i })).toBeInTheDocument();
    expect(screen.getByText(/not a measured saving/i)).toBeInTheDocument();
    const body = JSON.parse(f.mock.calls[0][1]!.body as string);
    expect(body).toEqual({ ticker: "AAPL", include_statement_profit: false });
  });

  it("sends the statement option when ticked", async () => {
    const f = mockFetch(200, result());
    render(<ResearchView />);
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: /retrieve/i }));
    await screen.findByText(/Apple/);
    expect(JSON.parse(f.mock.calls[0][1]!.body as string).include_statement_profit).toBe(true);
  });

  it("shows the API error and substitutes nothing", async () => {
    mockFetch(502, { detail: "ConnectionError: OpenD not running" });
    render(<ResearchView />);
    await userEvent.click(screen.getByRole("button", { name: /retrieve/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("OpenD not running");
    expect(screen.getByText(/No sample data was substituted/)).toBeInTheDocument();
    expect(screen.queryByText(/Research brief/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Incomplete screen/)).not.toBeInTheDocument();
  });

  it("explains an unreachable API without fabricating a result", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    render(<ResearchView />);
    await userEvent.click(screen.getByRole("button", { name: /retrieve/i }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/uvicorn api\.server:app/));
    expect(screen.queryByText(/Incomplete screen/)).not.toBeInTheDocument();
  });
});

describe("technicals and agent", () => {
  it("shows the technical card with trend rules and chart", async () => {
    mockFetch(200, result());
    render(<ResearchView />);
    await userEvent.click(screen.getByRole("button", { name: /retrieve/i }));
    expect(await screen.findByText("Price trend")).toBeInTheDocument();
    expect(screen.getByText(/Trend check \(trend-check-v1\)/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /closing price/i })).toBeInTheDocument();
  });

  it("says plainly when price history is unavailable and draws no chart", async () => {
    mockFetch(200, result({ technicals_status: "unavailable", technicals: null,
      trend: null, price_series: [] }));
    render(<ResearchView />);
    await userEvent.click(screen.getByRole("button", { name: /retrieve/i }));
    expect(await screen.findByText("Price history unavailable")).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /closing price/i })).not.toBeInTheDocument();
  });

  it("sends nothing to the agent until the button is pressed, then shows the reply and caveats", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/agent")) {
        return new Response(JSON.stringify({
          content: "## Agent says hello", run_id: "run-9", trace_id: "trace-9",
          tool_markers_in_response: { snapshot_screen: true, trend_check: false },
          evidence_sent: { ticker: "AAPL" }, elapsed_seconds: 4.2 }), { status: 200 });
      }
      return new Response(JSON.stringify(result()), { status: 200 });
    });
    render(<ResearchView />);
    await userEvent.click(screen.getByRole("button", { name: /retrieve/i }));
    await screen.findByText("Agent research summary");
    expect(f.mock.calls.some(([u]) => String(u).endsWith("/agent"))).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: /ask the ibm agent/i }));
    expect(await screen.findByText("Agent says hello")).toBeInTheDocument();
    expect(screen.getByText(/AI-generated by the Orchestrate agent/)).toBeInTheDocument();
    expect(screen.getByText(/run-9/)).toBeInTheDocument();
    expect(screen.getByText(/Trend-check version string in the reply: no/)).toBeInTheDocument();
    expect(screen.getByText(/Data sent to the agent/)).toBeInTheDocument();
    expect(f.mock.calls.some(([u]) => String(u) === "/api/research/rid-1/agent")).toBe(true);
  });

  it("shows agent configuration errors and nothing else", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
      String(input).endsWith("/agent")
        ? new Response(JSON.stringify({ detail: "WXO_RESEARCH_AGENT_ID is not configured." }), { status: 503 })
        : new Response(JSON.stringify(result()), { status: 200 }));
    render(<ResearchView />);
    await userEvent.click(screen.getByRole("button", { name: /retrieve/i }));
    await userEvent.click(await screen.findByRole("button", { name: /ask the ibm agent/i }));
    expect(await screen.findByText(/WXO_RESEARCH_AGENT_ID is not configured/)).toBeInTheDocument();
    expect(screen.queryByText(/AI-generated by the Orchestrate agent/)).not.toBeInTheDocument();
  });
});
