import { expect, test } from "@playwright/test";

/**
 * `/mcp` — MCP Server route (DAST). Verifies the page documents the three
 * agent-callable tools, shows the recorded consult-before-answer transcript,
 * and keeps the honest "runs locally over stdio / not a hosted service" framing.
 *
 * Source of truth for the asserted strings: src/regrails/mcp_server.py (tool
 * names) and the recorded transcript in src/routes/Mcp.tsx.
 */

const TOOL_NAMES = ["consult_guardrail", "list_rules", "check_faithfulness"];

test("renders the MCP Server page", async ({ page }) => {
  await page.goto("/mcp");
  await expect(page.locator("main h1")).toHaveText("MCP Server");
});

test("all three tool names appear", async ({ page }) => {
  await page.goto("/mcp");
  for (const name of TOOL_NAMES) {
    // Each tool is documented in its own card with the name in a <code> heading;
    // getByText matches at least that occurrence on the page.
    await expect(page.getByText(name).first()).toBeVisible();
  }
});

test("the recorded transcript panel is visible", async ({ page }) => {
  await page.goto("/mcp");
  // The transcript renders inside a CodeBlock (<pre class="block"><code>…) as a
  // single text node. Assert the panel is visible and shows the consult call +
  // the deterministic escalate_human_review result.
  const transcript = page
    .locator("pre.block", { hasText: "Recorded MCP session" })
    .first();
  await expect(transcript).toBeVisible();
  await expect(transcript).toContainText("consult_guardrail");
  await expect(transcript).toContainText("escalate_human_review");
  await expect(transcript).toContainText("human_gate_required");
});

test("the 'runs locally / not hosted' note is present", async ({ page }) => {
  await page.goto("/mcp");
  // The honest framing, as a callout title (contiguous text — not split by any
  // inline element).
  await expect(
    page.getByText("Not a hosted live server", { exact: false }),
  ).toBeVisible();
  // …and the local-only / stdio detail in the note body.
  await expect(
    page.getByText("no public endpoint to call", { exact: false }),
  ).toBeVisible();
  await expect(page.getByText("stdio", { exact: false }).first()).toBeVisible();
});
