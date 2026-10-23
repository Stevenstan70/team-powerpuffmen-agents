// The only module that talks to the backend. All requests go to the local
// Python API; failures are surfaced to the caller, never replaced by sample data.

export type RuleStatus = "pass" | "fail" | "unknown";

export interface Criterion {
  id?: string;
  rule_id?: string;
  label: string;
  operator?: string;
  threshold: string | number;
  unit?: string;
  reporting_period: string;
  observed_fmt: string;
  status: RuleStatus;
  explanation: string;
  provenance?: Record<string, unknown> | null;
}

export interface Evaluation {
  ticker: string;
  company_name: string | null;
  data_timestamp: string | null;
  evaluated_at?: string;
  criteria_version: string;
  aggregate_status: RuleStatus;
  scope_note: string;
  criteria: Criterion[];
}

export interface RawRow {
  "Provider field": string;
  "Raw value": string;
  Use: string;
}

export interface Warning {
  stage: string;
  error_type: string;
  message: string;
}

export interface Technicals {
  method_version: string;
  price_basis: string;
  sessions: number;
  first_date: string;
  last_date: string;
  last_close: number | null;
  sma_50: number | null;
  sma_150: number | null;
  sma_200: number | null;
  avg_close_12m: number | null;
  high_52w: number | null;
  low_52w: number | null;
  pct_below_52w_high: number | null;
  pct_above_52w_low: number | null;
  avg_volume_50d: number | null;
  reliability: { ok: boolean; reason: string | null };
  unavailable: string[];
}

export interface TrendRule {
  rule_name: string;
  observed_value: number | null;
  reference_value: number | null;
  threshold: string;
  status: "PASS" | "FAIL" | "UNVERIFIED";
  explanation: string;
}

export interface Trend {
  trend_check_status: "PASS" | "FAIL" | "UNVERIFIED";
  criteria_version: string;
  rules: TrendRule[];
  scope_note: string;
}

export interface PricePoint {
  date: string;
  close: number;
  sma_150: number | null;
  sma_200: number | null;
}

export interface AgentResult {
  content: string;
  run_id: string | null;
  trace_id: string | null;
  tool_markers_in_response: { snapshot_screen: boolean; trend_check: boolean };
  evidence_sent: Record<string, unknown>;
  elapsed_seconds: number;
}

export interface ResearchResult {
  research_id: string;
  technicals_status: "computed" | "unavailable";
  technicals: Technicals | null;
  trend: Trend | null;
  price_series: PricePoint[];
  evaluation: Evaluation;
  raw: RawRow[];
  code: string;
  fetched_at: string;
  statement_status: "not_requested" | "validated" | "unavailable";
  warnings: Warning[];
  brief_markdown: string;
  server_elapsed_seconds: number;
}

export class ApiError extends Error {}

async function postJson<T>(
  url: string,
  payload: unknown,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload === undefined ? undefined : JSON.stringify(payload),
      signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(
      "Could not reach the local API. Start it with: python -m uvicorn api.server:app --host 127.0.0.1 --port 8000",
    );
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // Non-JSON body (for example the dev proxy reporting a refused connection).
  }

  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? (body as { detail: unknown }).detail
        : null;
    if (response.status >= 500 && detail == null) {
      throw new ApiError(
        "The local API is not responding. Is it running on 127.0.0.1:8000?",
      );
    }
    throw new ApiError(
      typeof detail === "string"
        ? detail
        : `Request failed (HTTP ${response.status}). Check the ticker and try again.`,
    );
  }
  return body as T;
}

export function runResearch(
  ticker: string,
  includeStatementProfit: boolean,
  signal?: AbortSignal,
): Promise<ResearchResult> {
  return postJson<ResearchResult>(
    "/api/research",
    { ticker, include_statement_profit: includeStatementProfit },
    signal,
  );
}

export function runAgent(
  researchId: string,
  signal?: AbortSignal,
): Promise<AgentResult> {
  return postJson<AgentResult>(
    `/api/research/${encodeURIComponent(researchId)}/agent`,
    undefined,
    signal,
  );
}

export interface ScenarioChange {
  label: string;
  old_value: string;
  new_value: string;
  old_status: RuleStatus;
  new_status: RuleStatus;
}

export interface Scenario {
  ticker: string;
  name: string;
  evaluation: Evaluation;
  updated?: Evaluation;
  changes?: ScenarioChange[];
}

export async function fetchScenarios(): Promise<Scenario[]> {
  let response: Response;
  try {
    response = await fetch("/api/scenarios");
  } catch {
    throw new ApiError("Could not reach the local API.");
  }
  if (!response.ok) throw new ApiError(`Request failed (HTTP ${response.status}).`);
  return (await response.json()) as Scenario[];
}

export interface CompanyHit {
  code: string;
  ticker: string;
  name: string;
  exchange_type?: string;
  listing_date?: string;
}

export interface CompanySearch {
  query: string;
  source?: string;
  directory_size?: number;
  directory_loaded_at?: string;
  total_matches: number;
  results: CompanyHit[];
}

export async function searchCompanies(q: string, signal?: AbortSignal): Promise<CompanySearch> {
  let response: Response;
  try {
    response = await fetch(`/api/companies?q=${encodeURIComponent(q)}`, { signal });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError("Could not reach the local API.");
  }
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // fall through
  }
  if (!response.ok) {
    const detail = body && typeof body === "object" && "detail" in body ? (body as { detail: unknown }).detail : null;
    throw new ApiError(typeof detail === "string" ? detail : `Search failed (HTTP ${response.status}).`);
  }
  return body as CompanySearch;
}
