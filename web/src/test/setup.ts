// Vitest global setup. Adds @testing-library/jest-dom matchers (toBeInTheDocument,
// toHaveStyle, …) and auto-cleans the DOM between tests.
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});
