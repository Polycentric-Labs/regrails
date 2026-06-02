/**
 * `/exports` — Exports (OSCAL & SARIF). Owned by task B3.7.
 *
 * Two tabs over the two read-only interchange surfaces the anti-drift pipeline
 * dumps to `public/data/`:
 *   • OSCAL  — the encoded-rules control catalog (oscal.json), for GRC tooling.
 *   • SARIF  — the per-outcome code-scanning surface (sarif.json), for CI gates.
 *
 * Each tab pretty-prints the live payload in a <CodeBlock> (text node, never
 * innerHTML — XSS-safe) with the primitive's built-in Blob→<a download> button,
 * and carries an HONEST capability note so a GRC reader is not misled about the
 * standards posture (OSCAL is structurally shaped, NOT NIST-validated; SARIF is
 * a real 2.1.0 document meant to gate AI workflows in CI).
 *
 * The SPA only ever renders these generated files; it never recomputes engine
 * state client-side (see lib/data.ts).
 */
import { useEffect, useState } from "react";
import { DataLoadError, loadData, type DataName } from "../lib/data";
import { Card, CardBody, CardHead } from "../ui/Card";
import CodeBlock from "../ui/CodeBlock";

type TabKey = "oscal" | "sarif";

interface ExportTab {
  key: TabKey;
  /** The generated data file this tab fetches + downloads. */
  data: DataName;
  /** Tab-strip label. */
  label: string;
  /** Download filename (matches the served data file). */
  file: string;
  /** Short standard descriptor shown next to the tab title. */
  standard: string;
  /** One-sentence "what is this export for" line. */
  purpose: string;
  /** Honest capability note — tone matches the .alert variant below. */
  note: string;
  /** .alert modifier: "warning" tempers the OSCAL claim, "success" affirms SARIF. */
  noteTone: "warning" | "success";
  /** Accessible heading for the note. */
  noteTitle: string;
}

const TABS: readonly ExportTab[] = [
  {
    key: "oscal",
    data: "oscal",
    label: "OSCAL",
    file: "oscal.json",
    standard: "OSCAL 1.1.2-shaped",
    purpose:
      "A machine-readable control catalog of the encoded FERPA + Title IV rules — the surface a GRC platform (or an OSCAL-aware tool) ingests to map RegRails coverage into an existing compliance program.",
    note: "OSCAL 1.1.2-SHAPED — structurally aligned to the catalog model, but NOT NIST-validated. The document mirrors the OSCAL 1.1.2 catalog shape (groups → controls → parts/props, with SHA-256 back-matter); it has not been run through an official NIST OSCAL validator and makes no certification claim. Treat it as a faithful structural export, not a conformance attestation.",
    noteTone: "warning",
    noteTitle: "Honest scope",
  },
  {
    key: "sarif",
    data: "sarif",
    label: "SARIF",
    file: "sarif.json",
    standard: "SARIF 2.1.0",
    purpose:
      "A static-analysis–style results file describing each gate outcome as a finding — drop it into a code-scanning surface (e.g. a CI step or a security dashboard) to gate AI workflows the same way you would gate code.",
    note: "SARIF 2.1.0 — a standard static-analysis results document (OASIS SARIF v2.1.0 schema). Wire it into CI to gate AI workflows: each blocked or escalated outcome becomes a finding with its citation and risk tier, so a pipeline can fail or require review on a regulated decision just like it would on a code vulnerability.",
    noteTone: "success",
    noteTitle: "What you get",
  },
] as const;

function tabByKey(key: TabKey): ExportTab {
  // TABS is exhaustive over TabKey; the non-null assertion is safe.
  return TABS.find((t) => t.key === key)!;
}

/** Pretty-print with stable 2-space indentation for the viewer + the download. */
function pretty(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export default function Exports() {
  const [active, setActive] = useState<TabKey>("oscal");
  // One cache slot per tab so switching back is instant and we fetch each once.
  const [payloads, setPayloads] = useState<Partial<Record<TabKey, unknown>>>(
    {},
  );
  const [error, setError] = useState<string | null>(null);

  const tab = tabByKey(active);
  const cached = payloads[active];

  useEffect(() => {
    if (cached !== undefined) {
      setError(null);
      return;
    }
    let cancelled = false;
    setError(null);
    loadData(tab.data)
      .then((json) => {
        if (!cancelled) setPayloads((prev) => ({ ...prev, [tab.key]: json }));
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(
          err instanceof DataLoadError
            ? err.message
            : `Could not load ${tab.file}.`,
        );
      });
    return () => {
      cancelled = true;
    };
  }, [tab.data, tab.key, tab.file, cached]);

  const json = cached !== undefined ? pretty(cached) : null;

  return (
    <section className="page stack-5" data-route="exports">
      <header className="stack-2">
        <h1 className="page-title">Exports</h1>
        <p className="page-sub">
          The encoded ruleset and every gate outcome, exported as open
          interchange formats so RegRails plugs into the GRC and CI tooling a
          compliance team already runs — OSCAL for the control catalog, SARIF
          for the code-scanning surface.
        </p>
      </header>

      {/* Tab strip — built from primitives (no bespoke tab CSS in the system). */}
      <div className="box" role="tablist" aria-label="Export formats">
        <div className="row gap-2 wrap">
          {TABS.map((t) => {
            const selected = t.key === active;
            return (
              <button
                key={t.key}
                type="button"
                role="tab"
                id={`export-tab-${t.key}`}
                aria-selected={selected}
                aria-controls={`export-panel-${t.key}`}
                className={`btn ${selected ? "default" : "ghost"}`}
                onClick={() => setActive(t.key)}
              >
                {t.label}
                <span className="code-chip" style={{ marginLeft: "0.1rem" }}>
                  {t.file}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Active panel. Only the selected tab mounts so its viewer + note are
          unambiguous (and we never paint OSCAL prose while SARIF is showing). */}
      <div
        role="tabpanel"
        id={`export-panel-${tab.key}`}
        aria-labelledby={`export-tab-${tab.key}`}
        className="stack-4"
      >
        <Card accentTop>
          <CardHead
            title={
              <span className="row gap-3 wrap">
                <span>{tab.label}</span>
                <span className="badge" style={{ alignSelf: "center" }}>
                  {tab.standard}
                </span>
              </span>
            }
            desc={tab.purpose}
          />
          <CardBody flush>
            <div className="stack-4">
              {/* Honest capability note — sits ABOVE the payload on purpose. */}
              <div className={`alert ${tab.noteTone}`} role="note">
                <div className="alert-body">
                  <p className="alert-title">{tab.noteTitle}</p>
                  <p className="alert-desc">{tab.note}</p>
                </div>
              </div>

              {error ? (
                <div className="alert destructive" role="alert">
                  <div className="alert-body">
                    <p className="alert-title">Couldn’t load {tab.file}</p>
                    <p className="alert-desc">{error}</p>
                  </div>
                </div>
              ) : json === null ? (
                <div className="box dashed" aria-busy="true">
                  <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
                    Loading {tab.file}…
                  </p>
                </div>
              ) : (
                <CodeBlock
                  key={tab.key}
                  code={json}
                  language="json"
                  label={`${tab.standard} · ${tab.file}`}
                  downloadName={tab.file}
                  copyable
                  maxHeight="32rem"
                />
              )}
            </div>
          </CardBody>
        </Card>
      </div>
    </section>
  );
}
