import { Link } from "@tanstack/react-router";
import { useI18n } from "../i18n";

const VIEWS = [
  { to: "/wealth/projection", label: "projectionSimulator" },
  { to: "/wealth/projection/retirement", label: "wealthRetirement" },
] as const;

/** The projection's sub-tabs: the simulator and the retirement plan built on its savings. */
export function ProjectionTabs() {
  const { t } = useI18n();
  return (
    <nav aria-label={t.nav.projectionViews} className="flex gap-1 overflow-x-auto">
      {VIEWS.map(({ to, label }) => (
        <Link
          key={to}
          to={to}
          activeOptions={{ exact: true }}
          className="rounded-full px-3 py-1 text-sm font-medium whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-accent"
          activeProps={{ className: "bg-accent text-surface", "aria-current": "page" }}
          inactiveProps={{ className: "text-muted hover:text-fg" }}
        >
          {t.nav[label]}
        </Link>
      ))}
    </nav>
  );
}
