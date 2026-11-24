import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { Link, Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect } from "react";
import { showHousehold } from "./api/client";
import { logout, updateMe } from "./api/generated";
import { meQuery } from "./auth/session";
import { AccountMenu } from "./components/AccountMenu";
import { DemoBanner, useDemoSwitch } from "./components/DemoBanner";
import { Footer } from "./components/Footer";
import { Icon } from "./components/icons";
import { Logo } from "./components/Logo";
import { useI18n } from "./i18n";

/**
 * Three spaces, each with its tabs: spending (the everyday pages), wealth, apart since it is
 * followed monthly rather than daily, and goals. The overview, a summary of the whole app, is the app's
 * name; the household pages (accounts, categories, members…) are in the account menu. A new
 * page adds its tab to its space. The tabs sit on a bar of their own under the header, at every
 * width, so a space with many tabs never squeezes the header.
 */
const SPACES = {
  spending: [
    { to: "/spending", label: "lines", exact: false },
    { to: "/budget", label: "budget", exact: false },
    { to: "/reports", label: "reports", exact: false },
    { to: "/forecast", label: "forecast", exact: false },
  ],
  wealth: [
    { to: "/wealth", label: "wealthTracking", exact: true },
    { to: "/wealth/analysis", label: "wealthAnalysis", exact: false },
    { to: "/wealth/projection", label: "wealthProjection", exact: false },
    { to: "/wealth/retirement", label: "wealthRetirement", exact: false },
    { to: "/wealth/audit", label: "audit", exact: false },
  ],
  // The pyramid's tab stays marked on each goal's page.
  goals: [
    { to: "/goals", label: "goalsPyramid", exact: false },
    { to: "/goals/analysis", label: "goalsAnalysis", exact: false },
  ],
} as const;

type Space = keyof typeof SPACES;

/** On a phone, the bar at the bottom: the overview, then each space's most used page. */
const PHONE_BAR = [
  { key: null, to: "/", label: "home", icon: "home" },
  { key: "spending", to: "/spending", label: "spending", icon: "wallet" },
  { key: "wealth", to: "/wealth", label: "wealth", icon: "trend" },
  { key: "goals", to: "/goals", label: "goals", icon: "target" },
] as const;

/** Where each switch leads: the space's most used page. */
const SWITCH = [
  { key: "spending", to: "/spending", label: "spending" },
  { key: "wealth", to: "/wealth", label: "wealth" },
  { key: "goals", to: "/goals", label: "goals" },
] as const;

const SPENDING_PAGES = ["/spending", "/budget", "/reports", "/forecast"];

/** The space a page belongs to; none for the overview and the account menu's pages. */
function placeOf(pathname: string): Space | null {
  const under = (root: string) => pathname === root || pathname.startsWith(`${root}/`);
  if (under("/wealth")) return "wealth";
  if (under("/goals")) return "goals";
  if (under("/spending/categories")) return null;
  return SPENDING_PAGES.some(under) ? "spending" : null;
}

/** A tab is marked on its pages (its own only when `exact`), but not on a sibling tab's
 * nested under it. */
function tabHere(to: string, pathname: string, exact: boolean): boolean {
  if (pathname !== to && (exact || !pathname.startsWith(`${to}/`))) return false;
  const siblings = Object.values(SPACES)
    .flat()
    .map((tab) => tab.to as string)
    .filter((other) => other !== to && other.startsWith(`${to}/`));
  return !siblings.some((other) => pathname === other || pathname.startsWith(`${other}/`));
}

const SPACE =
  "rounded-full px-3 py-1 text-sm font-medium whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-accent";

const TAB =
  "flex shrink-0 items-center border-b-2 py-2.5 text-sm font-medium whitespace-nowrap hover:text-fg";

