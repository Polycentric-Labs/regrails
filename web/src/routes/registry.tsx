import type { ComponentType } from "react";
import Demo from "./Demo";
import Rules from "./Rules";
import Coverage from "./Coverage";
import Benchmark from "./Benchmark";
import Methodology from "./Methodology";
import Provenance from "./Provenance";
import Exports from "./Exports";
import Mcp from "./Mcp";
import Action from "./Action";
import About from "./About";

export interface RouteDef {
  /** Router path. */
  path: string;
  /** Nav-rail label. */
  label: string;
  /** Short descriptor (nav tooltip / future use). */
  blurb: string;
  /** The page component. */
  element: ComponentType;
}

/**
 * THE single source of truth for the 10 destinations. Both App.tsx (router) and
 * NavRail (links) read this list, so a later agent fills in a route by editing
 * only its own routes/<Name>.tsx file — never App.tsx. To add/remove a
 * destination, edit this array alone.
 *
 * Order here is the nav-rail order.
 */
export const ROUTES: RouteDef[] = [
  { path: "/", label: "Live demo", blurb: "Engine decides before any LLM", element: Demo },
  { path: "/rules", label: "Rules", blurb: "37 rules · FERPA + Title IV", element: Rules },
  { path: "/coverage", label: "Coverage", blurb: "31/37 mapped · 6 gaps", element: Coverage },
  { path: "/benchmark", label: "Benchmark", blurb: "Held-out eval", element: Benchmark },
  { path: "/methodology", label: "Methodology", blurb: "Scope + limitations", element: Methodology },
  { path: "/provenance", label: "Provenance", blurb: "Hash-chain audit", element: Provenance },
  { path: "/exports", label: "Exports", blurb: "OSCAL + SARIF", element: Exports },
  { path: "/mcp", label: "MCP", blurb: "3 agent tools", element: Mcp },
  { path: "/action", label: "Action", blurb: "Gate your pipeline", element: Action },
  { path: "/about", label: "About", blurb: "Thesis + links", element: About },
];
