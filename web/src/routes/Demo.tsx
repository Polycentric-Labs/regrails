/**
 * `/` — Live demo (PLACEHOLDER).
 *
 * Owned by task B3.1: a consult form → engine DecisionCard (via /api/decide) →
 * optional engine-gated LLM reply (via /api/reply) with guarded/unguarded
 * contrast. Filled in by a later agent; App.tsx already routes here.
 */
export default function Demo() {
  return (
    <section className="page" data-route="demo">
      <h1 className="page-title">Live demo</h1>
      <p className="page-sub">
        The deterministic engine decides before any LLM speaks. (Route scaffold —
        consult form and decision card land in B3.1.)
      </p>
    </section>
  );
}
