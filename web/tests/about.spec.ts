import { expect, test } from "@playwright/test";

/**
 * B3.10 About-route DAST. The About page frames the deterministic-guardrail
 * thesis and ties it to the four public artifacts. This spec pins the contract
 * the page must honor: every external destination is reachable as a real
 * anchor, opened in a new, isolated tab.
 *
 * Destinations (must each appear as an <a href>):
 *   - GitHub  · Polycentric-Labs/regrails           (the source)
 *   - PyPI    · regrails                              (the package)
 *   - HuggingFace · Polycentric-Labs/regrails-eval   (the eval dataset)
 *   - GitHub  · Polycentric-Labs/evidentia           (the sibling project)
 */

const REPO = "https://github.com/Polycentric-Labs/regrails";
const PYPI = "https://pypi.org/project/regrails/";
const EVAL = "https://huggingface.co/datasets/Polycentric-Labs/regrails-eval";
const EVIDENTIA = "https://github.com/Polycentric-Labs/evidentia";

test("about route renders its page title", async ({ page }) => {
  await page.goto("/about");
  await expect(page.locator("main h1")).toHaveText(/About/);
});

test("about links to all four destinations", async ({ page }) => {
  await page.goto("/about");

  // One anchor per destination must exist, addressed by its exact href.
  for (const href of [REPO, PYPI, EVAL, EVIDENTIA]) {
    await expect(
      page.locator(`a[href="${href}"]`).first(),
      `expected an <a> linking to ${href}`,
    ).toBeVisible();
  }
});

test("about links to the regrails repo on github", async ({ page }) => {
  await page.goto("/about");
  await expect(page.locator(`a[href="${REPO}"]`).first()).toBeVisible();
});

test("about links to the regrails package on pypi", async ({ page }) => {
  await page.goto("/about");
  await expect(page.locator(`a[href="${PYPI}"]`).first()).toBeVisible();
});

test("about links to the regrails-eval dataset on huggingface", async ({
  page,
}) => {
  await page.goto("/about");
  await expect(page.locator(`a[href="${EVAL}"]`).first()).toBeVisible();
});

test("about links to evidentia on github", async ({ page }) => {
  await page.goto("/about");
  await expect(page.locator(`a[href="${EVIDENTIA}"]`).first()).toBeVisible();
});

test("external about links open in a new tab, safely", async ({ page }) => {
  await page.goto("/about");

  // Every external anchor on the page opens in a new tab with a hardened rel
  // (noreferrer noopener) — no reverse-tabnabbing, no referrer leakage.
  for (const href of [REPO, PYPI, EVAL, EVIDENTIA]) {
    const anchor = page.locator(`a[href="${href}"]`).first();
    await expect(anchor).toHaveAttribute("target", "_blank");
    await expect(anchor).toHaveAttribute("rel", /noopener/);
    await expect(anchor).toHaveAttribute("rel", /noreferrer/);
  }
});

test("about route loads without a page error", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (e) => pageErrors.push(String(e)));

  await page.goto("/about");
  await expect(page.locator("main h1")).toBeVisible();

  expect(
    pageErrors,
    `unexpected page errors: ${pageErrors.join("; ")}`,
  ).toEqual([]);
});
