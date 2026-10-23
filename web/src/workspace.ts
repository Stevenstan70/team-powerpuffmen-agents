// Saved companies and their latest screen results, shared by Home and Screener.
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, runResearch, type CompanyHit, type ResearchResult } from "./api";

export interface SavedCompany extends CompanyHit {
  added_at: string;
}

export type ScreenState =
  | { state: "running" }
  | { state: "error"; message: string; at: string }
  | { state: "done"; result: ResearchResult; at: string };

const KEY = "investiq.saved.v1";

function load(): SavedCompany[] {
  try {
    const raw = localStorage.getItem(KEY);
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list.filter((c) => c && typeof c.code === "string") : [];
  } catch {
    return [];
  }
}

export function useWorkspace() {
  const [saved, setSaved] = useState<SavedCompany[]>(load);
  const [screens, setScreens] = useState<Record<string, ScreenState>>({});
  const [running, setRunning] = useState(false);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(saved));
    } catch {
      // Saved list still works for this session.
    }
  }, [saved]);

  const isSaved = useCallback((code: string) => saved.some((c) => c.code === code), [saved]);

  // The provider code (e.g. US.NVDA) is the identity, so duplicates are impossible.
  const add = useCallback((hit: CompanyHit) => {
    setSaved((prev) =>
      prev.some((c) => c.code === hit.code) ? prev : [...prev, { ...hit, added_at: new Date().toISOString() }],
    );
  }, []);

  const remove = useCallback((code: string) => {
    setSaved((prev) => prev.filter((c) => c.code !== code));
    setScreens((prev) => {
      const next = { ...prev };
      delete next[code];
      return next;
    });
  }, []);

  const screen = useCallback(async (companies: SavedCompany[]) => {
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setRunning(true);
    // One at a time: the local OpenD gateway serves one lookup at a time.
    for (const c of companies) {
      if (controller.signal.aborted) break;
      setScreens((prev) => ({ ...prev, [c.code]: { state: "running" } }));
      try {
        const result = await runResearch(c.ticker, false, controller.signal);
        const at = new Date().toISOString();
        if (result.code !== c.code) {
          setScreens((prev) => ({
            ...prev,
            [c.code]: { state: "error", at, message: `Lookup returned ${result.code}, not ${c.code}. Result discarded.` },
          }));
          continue;
        }
        setScreens((prev) => ({ ...prev, [c.code]: { state: "done", result, at } }));
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          setScreens((prev) => {
            const next = { ...prev };
            if (next[c.code]?.state === "running") delete next[c.code];
            return next;
          });
          break;
        }
        setScreens((prev) => ({
          ...prev,
          [c.code]: {
            state: "error",
            at: new Date().toISOString(),
            message: err instanceof ApiError ? err.message : (err as Error).message,
          },
        }));
      }
    }
    if (abort.current === controller) setRunning(false);
  }, []);

  const stop = useCallback(() => {
    abort.current?.abort();
    setRunning(false);
  }, []);

  return { saved, screens, running, isSaved, add, remove, screen, stop };
}

export type Workspace = ReturnType<typeof useWorkspace>;
