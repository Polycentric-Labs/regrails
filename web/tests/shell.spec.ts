import { expect, test } from "@playwright/test";

/**
 * B0.3 app-shell smoke (DAST). Verifies the foundation the parallel route
 * agents build on: the nav rail renders all 10 destinations, every route is
 * reachable without a router error, and the theme toggle flips <html>'s
 * data-theme + .dark class (persisted).
 */

const ROUTE_LABELS = [
  "Live demo",
  "Rules",
  "Coverage",
  "Benchmark",
  "Methodology",
  "Provenance",
  "Exports",
  "MCP",
  "Action",
  "About",
];

test("nav rail renders all 10 destinations", async ({ page }) => {
  await page.goto("/");
  const navLinks = page.locator("nav.nav-rail a");
  await expect(navLinks).toHaveCount(10);
  for (const label of ROUTE_LABELS) {
    await expect(
      page.locator("nav.nav-rail a", { hasText: label }),
    ).toBeVisible();
  }
});

test("theme toggle flips the document theme attribute and class", async ({
  page,
}) => {
  await page.goto("/");
  const html = page.locator("html");

  const initial = await html.getAttribute("data-theme");
  expect(initial === "light" || initial === "dark").toBeTruthy();

  await page.getByTestId("theme-toggle").click();

  const flipped = initial === "dark" ? "light" : "dark";
  await expect(html).toHaveAttribute("data-theme", flipped);
  if (flipped === "dark") {
    await expect(html).toHaveClass(/dark/);
  } else {
    await expect(html).not.toHaveClass(/dark/);
  }

  // Persistence: the choice survives a reload (localStorage + no-FOUC script).
  await page.reload();
  await expect(html).toHaveAttribute("data-theme", flipped);
});

test("all 10 routes are reachable with no page error", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (e) => pageErrors.push(String(e)));

  const paths = [
    "/",
    "/rules",
    "/coverage",
    "/benchmark",
    "/methodology",
    "/provenance",
    "/exports",
    "/mcp",
    "/action",
    "/about",
  ];

  for (const path of paths) {
    await page.goto(path);
    // Each placeholder renders a single <h1> page title.
    await expect(page.locator("main h1")).toBeVisible();
  }

  expect(pageErrors, `unexpected page errors: ${pageErrors.join("; ")}`).toEqual(
    [],
  );
});
