import { expect, test } from "@playwright/test";

/**
 * B3.4 Benchmark route (DAST). Drives the real /benchmark page against the
 * production build serving the real /data/eval.json (no mock). Verifies the
 * three load-bearing parts of the honest evaluation story:
 *   1. all four evaluated models are named,
 *   2. the Disagreements section surfaces the ho-07 / ho-08 edge cases, and
 *   3. the honest-framing copy (no over-refusal / human gate) is present —
 *      i.e. the page does NOT claim "models leak".
 */

const MODELS = [
  "deepseek/deepseek-v4-pro",
  "google/gemini-3.1-pro-preview",
  "openai/gpt-5.5",
  "x-ai/grok-4.3",
];

test("benchmark route renders without a page error", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (e) => pageErrors.push(String(e)));

  await page.goto("/benchmark");
  await expect(page.locator("main h1")).toHaveText("Benchmark");

  expect(pageErrors, `unexpected page errors: ${pageErrors.join("; ")}`).toEqual(
    [],
  );
});

test("all four evaluated model names appear", async ({ page }) => {
  await page.goto("/benchmark");

  // The per-model figures table lists each full model id verbatim. Wait on the
  // first (the data loads async) so the rest are guaranteed rendered.
  await expect(page.getByText(MODELS[0]!, { exact: true }).first()).toBeVisible();
  for (const model of MODELS) {
    await expect(page.getByText(model, { exact: true }).first()).toBeVisible();
  }
});

test("the Disagreements section lists ho-07 and ho-08", async ({ page }) => {
  await page.goto("/benchmark");

  // Scope to the Disagreements card so we assert the edge cases are surfaced in
  // the honest-framing section specifically (not just somewhere on the page).
  const disagreements = page.locator(".card", {
    has: page.getByRole("heading", { name: /Disagreements/i }),
  });
  await expect(disagreements).toBeVisible();

  // ho-07 / ho-08 each appear in the table (a code chip) and the framing alert;
  // target the disagreements table specifically so the row IDs are unambiguous.
  const table = disagreements.locator(".table-wrap");
  await expect(table.getByText("ho-07", { exact: true })).toBeVisible();
  await expect(table.getByText("ho-08", { exact: true })).toBeVisible();

  // And framed honestly: FERPA-permitted, not a failure/leak.
  await expect(disagreements).toContainText(/FERPA-permitted/i);
});

test("the honest-framing copy (no over-refusal / human gate) is present", async ({
  page,
}) => {
  await page.goto("/benchmark");

  // The finding is consistency + no over-refusal + the human gate — NOT a claim
  // that the models leak. Either phrase satisfies the requirement; assert both.
  await expect(page.getByText(/over-refus/i).first()).toBeVisible();
  await expect(page.getByText(/human gate/i).first()).toBeVisible();
});
