import { expect, test } from "@playwright/test";

/**
 * B3.6 Provenance & Audit (DAST). Drives the hash-chain verifier end to end
 * against a MOCKED /api/verify so the e2e is hermetic (no Python function, no
 * real SHA-256): the first verify returns an intact chain; after the user taps
 * "Tamper a record", the second verify returns a broken chain + one problem
 * line. We also stub the static /data/provenance-sample.jsonl fetch so the
 * textarea is prefilled deterministically regardless of the built asset.
 *
 * Mirrors shell.spec.ts conventions (import shape, page.goto, locators).
 */

// A small but VALID-looking 3-record chain. The real hashes don't matter here —
// /api/verify is mocked — but the shape mirrors the production sample so the
// page's preview parsing and the tamper transform behave realistically.
const SAMPLE_JSONL = [
  '{"prev_hash":"0000000000000000000000000000000000000000000000000000000000000000","record_hash":"4081aa1e9767f8c6e2f4419ca550c25fb329c2e8ba2ac206c78873e923ccbc08","decision":{"id":"demo-1","outcome":"allow","framework":"FERPA","risk_tier":"low","query":"What are the library hours tonight?"}}',
  '{"prev_hash":"4081aa1e9767f8c6e2f4419ca550c25fb329c2e8ba2ac206c78873e923ccbc08","record_hash":"dac20f034c03683e4fc379b61ba4ca629b6277ba902b0b0d8735270d1a548b50","decision":{"id":"demo-2","outcome":"escalate_human_review","framework":"Title IV","risk_tier":"high","query":"I defaulted on a loan; am I still eligible for aid?"}}',
  '{"prev_hash":"dac20f034c03683e4fc379b61ba4ca629b6277ba902b0b0d8735270d1a548b50","record_hash":"d75763cf9d08e76870b06dc738062d92522a4f1318a3757ae646336dc168e71a","decision":{"id":"demo-3","outcome":"block","framework":"FERPA","risk_tier":"medium","query":"Email me Jane Doe full transcript."}}',
].join("\n");

const BROKEN_PROBLEM =
  "record 1 (demo-2): record_hash mismatch — decision content was altered after writing";

test.beforeEach(async ({ page }) => {
  // Stub the static sample so the textarea is prefilled deterministically.
  await page.route("**/data/provenance-sample.jsonl", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/plain; charset=utf-8",
      body: SAMPLE_JSONL,
    });
  });

  // Mock the serverless verifier: 1st call → intact, every call after → broken.
  let verifyCalls = 0;
  await page.route("**/api/verify", async (route) => {
    verifyCalls += 1;
    const body =
      verifyCalls === 1
        ? { ok: true, problems: [] }
        : { ok: false, problems: [BROKEN_PROBLEM] };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
});

test("verifying the sample chain renders the intact / green state", async ({
  page,
}) => {
  await page.goto("/provenance");

  // The page title renders (route is reachable).
  await expect(page.locator("main h1")).toHaveText(/Provenance/i);

  // Textarea was prefilled from the stubbed sample.
  const textarea = page.getByTestId("prov-log");
  await expect(textarea).toHaveValue(/demo-1/);
  await expect(textarea).toHaveValue(/demo-2/);

  // Verify → intact/green panel.
  await page.getByTestId("prov-verify").click();

  const result = page.getByTestId("prov-result");
  await expect(result).toBeVisible();
  await expect(result).toHaveAttribute("data-chain", "intact");
  await expect(result).toContainText(/chain intact/i);
  await expect(result).toContainText(/VERIFIED/);

  // No tamper problem lines in the intact state.
  await expect(page.getByTestId("prov-problem")).toHaveCount(0);
});

test("tampering a record then re-verifying renders the broken / red state with a problem line", async ({
  page,
}) => {
  await page.goto("/provenance");

  const textarea = page.getByTestId("prov-log");
  await expect(textarea).toHaveValue(/demo-2/);
  const original = await textarea.inputValue();

  // First verify establishes the intact baseline.
  await page.getByTestId("prov-verify").click();
  await expect(page.getByTestId("prov-result")).toHaveAttribute(
    "data-chain",
    "intact",
  );

  // Tamper mutates the log text (one character flips in a record hash).
  await page.getByTestId("prov-tamper").click();
  const tampered = await textarea.inputValue();
  expect(tampered).not.toEqual(original);
  expect(tampered.length).toEqual(original.length); // single-char swap, not append

  // Re-verify → broken/red panel + the problem line.
  await page.getByTestId("prov-verify").click();

  const result = page.getByTestId("prov-result");
  await expect(result).toBeVisible();
  await expect(result).toHaveAttribute("data-chain", "broken");
  await expect(result).toContainText(/chain broken/i);
  await expect(result).toContainText(/FAILED/);

  // The mocked problem line is rendered.
  const problems = page.getByTestId("prov-problem");
  await expect(problems).toHaveCount(1);
  await expect(problems.first()).toContainText("record 1 (demo-2)");
  await expect(problems.first()).toContainText("record_hash mismatch");
});
