import { NavLink } from "react-router-dom";
import { ROUTES } from "../routes/registry";

/**
 * Deep-navy brand nav rail (Evidentia chrome). Lists all 10 destinations from
 * the route registry — the single source of truth — so adding a route never
 * touches this file. NavLink supplies the active-state styling.
 */
export function NavRail() {
  return (
    <nav className="nav-rail" aria-label="Primary">
      <div className="nav-brand">
        <span className="nav-brand-mark" aria-hidden="true">
          RR
        </span>
        <span className="stack">
          <span className="nav-brand-name">RegRails</span>
          <span className="nav-brand-sub">policy-as-code guardrail</span>
        </span>
      </div>

      <ul className="nav-list">
        {ROUTES.map((r) => (
          <li key={r.path}>
            <NavLink
              to={r.path}
              end={r.path === "/"}
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
              title={r.blurb}
            >
              <span className="nav-dot" aria-hidden="true" />
              {r.label}
            </NavLink>
          </li>
        ))}
      </ul>

      <div className="nav-foot">
        <code>pip install regrails</code>
      </div>
    </nav>
  );
}

export default NavRail;
