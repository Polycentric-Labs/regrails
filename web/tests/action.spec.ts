import { expect, test } from "@playwright/test";

/**
 * B3.9 /action route smoke (DAST). The GitHub-Action page must render the real
 * composite action: at least one dark code panel (the YAML), and the canonical
 * `uses: Polycentric-Labs/regrails…` usage so a reader can copy the gate verbatim.
 * Mirrors the shell.spec.ts shape (goto → locator → expect, no fixtures).
 */

test("a YAML / code block is present", async ({ page }) => {
  await page.goto("/action");

  // The page renders <h1> first (matches the shell smoke's per-route check).
  await expect(page.locator("main h1")).toBeVisible();

  // CodeBlock renders the YAML into the dark chrome panel `pre.block > code`.
  const blocks = page.locator("pre.block code");
  await expect(blocks.first()).toBeVisible();
  expect(await blocks.count()).toBeGreaterThan(0);
});

test("the canonical uses: Polycentric-Labs/regrails usage appears", async ({
  page,
}) => {
  await page.goto("/action");

  const body = page.locator("body");
  // The action is invoked with a `uses:` line…
  await expect(body).toContainText("uses:");
  // …that references the published RegRails composite action.
  await expect(body).toContainText("Polycentric-Labs/regrails");

  // Both strings co-occur inside a single rendered code panel (the real YAML),
  // not merely scattered across prose.
  const yaml = page
    .locator("pre.block code", { hasText: "Polycentric-Labs/regrails" })
    .first();
  await expect(yaml).toBeVisible();
  await expect(yaml).toContainText("uses:");
});
