/**
 * `/provenance` — Provenance & Audit (PLACEHOLDER). Owned by task B3.6: a
 * hash-chain explainer + a live audit-log verifier (paste a log → /api/verify;
 * tamper with it → watch the chain fail).
 */
export default function Provenance() {
  return (
    <section className="page" data-route="provenance">
      <h1 className="page-title">Provenance</h1>
      <p className="page-sub">
        Tamper-evident hash-chained decision logs. (Route scaffold — verifier
        lands in B3.6.)
      </p>
    </section>
  );
}
