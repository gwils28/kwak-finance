import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { Link, Outlet, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { logout, updateMe } from "./api/generated";
import { meQuery } from "./auth/session";
import { Footer } from "./components/Footer";
import { LanguageSelect } from "./components/LanguageSelect";
import { ThemeToggle } from "./components/ThemeToggle";
import { Button } from "./components/ui";
import { useI18n } from "./i18n";

const NAV_LINK = "rounded-md px-2 py-1 text-sm hover:text-accent";
const ACTIVE = { className: "text-accent" };

/** Header shared by every signed-in page. */
export function AppLayout() {
  const { data: user } = useSuspenseQuery(meQuery);
  const { t, language, setLanguage } = useI18n();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

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
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-3">
          <nav className="flex flex-wrap items-center gap-4">
            <Link to="/" className="text-xl font-black tracking-tight">
              {t.common.appName}
            </Link>
            <Link to="/accounts" className={NAV_LINK} activeProps={ACTIVE}>
              {t.nav.accounts}
            </Link>
            <Link to="/transactions" className={NAV_LINK} activeProps={ACTIVE}>
              {t.nav.transactions}
            </Link>
            <Link to="/budget" className={NAV_LINK} activeProps={ACTIVE}>
              {t.nav.budget}
            </Link>
            <Link to="/categories" className={NAV_LINK} activeProps={ACTIVE}>
              {t.nav.categories}
            </Link>
            <Link to="/members" className={NAV_LINK} activeProps={ACTIVE}>
              {t.nav.members}
            </Link>
          </nav>
          <div className="flex items-center gap-3">
            <span className="text-sm">{user.display_name}</span>
            <LanguageSelect onChange={saveLanguage} />
            <ThemeToggle />
            <Button variant="ghost" onClick={signOut}>
              {t.common.signOut}
            </Button>
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
