/**
 * `/methodology` — Methodology & Limitations (B3.5). The credibility centerpiece:
 * it states what RegRails does, what it does NOT do, and how every number is
 * re-derivable. Renders data/methodology.json (the dumped METHODOLOGY.md +
 * COVERAGE.md surfaces) with a sticky section TOC and well-typeset prose.
 *
 * SAFETY: body_md is rendered as React TEXT NODES only — never via raw-HTML
 * injection. A small block + inline parser walks the markdown into React
 * elements — paragraphs, `- ` bullets, `1.` ordered lists, pipe tables, fenced
 * ``` code, `> ` quotes, `### ` sub-headings — and the inline pass splits on
 * backticks / ** / _ / links into <code>/<strong>/<em>/<a> text nodes. Untrusted
 * regulatory text therefore can never inject markup. (Same posture as ui/CodeBlock
 * + ui/Card, which bind content through children, not raw HTML.)
 */
import {
  Fragment,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { loadData } from "../lib/data";
import { Card, CardBody, CardHead } from "../ui/Card";
import Button from "../ui/Button";

/* ── Data shape (data/methodology.json) ───────────────────────────────── */

interface MethodologySection {
  heading: string;
  body_md: string;
  /** Origin doc — "METHODOLOGY.md" (the narrative) or "COVERAGE.md" (appendix). */
  source?: string;
}
interface MethodologyDoc {
  title: string;
  sections: MethodologySection[];
}

/* ── Slugs / anchors ──────────────────────────────────────────────────── */

/** GitHub-flavoured-ish slug so in-doc `#anchor` links resolve to our headings. */
function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

/* ── Inline markdown → React (text nodes only, no raw-HTML injection) ───── */

/**
 * Render an inline string: `code`, **bold**, *italic* or _italic_, and
 * [text](href) links — everything else is a plain text node. Internal `#anchor`
 * links become same-page jumps; relative repo links (e.g. COVERAGE.md) render as
 * a non-navigating code chip so a SPA deep-link never 404s but the reference
 * stays legible. Parsing is a single left-to-right scan over a small token set.
 */
function renderInline(text: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = [];
  let buf = "";
  let k = 0;
  const pushText = () => {
    if (buf) {
      out.push(<Fragment key={`${keyBase}-t${k++}`}>{buf}</Fragment>);
      buf = "";
    }
  };

  for (let i = 0; i < text.length; ) {
    const ch = text[i]!;

    // Inline code: `...` (highest precedence — contents are literal).
    if (ch === "`") {
      const end = text.indexOf("`", i + 1);
      if (end > i) {
        pushText();
        out.push(
          <code key={`${keyBase}-c${k++}`} className="code-chip">
            {text.slice(i + 1, end)}
          </code>,
        );
        i = end + 1;
        continue;
      }
    }

    // Link: [label](href)
    if (ch === "[") {
      const close = text.indexOf("]", i + 1);
      if (close > i && text[close + 1] === "(") {
        const hrefEnd = text.indexOf(")", close + 2);
        if (hrefEnd > close) {
          const label = text.slice(i + 1, close);
          const href = text.slice(close + 2, hrefEnd).trim();
          pushText();
          if (href.startsWith("#")) {
            // In-document anchor — smooth-jump within the page.
            out.push(
              <a
                key={`${keyBase}-l${k++}`}
                href={href}
                className="primary-link"
                onClick={(e) => {
                  e.preventDefault();
                  const el = document.getElementById(href.slice(1));
                  if (el)
                    el.scrollIntoView({ behavior: "smooth", block: "start" });
                }}
              >
                {renderInline(label, `${keyBase}-l${k}`)}
              </a>,
            );
          } else if (/^https?:\/\//.test(href)) {
            out.push(
              <a
                key={`${keyBase}-l${k++}`}
                href={href}
                className="primary-link"
                target="_blank"
                rel="noreferrer noopener"
              >
                {renderInline(label, `${keyBase}-l${k}`)}
              </a>,
            );
          } else {
            // Relative repo path (COVERAGE.md, ../src/…): show the label as a
            // chip — no nav, no 404, still a visible pointer to the file.
            out.push(
              <code
                key={`${keyBase}-r${k++}`}
                className="code-chip"
                title={href}
              >
                {label.replace(/^`(.*)`$/, "$1")}
              </code>,
            );
          }
          i = hrefEnd + 1;
          continue;
        }
      }
    }

    // Bold: **...**
    if (ch === "*" && text[i + 1] === "*") {
      const end = text.indexOf("**", i + 2);
      if (end > i) {
        pushText();
        out.push(
          <strong key={`${keyBase}-b${k++}`}>
            {renderInline(text.slice(i + 2, end), `${keyBase}-b${k}`)}
          </strong>,
        );
        i = end + 2;
        continue;
      }
    }

    // Italic: *...* or _..._ (single delimiter, not part of a ** run).
    if ((ch === "*" || ch === "_") && text[i + 1] !== ch) {
      const end = text.indexOf(ch, i + 1);
      if (end > i && text[end - 1] !== " ") {
        pushText();
        out.push(
          <em key={`${keyBase}-i${k++}`}>
            {renderInline(text.slice(i + 1, end), `${keyBase}-i${k}`)}
          </em>,
        );
        i = end + 1;
        continue;
      }
    }

    buf += ch;
    i += 1;
  }
  pushText();
  return out;
}

/* ── Block markdown → React ───────────────────────────────────────────── */

type Block =
  | { kind: "h3"; text: string }
  | { kind: "p"; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "quote"; text: string }
  | { kind: "code"; lang: string; text: string }
  | { kind: "table"; header: string[]; rows: string[][] };

/** Split a pipe-table row "| a | b |" into trimmed cells. */
function splitRow(line: string): string[] {
  let s = line.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|")) s = s.slice(0, -1);
  return s.split("|").map((c) => c.trim());
}
const isTableDivider = (line: string): boolean =>
  /^\s*\|?[\s:-]*-[\s:|-]*\|?\s*$/.test(line) && line.includes("-");

/** Parse one section's body_md into a flat list of blocks. */
function parseBlocks(md: string): Block[] {
  const lines = md.split("\n");
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i] ?? "";
    const trimmed = line.trim();

    if (trimmed === "") {
      i += 1;
      continue;
    }

    // Fenced code: ```lang … ```
    if (trimmed.startsWith("```")) {
      const lang = trimmed.slice(3).trim();
      const body: string[] = [];
      i += 1;
      while (i < lines.length && !(lines[i] ?? "").trim().startsWith("```")) {
        body.push(lines[i] ?? "");
        i += 1;
      }
      i += 1; // consume closing fence
      blocks.push({ kind: "code", lang, text: body.join("\n") });
      continue;
    }

    // Sub-heading: ### …
    if (trimmed.startsWith("### ")) {
      blocks.push({ kind: "h3", text: trimmed.slice(4).trim() });
      i += 1;
      continue;
    }

    // Pipe table: a header row immediately followed by a divider row.
    if (
      trimmed.startsWith("|") &&
      i + 1 < lines.length &&
      isTableDivider(lines[i + 1] ?? "")
    ) {
      const header = splitRow(line);
      i += 2; // header + divider
      const rows: string[][] = [];
      while (i < lines.length && (lines[i] ?? "").trim().startsWith("|")) {
        rows.push(splitRow(lines[i] ?? ""));
        i += 1;
      }
      blocks.push({ kind: "table", header, rows });
      continue;
    }

    // Blockquote: > … (one or more consecutive lines).
    if (trimmed.startsWith(">")) {
      const parts: string[] = [];
      while (i < lines.length && (lines[i] ?? "").trim().startsWith(">")) {
        parts.push((lines[i] ?? "").trim().replace(/^>\s?/, ""));
        i += 1;
      }
      blocks.push({ kind: "quote", text: parts.join(" ") });
      continue;
    }

    // Unordered list: "- " items (continuation lines are indented).
    if (/^[-*]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length) {
        const cur = lines[i] ?? "";
        const curTrim = cur.trim();
        if (/^[-*]\s+/.test(curTrim)) {
          items.push(curTrim.replace(/^[-*]\s+/, ""));
          i += 1;
        } else if (curTrim !== "" && /^\s/.test(cur) && items.length) {
          // Wrapped continuation of the previous bullet.
          const last = items[items.length - 1];
          if (last !== undefined) items[items.length - 1] = `${last} ${curTrim}`;
          i += 1;
        } else {
          break;
        }
      }
      blocks.push({ kind: "ul", items });
      continue;
    }

    // Ordered list: "1. " items.
    if (/^\d+\.\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length) {
        const cur = lines[i] ?? "";
        const curTrim = cur.trim();
        if (/^\d+\.\s+/.test(curTrim)) {
          items.push(curTrim.replace(/^\d+\.\s+/, ""));
          i += 1;
        } else if (curTrim !== "" && /^\s/.test(cur) && items.length) {
          const last = items[items.length - 1];
          if (last !== undefined) items[items.length - 1] = `${last} ${curTrim}`;
          i += 1;
        } else {
          break;
        }
      }
      blocks.push({ kind: "ol", items });
      continue;
    }

    // Paragraph: gather until a blank line or the start of another block.
    const para: string[] = [];
    while (i < lines.length) {
      const cur = (lines[i] ?? "").trim();
      if (
        cur === "" ||
        cur.startsWith("```") ||
        cur.startsWith("### ") ||
        cur.startsWith(">") ||
        /^[-*]\s+/.test(cur) ||
        /^\d+\.\s+/.test(cur) ||
        (cur.startsWith("|") && isTableDivider(lines[i + 1] ?? ""))
      ) {
        break;
      }
      para.push(cur);
      i += 1;
    }
    blocks.push({ kind: "p", text: para.join(" ") });
  }

  return blocks;
}

