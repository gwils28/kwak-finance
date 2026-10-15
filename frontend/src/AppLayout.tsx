import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { Link, Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect } from "react";
import { logout, updateMe } from "./api/generated";
import { meQuery } from "./auth/session";
import { AccountMenu } from "./components/AccountMenu";
import { Footer } from "./components/Footer";
import { Icon } from "./components/icons";
import { Logo } from "./components/Logo";
import { useI18n } from "./i18n";

/**
 * The overview, a summary of the whole app, then two spaces with their tabs: spending (the
 * everyday pages) and wealth, apart since it is followed monthly rather than daily. A new page
 * adds its tab to its space.
 */
const SPACES = {
  spending: [
    { to: "/accounts", label: "accounts", exact: false },
    { to: "/transactions", label: "transactions", exact: false },
    { to: "/budget", label: "budget", exact: false },
    { to: "/reports", label: "reports", exact: false },
  ],
  wealth: [
    { to: "/wealth", label: "wealthTracking", exact: true },
    { to: "/wealth/analysis", label: "wealthAnalysis", exact: false },
  ],
} as const;

type Space = keyof typeof SPACES;

/** Where each switch leads: the overview, or a space's most used page. */
const SWITCH = [
  { key: "overview", to: "/", label: "overview" },
  { key: "spending", to: "/transactions", label: "spending" },
  { key: "wealth", to: "/wealth", label: "wealth" },
] as const;

const SPENDING_PAGES = [
  "/accounts",
  "/transactions",
  "/recurring",
  "/budget",
  "/reports",
  "/categories",
];

/** The overview, a space, or neither for the household pages (members, activity, guide). */
function placeOf(pathname: string): Space | "overview" | null {
  if (pathname === "/") return "overview";
  const under = (root: string) => pathname === root || pathname.startsWith(`${root}/`);
  if (under("/wealth")) return "wealth";
  return SPENDING_PAGES.some(under) ? "spending" : null;
}

const SPACE =
  "rounded-full px-3 py-1 text-sm font-medium whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-accent";

const TAB =
  "flex shrink-0 items-center border-b-2 py-3 text-sm font-medium whitespace-nowrap hover:text-fg md:py-0";

/** Header shared by every signed-in page. */
export function AppLayout() {
  const { data: user } = useSuspenseQuery(meQuery);
  const { t, language, setLanguage } = useI18n();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const place = placeOf(pathname);

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
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 border-b border-border bg-surface/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 px-4 md:h-14 md:flex-nowrap">
          <Link
            to="/"
            className="flex h-14 items-center gap-2 font-display text-xl font-black tracking-tight"
          >
            <Logo />
            {t.common.appName}
          </Link>
          <nav
            aria-label={t.nav.spacesLabel}
            className="flex items-center gap-1 rounded-full border border-border p-0.5"
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
          {(place === "spending" || place === "wealth") && (
            <nav
              aria-label={t.nav.mainLabel}
              className="-mx-4 order-last flex w-[calc(100%+2rem)] gap-6 self-stretch overflow-x-auto border-t border-border px-4 md:order-none md:mx-0 md:w-auto md:border-t-0 md:px-0"
            >
              {SPACES[place].map(({ to, label, exact }) => (
                <Link
                  key={to}
                  to={to}
                  activeOptions={{ exact }}
                  className={TAB}
                  activeProps={{ className: "border-accent text-fg" }}
                  inactiveProps={{ className: "border-transparent text-muted" }}
                >
                  {t.nav[label]}
                </Link>
              ))}
            </nav>
          )}
          <div className="ml-auto flex items-center gap-3">
            <Link
              to="/guide"
              className="flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm hover:text-accent"
              activeProps={{ className: "text-accent" }}
              inactiveProps={{ className: "text-muted" }}
            >
              <Icon name="help" className="size-5" />
              <span className="hidden sm:inline">{t.nav.guide}</span>
            </Link>
            <span aria-hidden="true" className="h-6 w-px bg-border" />
            <AccountMenu
              name={user.display_name}
              email={user.email}
              onLanguageChange={saveLanguage}
              onSignOut={signOut}
            />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
