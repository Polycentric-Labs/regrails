import { expect, test } from "@playwright/test";

/**
 * B3.2 Rules-browser DAST. Drives the /rules route against the production
 * preview server, which serves the REAL generated /data/rules.json (37 rules
 * across FERPA Subpart D + Title IV). No mocking — these assertions prove the
 * route renders, filters, and expands the live corpus.
 */

test("renders all 37 rules from the live data file", async ({ page }) => {
  await page.goto("/rules");

  // The route title confirms we're on the right page (also the shell's main h1).
  await expect(page.locator("main h1")).toHaveText("Rules");

  // The live shown/total count surfaces 37 with the "All" filter active.
  await expect(page.getByTestId("total-count")).toHaveText("37");
  await expect(page.getByTestId("shown-count")).toHaveText("37");

  // ...and the table actually renders one summary row per rule.
  await expect(page.getByTestId("rule-row")).toHaveCount(37);
});

test("selecting the Title IV filter reduces the visible count", async ({
  page,
}) => {
  await page.goto("/rules");

  // Baseline: everything is shown.
  await expect(page.getByTestId("shown-count")).toHaveText("37");
  const initial = Number(await page.getByTestId("shown-count").innerText());

  // Apply the Title IV framework filter (button label is "Title IV <count>").
  await page.getByRole("button", { name: /^Title IV/ }).click();

  // The count strictly drops (Title IV is a subset of the 37) and only Title IV
  // rows remain on screen.
  await expect(page.getByTestId("shown-count")).not.toHaveText("37");
  const filtered = Number(await page.getByTestId("shown-count").innerText());
  expect(filtered).toBeLessThan(initial);
  expect(filtered).toBeGreaterThan(0);

  const rows = page.getByTestId("rule-row");
  await expect(rows).toHaveCount(filtered);
  const frameworks = await rows.evaluateAll((els) =>
    els.map((el) => el.getAttribute("data-framework")),
  );
  expect(frameworks.every((f) => f === "Title IV")).toBe(true);
});

test("expanding a row reveals the verbatim CFR section text + hash", async ({
  page,
}) => {
  await page.goto("/rules");
  await expect(page.getByTestId("rule-row")).toHaveCount(37);

  // No detail panel is open initially.
  await expect(page.getByTestId("rule-detail-row")).toHaveCount(0);

  // Expand the first rule (FERPA § 99.30 in document order) via its citation.
  await page
    .getByRole("button", { name: /34-CFR-99\.30/ })
    .first()
    .click();

  // The detail row appears with the VERBATIM CFR text (a phrase that only lives
  // in the source section body, not the plain-language summary).
  const detail = page.getByTestId("rule-detail-row");
  await expect(detail).toHaveCount(1);
  await expect(detail).toContainText(
    "Under what conditions is prior consent required to disclose",
  );

  // The pinned section hash is shown as a 64-char hex string (monospace).
  const hash = page.getByTestId("section-hash").first();
  await expect(hash).toBeVisible();
  const hashText = (await hash.innerText()).trim();
  expect(hashText).toMatch(/^[0-9a-f]{64}$/);
});
