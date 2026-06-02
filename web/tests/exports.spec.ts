import { expect, test } from "@playwright/test";

/**
 * B3.7 Exports route (DAST). Drives the real production build via `vite preview`
 * against the actual generated payloads (web/public/data/{oscal,sarif}.json) —
 * no mocks. Verifies the two-tab OSCAL | SARIF viewer:
 *   1. OSCAL is the default tab: its <CodeBlock> shows the real catalog JSON
 *      (contains the "1.1.2" oscal-version) AND the honest "not NIST-validated"
 *      capability note is on screen.
 *   2. Switching to SARIF shows the real SARIF JSON (contains the "2.1.0"
 *      schema version).
 *   3. A Download button exists (CodeBlock's Blob→<a download> trigger).
 */

test("OSCAL tab shows the catalog JSON and the honest NIST note", async ({
  page,
}) => {
  await page.goto("/exports");

  // The route renders without a router/page error.
  await expect(page.locator("main h1")).toHaveText("Exports");

  // OSCAL is the default tab — its tab trigger is selected.
  await expect(page.getByRole("tab", { name: /OSCAL/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );

  // The rendered code panel contains the real OSCAL version string.
  const code = page.locator("pre.block code");
  await expect(code).toBeVisible();
  await expect(code).toContainText("1.1.2");

  // The honest capability cap is on screen (case-insensitive: the UI emphasizes
  // "NOT NIST-validated").
  await expect(page.locator('[role="tabpanel"]')).toContainText(
    /not NIST-validated/i,
  );
});

test("switching to the SARIF tab shows the SARIF 2.1.0 JSON", async ({
  page,
}) => {
  await page.goto("/exports");

  await page.getByRole("tab", { name: /SARIF/ }).click();

  await expect(page.getByRole("tab", { name: /SARIF/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );

  const code = page.locator("pre.block code");
  await expect(code).toBeVisible();
  await expect(code).toContainText("2.1.0");
});

test("a Download button exists on the exports view", async ({ page }) => {
  await page.goto("/exports");

  // Wait for the payload (and thus the CodeBlock action bar) to render.
  await expect(page.locator("pre.block code")).toBeVisible();

  await expect(
    page.getByRole("button", { name: "Download" }),
  ).toBeVisible();
});
