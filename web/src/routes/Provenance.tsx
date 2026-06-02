/**
 * `/provenance` — Provenance & Audit (B3.6).
 *
 * Tamper-evidence, made tangible. Every decision the engine writes is appended
 * to a hash-chained log: each record stores the previous record's hash plus its
 * own `record_hash = SHA-256(prev_hash + canonical(decision))`. Because each
 * link folds in the one before it, editing, reordering, or deleting ANY record
 * silently rewrites every hash downstream — so a single pass over the chain
 * proves the whole history is intact (or pinpoints exactly where it broke).
 *
 * The page: (1) explains the chain with the live sample's own hashes; (2) loads
 * the real 3-record sample into an editable textarea; (3) verifies it via
 * /api/verify (the same regrails.audit code the CLI uses) and renders an
 * intact/green or broken/red panel with the engine's `problems` list; and
 * (4) a "Tamper a record" button that flips one character so a re-verify fails
 * — letting a visitor feel the chain catch the edit.
 *
 * Security note: untrusted log text only ever reaches the DOM as React text
 * children (never innerHTML), and the textarea content is POSTed verbatim to
 * the server verifier — the SPA never recomputes hashes client-side.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ChangeEvent } from "react";
import { ApiError, verify, type VerifyResponse } from "../lib/api";
import { Card, CardBody, CardHead } from "../ui/Card";
import { Button } from "../ui/Button";
import { CodeBlock } from "../ui/CodeBlock";
import { Badge } from "../ui/Badge";

/** Public path of the real, valid 3-record sample chain (served statically). */
const SAMPLE_URL = "/data/provenance-sample.jsonl";

/** Fallback sample used only if the static fetch fails (keeps the page usable). */
const FALLBACK_SAMPLE = [
  '{"prev_hash":"0000000000000000000000000000000000000000000000000000000000000000","record_hash":"4081aa1e9767f8c6e2f4419ca550c25fb329c2e8ba2ac206c78873e923ccbc08","decision":{"id":"demo-1","outcome":"allow","framework":"FERPA","risk_tier":"low","query":"What are the library hours tonight?"}}',
  '{"prev_hash":"4081aa1e9767f8c6e2f4419ca550c25fb329c2e8ba2ac206c78873e923ccbc08","record_hash":"dac20f034c03683e4fc379b61ba4ca629b6277ba902b0b0d8735270d1a548b50","decision":{"id":"demo-2","outcome":"escalate_human_review","framework":"Title IV","risk_tier":"high","query":"I defaulted on a loan; am I still eligible for aid?"}}',
  '{"prev_hash":"dac20f034c03683e4fc379b61ba4ca629b6277ba902b0b0d8735270d1a548b50","record_hash":"d75763cf9d08e76870b06dc738062d92522a4f1318a3757ae646336dc168e71a","decision":{"id":"demo-3","outcome":"block","framework":"FERPA","risk_tier":"medium","query":"Email me Jane Doe full transcript."}}',
].join("\n");

/** A parsed JSONL record, only the fields we surface in the explainer. */
interface ChainRecord {
  prev_hash?: string;
  record_hash?: string;
  decision?: { id?: string; outcome?: string };
}

type VerifyState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ok"; result: VerifyResponse }
  | { kind: "broken"; result: VerifyResponse }
  | { kind: "error"; message: string };

/** Shorten a 64-char hash for inline display: `4081aa1e…23ccbc08`. */
function shortHash(h: string | undefined): string {
  if (!h) return "—";
  if (/^0+$/.test(h)) return "genesis (all-zero)";
  return h.length > 18 ? `${h.slice(0, 8)}…${h.slice(-8)}` : h;
}

/** Best-effort parse of JSONL into records (ignores blank/garbled lines). */
function parseChain(text: string): ChainRecord[] {
  const out: ChainRecord[] = [];
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      out.push(JSON.parse(trimmed) as ChainRecord);
    } catch {
      // A tampered/partial line won't parse — skip it for the *preview* only.
      // The authoritative check is the server verifier on the raw text.
    }
  }
  return out;
}

/**
 * Tamper transform: flip exactly one hex character inside a record's
 * `record_hash`, leaving everything else byte-identical. We target the SECOND
 * record's hash so the break lands mid-chain (record index 1 = "demo-2"),
 * matching the canonical demo. The swap is deterministic and idempotent — a
 * `0→1` / `1→0` toggle on the first nibble of that hash — so repeated clicks
 * don't keep mutating new characters.
 */