/** Render parsed blocks for one section. */
function Markdown({ md }: { md: string }): ReactNode {
  const blocks = useMemo(() => parseBlocks(md), [md]);
  return (
    <div className="prose">
      {blocks.map((b, bi) => {
        const key = `b${bi}`;
        switch (b.kind) {
          case "h3":
            return (
              <h4 className="prose-h4" key={key}>
                {renderInline(b.text, key)}
              </h4>
            );
          case "p":
            return <p key={key}>{renderInline(b.text, key)}</p>;
          case "ul":
            return (
              <ul key={key}>
                {b.items.map((it, ii) => (
                  <li key={`${key}-${ii}`}>{renderInline(it, `${key}-${ii}`)}</li>
                ))}
              </ul>
            );
          case "ol":
            return (
              <ol key={key}>
                {b.items.map((it, ii) => (
                  <li key={`${key}-${ii}`}>{renderInline(it, `${key}-${ii}`)}</li>
                ))}
              </ol>
            );
          case "quote":
            return (
              <blockquote key={key} className="prose-quote">
                {renderInline(b.text, key)}
              </blockquote>
            );
          case "code":
            return (
              <pre className="block" key={key}>
                <code>{b.text}</code>
              </pre>
            );
          case "table":
            return (
              <div className="table-wrap" key={key}>
                <table className="tbl">
                  <thead>
                    <tr>
                      {b.header.map((h, hi) => (
                        <th key={`${key}-h${hi}`}>{renderInline(h, `${key}-h${hi}`)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {b.rows.map((row, ri) => (
                      <tr key={`${key}-r${ri}`}>
                        {b.header.map((_, ci) => (
                          <td key={`${key}-r${ri}-c${ci}`}>
                            {renderInline(row[ci] ?? "", `${key}-r${ri}-c${ci}`)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          default:
            return null;
        }
      })}
    </div>
  );
}

/* ── TOC / scroll-spy ─────────────────────────────────────────────────── */

interface TocEntry {
  id: string;
  heading: string;
  source: string;
}

function useScrollSpy(ids: string[]): string | null {
  const [active, setActive] = useState<string | null>(ids[0] ?? null);
  useEffect(() => {
    if (ids.length === 0) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]?.target.id) setActive(visible[0].target.id);
      },
      // Trip a section "active" once its heading nears the top of the viewport.
      { rootMargin: "-12% 0px -78% 0px", threshold: 0 },
    );
    for (const id of ids) {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, [ids]);
  return active;
}

/* ── Route ────────────────────────────────────────────────────────────── */

export default function Methodology() {
  const [doc, setDoc] = useState<MethodologyDoc | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    loadData<MethodologyDoc>("methodology")
      .then((d) => {
        if (mounted.current) setDoc(d);
      })
      .catch((e: unknown) => {
        if (mounted.current)
          setError(e instanceof Error ? e : new Error(String(e)));
      });
    return () => {
      mounted.current = false;
    };
  }, []);

  // Stable ids per section heading (deduped — both docs start with "Overview").
  const sections = useMemo(() => doc?.sections ?? [], [doc]);
  const toc: TocEntry[] = useMemo(() => {
    const seen = new Map<string, number>();
    return sections.map((s) => {
      const base = slugify(s.heading) || "section";
      const n = seen.get(base) ?? 0;
      seen.set(base, n + 1);
      return {
        id: n === 0 ? base : `${base}-${n}`,
        heading: s.heading,
        source: s.source ?? "METHODOLOGY.md",
      };
    });
  }, [sections]);

  const activeId = useScrollSpy(toc.map((t) => t.id));

  if (error) {
    return (
      <section className="page" data-route="methodology">
        <h1 className="page-title">Methodology &amp; limitations</h1>
        <div className="alert destructive" style={{ marginTop: "1rem" }}>
          <div className="alert-body">
            <p className="alert-title">Couldn&apos;t load the methodology document</p>
            <p className="alert-desc">{error.message}</p>
          </div>
        </div>
      </section>
    );
  }

  if (!doc) {
    return (
      <section className="page" data-route="methodology">
        <h1 className="page-title">Methodology &amp; limitations</h1>
        <p className="page-sub">Loading the methodology document…</p>
      </section>
    );
  }

  // Group the TOC by origin doc so COVERAGE.md reads as a labelled appendix.
  const methodologyToc = toc.filter((t) => t.source === "METHODOLOGY.md");
  const appendixToc = toc.filter((t) => t.source !== "METHODOLOGY.md");

  return (
    <section className="page methodology" data-route="methodology">
      <header className="stack-2">
        <h1 className="page-title">{doc.title}</h1>
        <p className="page-sub">
          Written to be checked, not believed. Every number below is the number
          the tooling produces; the commands to reproduce each one are in the
          Reproducibility section. This is a proof-of-concept — not legal advice,
          not a compliance certification, and not production software.
        </p>
      </header>

      {/* Honest-framing pull-out — the three load-bearing caveats up front. */}
      <Card variant="dest" accentTop className="methodology-caveat">
        <CardHead title="Read this first" />
        <CardBody flush>
          <ul className="caveat-list">
            <li>
              <strong>Not legal advice.</strong> RegRails produces auditable
              guardrails and escalation paths — it is not a statement that any
              institution is &ldquo;compliant,&rdquo; and not a substitute for
              review by a FERPA or financial-aid officer.
            </li>
            <li>
              <strong>Faithfulness&nbsp;&ne;&nbsp;semantic correctness.</strong>{" "}
              The faithfulness gate proves the quoted words are verbatim CFR text.
              It says nothing about whether the encoded legal reading is{" "}
              <em>correct</em>. A rule can quote the statute perfectly and still
              map to the wrong outcome.
            </li>
            <li>
              <strong>Subset coverage, stated openly.</strong> Only 8 CFR sections
              are encoded, and only 31 of 37 rules have a golden scenario — the 6
              uncovered rules are listed, not hidden.
            </li>
          </ul>
        </CardBody>
      </Card>

      <div className="methodology-layout">
        {/* Sticky section navigation / table of contents. */}
        <nav className="methodology-toc" aria-label="Methodology sections">
          <p className="toc-eyebrow">On this page</p>
          <ol className="toc-list">
            {methodologyToc.map((t) => (
              <li key={t.id}>
                <a
                  href={`#${t.id}`}
                  className={`toc-link${activeId === t.id ? " active" : ""}`}
                  aria-current={activeId === t.id ? "true" : undefined}
                  onClick={(e) => {
                    e.preventDefault();
                    document
                      .getElementById(t.id)
                      ?.scrollIntoView({ behavior: "smooth", block: "start" });
                  }}
                >
                  {t.heading}
                </a>
              </li>
            ))}
          </ol>
          {appendixToc.length > 0 && (
            <>
              <p className="toc-eyebrow toc-eyebrow-2">Appendix · COVERAGE.md</p>
              <ol className="toc-list">
                {appendixToc.map((t) => (
                  <li key={t.id}>
                    <a
                      href={`#${t.id}`}
                      className={`toc-link${activeId === t.id ? " active" : ""}`}
                      aria-current={activeId === t.id ? "true" : undefined}
                      onClick={(e) => {
                        e.preventDefault();
                        document
                          .getElementById(t.id)
                          ?.scrollIntoView({ behavior: "smooth", block: "start" });
                      }}
                    >
                      {t.heading}
                    </a>
                  </li>
                ))}
              </ol>
            </>
          )}
        </nav>

        {/* The document body. */}
        <div className="methodology-body stack-5">
          {sections.map((s, si) => {
            const entry = toc[si]!;
            const isAppendix = entry.source !== "METHODOLOGY.md";
            const prevSource = si > 0 ? sections[si - 1]?.source : undefined;
            return (
              <article
                key={entry.id}
                id={entry.id}
                className="methodology-section"
                data-source={entry.source}
              >
                {isAppendix && prevSource === "METHODOLOGY.md" && (
                  <p className="appendix-banner">
                    Appendix · generated from{" "}
                    <code className="code-chip">COVERAGE.md</code> (the same
                    rule&rarr;scenario matrix shown on the Coverage page)
                  </p>
                )}
                <h2 className="section-heading">{s.heading}</h2>
                <Markdown md={s.body_md} />
              </article>
            );
          })}

          <footer className="methodology-foot">
            <p className="muted">
              Source: <code className="code-chip">METHODOLOGY.md</code> +{" "}
              <code className="code-chip">COVERAGE.md</code>, dumped verbatim from
              the installed package by the anti-drift data pipeline. Nothing on
              this page is recomputed in the browser.
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            >
              Back to top
            </Button>
          </footer>
        </div>
      </div>

      {/* Scoped typography for the rendered document. Uses design tokens only. */}
      <style>{METHODOLOGY_CSS}</style>
    </section>
  );
}

/* ── Scoped prose styling (design-token driven; no new globals) ───────── */

const METHODOLOGY_CSS = `
.methodology .methodology-caveat { margin-top: 1.3rem; }
.methodology .caveat-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.7rem; }
.methodology .caveat-list li { position: relative; padding-left: 1.15rem; font-size: 0.92rem; line-height: 1.55; color: hsl(var(--fg)); }
.methodology .caveat-list li::before { content: ""; position: absolute; left: 0; top: 0.55rem; width: 0.42rem; height: 0.42rem; border-radius: 999px; background: hsl(var(--destructive)); }
.methodology .caveat-list strong { color: hsl(var(--fg)); }

.methodology .methodology-layout { display: grid; grid-template-columns: 232px minmax(0, 1fr); gap: 2.2rem; margin-top: 1.8rem; align-items: start; }
@media (max-width: 940px) { .methodology .methodology-layout { grid-template-columns: 1fr; gap: 1.3rem; } }

.methodology .methodology-toc { position: sticky; top: 4.4rem; align-self: start; }
@media (max-width: 940px) {
  .methodology .methodology-toc { position: static; border: 1px solid hsl(var(--border)); border-radius: var(--radius); padding: 0.9rem 1rem; background: hsl(var(--surface)); }
}
.methodology .toc-eyebrow { font-size: 0.68rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: hsl(var(--fg-muted)); margin: 0 0 0.5rem; }
.methodology .toc-eyebrow-2 { margin-top: 1.1rem; padding-top: 0.9rem; border-top: 1px solid hsl(var(--border)); }
.methodology .toc-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.05rem; }
.methodology .toc-link { display: block; padding: 0.32rem 0.6rem; border-radius: var(--radius-sm-px); font-size: 0.82rem; line-height: 1.35; color: hsl(var(--fg-muted)); border-left: 2px solid transparent; text-decoration: none; transition: color .12s, background-color .12s, border-color .12s; }
.methodology .toc-link:hover { color: hsl(var(--fg)); background: hsl(var(--accent) / 0.5); text-decoration: none; }
.methodology .toc-link.active { color: hsl(var(--primary)); border-left-color: hsl(var(--primary)); background: hsl(var(--accent) / 0.6); font-weight: 600; }

.methodology .methodology-section { scroll-margin-top: 4.4rem; }
.methodology .section-heading { font-size: 1.28rem; font-weight: 600; letter-spacing: -0.015em; line-height: 1.25; margin: 0 0 0.85rem; padding-bottom: 0.55rem; border-bottom: 1px solid hsl(var(--border)); color: hsl(var(--fg)); }
.methodology .appendix-banner { font-size: 0.78rem; color: hsl(var(--fg-muted)); background: hsl(var(--surface-2)); border: 1px solid hsl(var(--border)); border-radius: var(--radius-sm-px); padding: 0.45rem 0.7rem; margin: 0 0 1rem; }

/* Prose — measured line length + the IBM Plex stack for readability. */
.methodology .prose { max-width: 72ch; }
.methodology .prose p { margin: 0 0 0.95rem; font-size: 0.95rem; line-height: 1.7; color: hsl(var(--fg)); }
.methodology .prose p:last-child { margin-bottom: 0; }
.methodology .prose ul, .methodology .prose ol { margin: 0 0 1rem; padding-left: 1.35rem; }
.methodology .prose li { margin: 0.3rem 0; font-size: 0.95rem; line-height: 1.65; color: hsl(var(--fg)); }
.methodology .prose li::marker { color: hsl(var(--fg-muted)); }
.methodology .prose-h4 { font-size: 1.0rem; font-weight: 600; letter-spacing: -0.01em; margin: 1.4rem 0 0.6rem; color: hsl(var(--fg)); }
.methodology .prose-quote { margin: 0 0 1rem; padding: 0.7rem 1rem; border-left: 3px solid hsl(var(--primary)); background: hsl(var(--accent) / 0.45); border-radius: 0 var(--radius-sm-px) var(--radius-sm-px) 0; font-size: 0.95rem; line-height: 1.6; color: hsl(var(--fg)); }
.methodology .prose-quote strong { color: hsl(var(--primary)); }
.methodology .prose .code-chip { font-size: 0.82em; }
.methodology .prose pre.block { margin: 0 0 1rem; max-width: 100%; }
.methodology .prose .table-wrap { margin: 0 0 1rem; max-width: 100%; }
.methodology .prose .tbl td { font-size: 0.82rem; line-height: 1.5; vertical-align: top; }
.methodology .prose .tbl td .code-chip { white-space: nowrap; }

.methodology .methodology-foot { margin-top: 2rem; padding-top: 1.2rem; border-top: 1px solid hsl(var(--border)); display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
.methodology .methodology-foot .muted { font-size: 0.82rem; line-height: 1.6; margin: 0; max-width: 64ch; }
`;
