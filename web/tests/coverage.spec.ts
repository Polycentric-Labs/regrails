import { expect, test } from "@playwright/test";

/**
 * B3.3 Coverage route (DAST). Drives the production build against the REAL
 * /data/coverage.json (no mock) and verifies the credibility story renders:
 * the 31/37 headline stat and one card per documented gap (the 6 uncovered
 * rule IDs). Mirrors shell.spec.ts: real navigation, no network stubbing.
 */

// The 6 known gaps in data/coverage.json (rules with zero golden scenarios).
const GAP_IDS = [
  "FERPA-99.30-3",
  "FERPA-99.31-A3",
  "FERPA-99.31-A4",
  "FERPA-99.31-A9",
  "FERPA-99.33-A2",
  "FERPA-99.36-B1",
];

test("renders the 31 / 37 coverage headline", async ({ page }) => {
  await page.goto("/coverage");

  // The page title proves the route mounted (matches the shell smoke).
  await expect(page.locator("main h1")).toHaveText("Coverage");

  // Headline stat: both the covered count and the total are visible.
  await expect(page.getByText("31", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("37", { exact: false }).first()).toBeVisible();
});

test("renders one card per documented gap (6 gaps)", async ({ page }) => {
  await page.goto("/coverage");

  // The "Known gaps (6)" heading reflects the data's n_gaps.
  await expect(
    page.getByRole("heading", { name: /Known gaps \(6\)/ }),
  ).toBeVisible();

  // Exactly 6 gap cards render…
  const gapCards = page.locator("[data-gap-id]");
  await expect(gapCards).toHaveCount(6);

  // …and each known gap rule ID is present.
  for (const id of GAP_IDS) {
    await expect(page.locator(`[data-gap-id="${id}"]`)).toBeVisible();
    await expect(
      page.locator(`[data-gap-id="${id}"]`).getByText(id),
    ).toBeVisible();
  }
});

test("coverage route loads with no page error", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (e) => pageErrors.push(String(e)));

  await page.goto("/coverage");
  await expect(page.locator("main h1")).toBeVisible();

  expect(pageErrors, `unexpected page errors: ${pageErrors.join("; ")}`).toEqual(
    [],
  );
});
