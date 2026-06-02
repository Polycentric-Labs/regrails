/*
 * Static-data loader. The anti-drift pipeline (scripts/gen_web_data.py) dumps
 * the *installed regrails package*'s read-only surfaces to web/public/data/*.json,
 * which Vercel serves statically. The SPA only ever renders these — it never
 * recomputes engine state client-side. loadData() is the single fetch path.
 */

/** The known generated data files (see the design spec's data pipeline). */
export type DataName =
  | "rules"
  | "coverage"
  | "eval"
  | "oscal"
  | "sarif"
  | "methodology";

export class DataLoadError extends Error {
  constructor(
    public readonly name: DataName,
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "DataLoadError" as DataName; // satisfy Error.name typing
  }
}

/**
 * Fetch and parse `/data/<name>.json`. The caller supplies the expected shape
 * `T` (the route owns the precise type). Throws DataLoadError on a non-OK
 * response so an ErrorBoundary can render a fallback instead of a blank page.
 */
export async function loadData<T = unknown>(
  name: DataName,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`/data/${name}.json`, {
    headers: { accept: "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new DataLoadError(
      name,
      res.status,
      `Failed to load /data/${name}.json (HTTP ${res.status})`,
    );
  }
  return (await res.json()) as T;
}
