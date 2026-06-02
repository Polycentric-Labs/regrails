import { Outlet, Route, Routes } from "react-router-dom";
import NavRail from "./components/NavRail";
import TopBar from "./components/TopBar";
import ErrorBoundary from "./components/ErrorBoundary";
import { ROUTES } from "./routes/registry";

/**
 * App shell: deep-navy nav rail + top bar around the routed outlet. The "demo"
 * banner reinforces the synthetic-data / not-legal-advice framing (spec §5).
 *
 * Routes are registered from ROUTES (the single source of truth), so a later
 * agent fills a route by editing only its routes/<Name>.tsx — never this file.
 * Each route renders inside one ErrorBoundary so a single route crash shows a
 * fallback, not a blank page.
 */
function Shell() {
  return (
    <div className="app-shell">
      <NavRail />
      <div className="main-col">
        <TopBar />
        <div className="banner" role="note">
          Synthetic data only · <b>not legal advice</b> · the engine decides
          before any LLM speaks.
        </div>
        <main>
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}

// Fallback element for unknown paths: the first registered route (the demo).
const Fallback = ROUTES[0]!.element;

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        {ROUTES.map(({ path, element: El }) => (
          <Route key={path} path={path} element={<El />} />
        ))}
        {/* Unknown paths fall back to the demo so a stale deep-link never 404s. */}
        <Route path="*" element={<Fallback />} />
      </Route>
    </Routes>
  );
}