/** Header shared by every signed-in page. */
export function AppLayout() {
  const { data: user } = useSuspenseQuery(meQuery);
  const { t, language, setLanguage } = useI18n();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const place = placeOf(pathname);
  const demo = useDemoSwitch();

  // Every change names the household shown, so a page left in the demo (or out of it) cannot
  // write to the other one.
  useEffect(() => {
    showHousehold(user.household_id);
    return () => showHousehold(null);
  }, [user.household_id]);

  // The account's language wins; with none saved yet, keep the browser's and save it.
  useEffect(() => {
    if (user.language && user.language !== language) setLanguage(user.language);
    if (!user.language) void updateMe({ body: { language } });
  }, [user.language, language, setLanguage]);

  // Update the cache first: the effect above would otherwise switch back until the reply.
  const saveLanguage = async (next: typeof language) => {
    queryClient.setQueryData(meQuery.queryKey, { ...user, language: next });
    await updateMe({ body: { language: next } });
  };

  const signOut = async () => {
    await logout();
    queryClient.clear();
    await navigate({ to: "/login" });
  };

  return (
    // On a phone, room at the bottom for the bar, so it never covers the footer.
    <div className="flex min-h-screen flex-col pb-16 sm:pb-0 print:pb-0">
      {/* Above the tables' sticky headers (z-30), so the account menu opens over them. */}
      <header className="sticky top-0 z-40 print:hidden border-b border-border bg-surface/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-x-4 px-4 lg:gap-x-8">
          <Link
            to="/"
            aria-label={t.common.appName}
            className="flex h-14 shrink-0 items-center gap-2 font-display text-xl font-black tracking-tight whitespace-nowrap"
          >
            <Logo />
            {/* The name only where there is room for it beside the spaces. */}
            <span aria-hidden="true" className="hidden lg:inline">
              {t.common.appName}
            </span>
          </Link>
          <nav
            aria-label={t.nav.spacesLabel}
            // On a phone the spaces are in the bar at the bottom instead.
            className="hidden items-center gap-1 rounded-full border border-border p-0.5 sm:flex"
          >
            {SWITCH.map(({ key, to, label }) => (
              <Link
                key={key}
                to={to}
                aria-current={place === key ? "true" : undefined}
                className={`${SPACE} ${
                  place === key ? "bg-accent text-bg" : "text-muted hover:text-fg"
                }`}
                // The router marks the link "page" on its own page only; elsewhere in the
                // space, the space marks itself.
                activeOptions={{ exact: true }}
              >
                {t.nav[label]}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex shrink-0 items-center gap-3">
            <Link
              to="/guide"
              className="flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm hover:text-accent"
              activeProps={{ className: "text-accent" }}
              inactiveProps={{ className: "text-muted" }}
            >
              <Icon name="help" className="size-5" />
              <span className="hidden lg:inline">{t.nav.guide}</span>
            </Link>
            <span aria-hidden="true" className="h-6 w-px bg-border" />
            <AccountMenu
              name={user.display_name}
              email={user.email}
              inDemo={user.demo}
              onDemo={user.demo ? demo.leave : demo.open}
              onLanguageChange={saveLanguage}
              onSignOut={signOut}
            />
          </div>
        </div>
        {place !== null && (
          <div className="border-t border-border">
            <nav
              aria-label={t.nav.mainLabel}
              className="mx-auto flex max-w-6xl gap-6 overflow-x-auto px-4 [scrollbar-width:none]"
            >
              {SPACES[place].map(({ to, label, exact }) => {
                // The router marks the exact page only; the tab marks itself on its own pages.
                const here = tabHere(to, pathname, exact);
                return (
                  <Link
                    key={to}
                    to={to}
                    activeOptions={{ exact: true }}
                    aria-current={here ? "page" : undefined}
                    className={`${TAB} ${here ? "border-accent text-fg" : "border-transparent text-muted"}`}
                  >
                    {t.nav[label]}
                  </Link>
                );
              })}
            </nav>
          </div>
        )}
      </header>
      {user.demo && <DemoBanner demo={demo} />}
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 print:max-w-none print:p-0">
        <Outlet />
      </main>
      <Footer />
      <nav
        aria-label={t.nav.sectionsLabel}
        className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-border bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur sm:hidden print:hidden"
      >
        {PHONE_BAR.map(({ key, to, label, icon }) => {
          const here = key === null ? pathname === "/" : place === key;
          return (
            <Link
              key={to}
              to={to}
              activeOptions={{ exact: true }}
              aria-current={here ? "true" : undefined}
              className={`flex flex-col items-center gap-0.5 py-2 text-xs font-medium whitespace-nowrap ${
                here ? "text-accent" : "text-muted"
              }`}
            >
              <Icon name={icon} className="size-5" />
              {t.nav[label]}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