function tamperLog(text: string): { next: string; changed: boolean } {
  const lines = text.split("\n");
  // Find the line carrying demo-2 (fall back to the 2nd non-empty line).
  let target = lines.findIndex((l) => l.includes('"id":"demo-2"'));
  if (target < 0) {
    const nonEmpty = lines
      .map((l, i) => ({ l, i }))
      .filter((x) => x.l.trim().length > 0);
    target = nonEmpty[1]?.i ?? nonEmpty[0]?.i ?? -1;
  }
  // `noUncheckedIndexedAccess` makes lines[target] possibly-undefined; narrow it.
  const original = target >= 0 ? lines[target] : undefined;
  if (original === undefined) return { next: text, changed: false };

  // Flip the first hex digit of that line's record_hash value.
  let mutated = original.replace(
    /("record_hash":")([0-9a-f])/,
    (_m, head: string, first: string) => `${head}${first === "0" ? "1" : "0"}`,
  );
  if (mutated === original) {
    // No record_hash on that line (unexpected) — nudge the trailing hex char so
    // *something* changes and the re-verify still fails.
    mutated = original.replace(
      /([0-9a-f])([",}\s]*)$/,
      (_m, c: string, tail: string) => `${c === "0" ? "1" : "0"}${tail}`,
    );
  }
  if (mutated === original) return { next: text, changed: false };

  lines[target] = mutated;
  return { next: lines.join("\n"), changed: true };
}

export default function Provenance() {
  const [log, setLog] = useState<string>("");
  const [loadedSample, setLoadedSample] = useState<boolean>(false);
  const [state, setState] = useState<VerifyState>({ kind: "idle" });
  const [tampered, setTampered] = useState<boolean>(false);

  // Prefill the textarea by fetching the real static sample chain.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch(SAMPLE_URL, { headers: { accept: "text/plain" } });
        const text = res.ok ? (await res.text()).trim() : FALLBACK_SAMPLE;
        if (!cancelled) {
          setLog(text || FALLBACK_SAMPLE);
          setLoadedSample(true);
        }
      } catch {
        if (!cancelled) {
          setLog(FALLBACK_SAMPLE);
          setLoadedSample(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const records = useMemo(() => parseChain(log), [log]);

  const onVerify = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const result = await verify(log);
      setState({ kind: result.ok ? "ok" : "broken", result });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Verification request failed.";
      setState({ kind: "error", message });
    }
  }, [log]);

  const onTamper = useCallback(() => {
    setLog((current) => {
      const { next, changed } = tamperLog(current);
      if (changed) {
        setTampered(true);
        // Invalidate any prior "intact" verdict — the chain just changed.
        setState({ kind: "idle" });
      }
      return next;
    });
  }, []);

  const restoreSample = useCallback(() => {
    void (async () => {
      try {
        const res = await fetch(SAMPLE_URL, { headers: { accept: "text/plain" } });
        const text = res.ok ? (await res.text()).trim() : FALLBACK_SAMPLE;
        setLog(text || FALLBACK_SAMPLE);
      } catch {
        setLog(FALLBACK_SAMPLE);
      }
      setTampered(false);
      setState({ kind: "idle" });
    })();
  }, []);

  const onTextareaChange = useCallback(
    (e: ChangeEvent<HTMLTextAreaElement>) => {
      setLog(e.target.value);
      // Editing by hand also invalidates the last verdict.
      setState({ kind: "idle" });
    },
    [],
  );

  return (
    <section className="page" data-route="provenance">
      <header className="stack-2">
        <div className="row gap-3 wrap">
          <h1 className="page-title">Provenance &amp; Audit</h1>
          <Badge color="var(--outcome-escalate-human)" dot>
            tamper-evident
          </Badge>
        </div>
        <p className="page-sub">
          Every guardrail decision is appended to a hash-chained log. Verify the
          sample below, then tamper with one record and watch the chain catch
          the edit — the same check the <code className="code-chip">regrails
          audit verify</code> CLI runs.
        </p>
      </header>

      <div className="stack-5" style={{ marginTop: "1.5rem" }}>
        {/* ── How the chain works ─────────────────────────────────────── */}
        <Card accentTop>
          <CardHead
            title="How the hash chain works"
            desc="Each record commits to the one before it, so the log is append-only and any after-the-fact edit is detectable."
          />
          <CardBody flush>
            <div className="stack-4">
              <ol className="prov-steps">
                <li>
                  <span className="prov-step-n">1</span>
                  <div>
                    <strong>Canonicalize.</strong> The decision object is
                    serialized deterministically — same bytes every time,
                    regardless of key order.
                  </div>
                </li>
                <li>
                  <span className="prov-step-n">2</span>
                  <div>
                    <strong>Link.</strong> Compute{" "}
                    <code className="code-chip">
                      record_hash = SHA-256(prev_hash + canonical(decision))
                    </code>{" "}
                    — the new hash folds in the previous record&apos;s hash.
                  </div>
                </li>
                <li>
                  <span className="prov-step-n">3</span>
                  <div>
                    <strong>Append.</strong> The first record points at a
                    genesis hash of all zeros; every record after it points at
                    its predecessor&apos;s <code className="code-chip">record_hash</code>.
                  </div>
                </li>
                <li>
                  <span className="prov-step-n">4</span>
                  <div>
                    <strong>Verify.</strong> Re-derive each hash and confirm
                    every link matches. Editing, reordering, or deleting{" "}
                    <em>any</em> record changes its hash and breaks every link
                    downstream.
                  </div>
                </li>
              </ol>

              {records.length > 0 && (
                <div className="prov-chain" aria-label="hash chain visualization">
                  {records.map((r, i) => {
                    const id = r.decision?.id ?? `record ${i}`;
                    const outcome = r.decision?.outcome ?? "—";
                    const isGenesisPrev = !!r.prev_hash && /^0+$/.test(r.prev_hash);
                    return (
                      <div className="prov-node-wrap" key={`${id}-${i}`}>
                        {i > 0 && (
                          <div className="prov-link" aria-hidden="true">
                            <span className="prov-link-line" />
                            <span className="prov-link-label">prev_hash</span>
                          </div>
                        )}
                        <div className="prov-node">
                          <div className="row-between gap-2">
                            <span className="prov-node-id mono">{id}</span>
                            <Badge color="var(--outcome-out-of-scope)" capitalize>
                              {String(outcome).replace(/_/g, " ")}
                            </Badge>
                          </div>
                          <dl className="prov-node-hashes">
                            <div>
                              <dt>prev</dt>
                              <dd className="mono" title={r.prev_hash}>
                                {isGenesisPrev ? "genesis (00…00)" : shortHash(r.prev_hash)}
                              </dd>
                            </div>
                            <div>
                              <dt>hash</dt>
                              <dd className="mono" title={r.record_hash}>
                                {shortHash(r.record_hash)}
                              </dd>
                            </div>
                          </dl>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </CardBody>
        </Card>

        {/* ── Verifier ────────────────────────────────────────────────── */}
        <Card>
          <CardHead
            title="Verify a decision log"
            desc="Paste a JSONL hash-chain (one record per line) or use the prefilled sample, then verify it server-side."
          >
            <div className="row gap-2 wrap" style={{ marginTop: "0.2rem" }}>
              {tampered ? (
                <Badge color="var(--outcome-block)" dot>
                  edited — chain expected to break
                </Badge>
              ) : loadedSample ? (
                <Badge color="var(--outcome-allow)" dot>
                  sample loaded ({records.length}-record chain)
                </Badge>
              ) : (
                <span className="muted" style={{ fontSize: "0.8rem" }}>
                  loading sample…
                </span>
              )}
            </div>
          </CardHead>
          <CardBody flush>
            <div className="stack-3">
              <label className="label" htmlFor="prov-log">
                Decision log (JSONL)
              </label>
              <textarea
                id="prov-log"
                className="textarea mono"
                data-testid="prov-log"
                spellCheck={false}
                rows={9}
                value={log}
                onChange={onTextareaChange}
                style={{ fontSize: "0.74rem", lineHeight: 1.55, minHeight: "9rem" }}
                aria-label="Hash-chained decision log to verify"
              />

              <div className="row gap-2 wrap">
                <Button
                  onClick={() => void onVerify()}
                  disabled={state.kind === "loading" || !log.trim()}
                  data-testid="prov-verify"
                >
                  {state.kind === "loading" ? "Verifying…" : "Verify chain"}
                </Button>
                <Button
                  variant="outline"
                  onClick={onTamper}
                  disabled={!log.trim()}
                  data-testid="prov-tamper"
                  title="Flip one character in the second record's hash"
                >
                  Tamper a record
                </Button>
                <Button
                  variant="ghost"
                  onClick={restoreSample}
                  data-testid="prov-restore"
                >
                  Restore sample
                </Button>
              </div>

              <VerifyResult state={state} />
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Page-scoped styles for the explainer + chain visualization. */}
      <ProvenanceStyles />
    </section>
  );
}

/** The result panel — green "intact", red "broken", or a transport error. */
function VerifyResult({ state }: { state: VerifyState }) {
  if (state.kind === "idle") {
    return (
      <div className="box dashed" data-testid="prov-result-idle">
        <span className="muted" style={{ fontSize: "0.85rem" }}>
          Not yet verified. Click <strong>Verify chain</strong> to check every
          link against its hash.
        </span>
      </div>
    );
  }

  if (state.kind === "loading") {
    return (
      <div className="box" data-testid="prov-result-loading">
        <span className="muted" style={{ fontSize: "0.85rem" }}>
          Re-deriving hashes and checking each link…
        </span>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="alert warning" role="alert" data-testid="prov-result-error">
        <div className="alert-body">
          <p className="alert-title">Could not verify</p>
          <p className="alert-desc">{state.message}</p>
        </div>
      </div>
    );
  }

  const { result } = state;
  const intact = state.kind === "ok";

  return (
    <div
      className={intact ? "alert success" : "alert destructive"}
      role="status"
      data-testid="prov-result"
      data-chain={intact ? "intact" : "broken"}
    >
      <div className="alert-body stack-3">
        <div className="row-between gap-2 wrap">
          <p className="alert-title">
            {intact
              ? "Chain intact — every link verified"
              : "Chain broken — tamper detected"}
          </p>
          <Badge
            color={intact ? "var(--outcome-allow)" : "var(--outcome-block)"}
            solid
          >
            {intact ? "VERIFIED" : "FAILED"}
          </Badge>
        </div>

        {intact ? (
          <p className="alert-desc" data-testid="prov-ok-detail">
            Every record hash-chains cleanly: each{" "}
            <code className="code-chip">record_hash</code> re-derives from its
            predecessor and matches the stored value. No edits, reorders, or
            deletions detected.
          </p>
        ) : (
          <div className="stack-2" data-testid="prov-broken-detail">
            <p className="alert-desc">
              The verifier re-derived the hashes and found a mismatch. The
              record listed below (and every record after it) no longer matches
              its stored hash:
            </p>
            <ul className="prov-problems">
              {result.problems.length === 0 ? (
                <li className="mono">chain verification failed</li>
              ) : (
                result.problems.map((p, i) => (
                  <li className="mono" key={i} data-testid="prov-problem">
                    {p}
                  </li>
                ))
              )}
            </ul>
            <p className="alert-desc faint" style={{ marginTop: "0.2rem" }}>
              That is the whole point: a single altered byte is mathematically
              unhideable. Click <strong>Restore sample</strong> to reset.
            </p>
          </div>
        )}

        {result.problems.length > 0 && !intact && (
          <CodeBlock
            code={result.problems.join("\n")}
            label="problems"
            language="text"
            copyable
          />
        )}
      </div>
    </div>
  );
}

/** Scoped CSS for the explainer + chain — kept here so the route is self-contained. */
function ProvenanceStyles() {
  return (
    <style>{`
      .prov-steps { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.7rem; }
      .prov-steps li { display: flex; gap: 0.7rem; align-items: flex-start; font-size: 0.88rem; line-height: 1.5; }
      .prov-steps li strong { font-weight: 600; }
      .prov-step-n {
        flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center;
        width: 1.5rem; height: 1.5rem; border-radius: 999px; font-size: 0.78rem; font-weight: 600;
        font-family: var(--font-mono);
        background: hsl(var(--accent)); color: hsl(var(--accent-fg));
        border: 1px solid hsl(var(--primary) / 0.25);
      }
      .prov-chain { display: flex; flex-direction: column; gap: 0; padding-top: 0.3rem; }
      .prov-node-wrap { display: flex; flex-direction: column; }
      .prov-node {
        border: 1px solid hsl(var(--border)); border-radius: var(--radius);
        background: hsl(var(--surface-2) / 0.5); padding: 0.7rem 0.85rem;
        display: flex; flex-direction: column; gap: 0.5rem;
      }
      .prov-node-id { font-size: 0.82rem; font-weight: 600; color: hsl(var(--fg)); }
      .prov-node-hashes { display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem 1.1rem; margin: 0; }
      @media (max-width: 560px) { .prov-node-hashes { grid-template-columns: 1fr; } }
      .prov-node-hashes div { display: flex; flex-direction: column; gap: 0.1rem; min-width: 0; }
      .prov-node-hashes dt {
        font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.07em;
        font-weight: 600; color: hsl(var(--fg-muted));
      }
      .prov-node-hashes dd { margin: 0; font-size: 0.74rem; color: hsl(var(--fg)); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .prov-link { display: flex; flex-direction: column; align-items: center; height: 1.6rem; position: relative; }
      .prov-link-line { width: 2px; flex: 1; background: linear-gradient(hsl(var(--primary) / 0.55), hsl(var(--primary) / 0.55)); margin: 0.15rem 0; }
      .prov-link-label {
        position: absolute; left: calc(50% + 0.55rem); top: 50%; transform: translateY(-50%);
        font-size: 0.6rem; font-family: var(--font-mono); color: hsl(var(--fg-faint));
        letter-spacing: 0.03em; white-space: nowrap;
      }
      .prov-problems { margin: 0; padding-left: 1.1rem; display: grid; gap: 0.3rem; }
      .prov-problems li { font-size: 0.78rem; line-height: 1.45; color: hsl(var(--destructive)); word-break: break-word; }
      .dark .prov-problems li { color: hsl(var(--destructive)); }
    `}</style>
  );
}
