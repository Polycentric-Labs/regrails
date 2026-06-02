import { useLocation } from "react-router-dom";
import { ROUTES } from "../routes/registry";
import ThemeToggle from "./ThemeToggle";

const GITHUB_URL = "https://github.com/Polycentric-Labs/regrails";
const PYPI_URL = "https://pypi.org/project/regrails/";

/**
 * Top bar (deep-navy chrome): the current route's title on the left; the theme
 * toggle + outbound GitHub / PyPI links on the right.
 */
export function TopBar() {
  const { pathname } = useLocation();
  const current =
    ROUTES.find((r) => r.path === pathname) ??
    ROUTES.find((r) => r.path !== "/" && pathname.startsWith(r.path)) ??
    ROUTES[0];
  const title = current ? current.label : "RegRails";

  return (
    <header className="topbar">
      <div className="topbar-title">{title}</div>
      <div className="topbar-actions">
        <a
          className="topbar-link"
          href={GITHUB_URL}
          target="_blank"
          rel="noreferrer noopener"
        >
          GitHub
        </a>
        <a
          className="topbar-link"
          href={PYPI_URL}
          target="_blank"
          rel="noreferrer noopener"
        >
          PyPI
        </a>
        <ThemeToggle />
      </div>
    </header>
  );
}

export default TopBar;
