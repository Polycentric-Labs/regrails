import { expect, test } from "@playwright/test";

/**
 * B3.5 Methodology & Limitations (DAST). Drives the real /methodology route
 * against the real /data/methodology.json (no mock) and asserts the credibility-
 * critical framing is actually legible on the page: the "not legal advice"
 * boundary and the "faithfulness" gate must both render as visible text.
 */

test("methodology page renders the document title and section nav", async ({
  page,
}) => {
  await page.goto("/methodology");

  // The page title comes from the loaded document (title: "RegRails — …").
  await expect(page.locator("main h1")).toBeVisible();

  // The section TOC and the rendered sections come from the JSON, not a mock.
  await expect(page.locator("nav.methodology-toc")).toBeVisible();
  await expect(
    page.locator("section[data-route='methodology'] article.methodology-section").first(),
  ).toBeVisible();
});

test("methodology states the legal boundary and the faithfulness limit", async ({
  page,
}) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (e) => pageErrors.push(String(e)));

  await page.goto("/methodology");

  // Scope the assertions to the routed content (not the global shell banner),
  // so the strings must come from the rendered methodology document itself.
  const main = page.locator("section[data-route='methodology']");

  // "not legal advice" — case-insensitive; present in the lede + the Overview body.
  await expect(
    main.getByText(/not legal advice/i).first(),
  ).toBeVisible();

  // "faithfulness" — the verbatim-text gate that is NOT semantic correctness.
  await expect(main.getByText(/faithfulness/i).first()).toBeVisible();

  expect(
    pageErrors,
    `unexpected page errors: ${pageErrors.join("; ")}`,
  ).toEqual([]);
});
