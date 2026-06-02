import { expect, test, type Page } from "@playwright/test";

/**
 * B3.1 — the `/` Live demo route. The deterministic engine verdict is THE
 * headline, so these tests pin the contract the route depends on: the engine
 * decision always renders (even when the optional advisor reply 500s), the
 * human-gate flag + CFR citations surface, and each outcome's badge shows.
 *
 * Both API calls are mocked via page.route so the tests never need the Python
 * serverless functions or an LLM key — they assert the SPA's rendering of a
 * known engine response, mirroring web/tests/shell.spec.ts's setup.
 */

/** Fulfill /api/decide with a fixed GuardrailDecision JSON body. */
async function mockDecide(page: Page, decision: Record<string, unknown>) {
  await page.route("**/api/decide", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(decision),
    });
  });
}

const LOAN_DEFAULT_DECISION = {
  id: "test-loan-default",
  query: "I defaulted on a loan; am I still eligible for aid?",
  framework: "Title IV",
  outcome: "escalate_human_review",
  risk_tier: "high",
  human_gate_required: true,
  matched_rules: ["TIV-668.35-A1"],
  citations_emitted: ["Title IV 668.35"],
  llm_response:
    "This is a high-stakes financial-aid determination a human aid officer must make.",
};

const OUT_OF_SCOPE_DECISION = {
  id: "test-oos",
  query: "What time does the library close tonight?",
  framework: "N/A",
  outcome: "out_of_scope",
  risk_tier: "low",
  human_gate_required: false,
  matched_rules: [],
  citations_emitted: [],
  llm_response: "",
};

test("Loan default preset → human gate + Title IV citation surface", async ({
  page,
}) => {
  await mockDecide(page, LOAN_DEFAULT_DECISION);
  await page.goto("/");

  // Tap the preset, then run the engine.
  await page.getByRole("button", { name: "Loan default" }).click();
  await page.getByRole("button", { name: /Consult the guardrail/ }).click();

  // The DecisionCard renders with the escalation outcome (scope the outcome
  // text to the badge region — the word "scope" etc. appears elsewhere on the
  // page, and getByText matches case-insensitive substrings).
  const card = page.getByTestId("decision-title");
  await expect(card).toBeVisible();
  await expect(
    page.getByTestId("decision-badges").getByText("Escalate Human Review"),
  ).toBeVisible();

  // The HUMAN GATE chip is shown for an irreversible determination.
  await expect(page.getByTestId("human-gate")).toBeVisible();
  await expect(page.getByTestId("human-gate")).toContainText(/human gate/i);

  // The Title IV citation is emitted as a code chip inside the citations group.
  const citations = page.getByTestId("citations");
  await expect(citations).toBeVisible();
  await expect(citations).toContainText("Title IV 668.35");
});

test("Out of scope preset → out_of_scope outcome rendered", async ({ page }) => {
  await mockDecide(page, OUT_OF_SCOPE_DECISION);
  await page.goto("/");

  await page.getByRole("button", { name: "Out of scope" }).click();
  await page.getByRole("button", { name: /Consult the guardrail/ }).click();

  await expect(page.getByTestId("decision-title")).toBeVisible();
  await expect(
    page.getByTestId("decision-badges").getByText("Out Of Scope"),
  ).toBeVisible();
  // No human gate for an out-of-scope question.
  await expect(page.getByTestId("human-gate")).toHaveCount(0);
});

test("advisor reply 500s → DecisionCard still renders + unavailable note", async ({
  page,
}) => {
  // The decision succeeds; the optional reply fails hard.
  await mockDecide(page, LOAN_DEFAULT_DECISION);
  await page.route("**/api/reply", async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ error: "reply backend down" }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Loan default" }).click();
  await page.getByRole("button", { name: /Consult the guardrail/ }).click();
  await expect(page.getByTestId("decision-title")).toBeVisible();

  // Ask for the reply; the backend 500s.
  await page.getByRole("button", { name: /Show advisor reply/ }).click();

  // Always-degrade: the engine verdict still stands, and an "unavailable" note
  // is shown instead of a model reply.
  await expect(page.getByTestId("decision-title")).toBeVisible();
  await expect(
    page.getByTestId("decision-badges").getByText("Escalate Human Review"),
  ).toBeVisible();
  await expect(page.getByTestId("reply-unavailable")).toBeVisible();
  await expect(page.getByTestId("reply-unavailable")).toContainText(
    /advisor reply unavailable/i,
  );
  // And no guarded-reply box was rendered.
  await expect(page.getByTestId("guarded-reply")).toHaveCount(0);
});
