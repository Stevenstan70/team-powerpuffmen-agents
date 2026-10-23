import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ScreenerView from "./ScreenerView";
import { useWorkspace } from "./workspace";

beforeEach(() => {
  try {
    localStorage.clear();
  } catch {
    // ignore
  }
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const searchBody = {
  query: "nvidia",
  source: "Moomoo OpenD US stock list",
  directory_size: 3,
  total_matches: 1,
  results: [{ code: "US.NVDA", ticker: "NVDA", name: "NVIDIA", exchange_type: "US_NASDAQ" }],
};

function Harness() {
  const ws = useWorkspace();
  return <ScreenerView ws={ws} onOpen={() => {}} />;
}

function mockFetch() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.startsWith("/api/companies")) {
      return new Response(JSON.stringify(searchBody), { status: 200 });
    }
    throw new Error(`unexpected request ${url}`);
  });
}

describe("company search and saved companies", () => {
  it("previews, adds once, shows Added, and removes", async () => {
    const f = mockFetch();
    const user = userEvent.setup();
    render(<Harness />);

    await user.type(screen.getByLabelText(/search companies/i), "nvidia");
    await user.click(await screen.findByRole("button", { name: /NVDA\s*NVIDIA/ }));

    const preview = screen.getByLabelText("Company preview");
    expect(within(preview).getByText("NASDAQ")).toBeInTheDocument();
    expect(within(preview).getByText(/No company description is available/)).toBeInTheDocument();

    const add = within(preview).getByRole("button", { name: "Add to saved companies" });
    await user.click(add);
    const added = within(preview).getByRole("button", { name: /Added/ });
    expect(added).toBeDisabled();

    // Preview and adding never trigger research.
    expect(f.mock.calls.every(([u]) => String(u).startsWith("/api/companies"))).toBe(true);

    const table = screen.getByRole("table");
    expect(within(table).getAllByText("NVDA")).toHaveLength(1);
    expect(within(table).getByText("Not screened yet")).toBeInTheDocument();

    await user.click(within(table).getByRole("button", { name: /Remove NVDA/ }));
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(within(preview).getByRole("button", { name: "Add to saved companies" })).toBeEnabled();
  });

  it("shows a lookup failure distinctly from no matches", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "The company list could not be loaded: down" }), { status: 502 }),
    );
    const user = userEvent.setup();
    render(<Harness />);
    await user.type(screen.getByLabelText(/search companies/i), "nv");
    expect(await screen.findByText("Search failed")).toBeInTheDocument();
    expect(screen.getByText(/could not be loaded/)).toBeInTheDocument();
  });

  it("says when nothing matches", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ...searchBody, query: "zzz", total_matches: 0, results: [] }), { status: 200 }),
    );
    const user = userEvent.setup();
    render(<Harness />);
    await user.type(screen.getByLabelText(/search companies/i), "zzz");
    expect(await screen.findByText(/No companies match/)).toBeInTheDocument();
  });
});
