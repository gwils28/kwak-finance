import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { Link, Outlet, useNavigate } from "@tanstack/react-router";
import { logout } from "./api/generated";
import { meQuery } from "./auth/session";
import { ThemeToggle } from "./components/ThemeToggle";
import { Button } from "./components/ui";

const NAV_LINK = "rounded-md px-2 py-1 text-sm hover:text-accent";

/** Header shared by every signed-in page. */
export function AppLayout() {
  const { data: user } = useSuspenseQuery(meQuery);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const signOut = async () => {
    await logout();
    queryClient.clear();
    await navigate({ to: "/login" });
  };

  return (
    <div className="min-h-screen">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <nav className="flex items-center gap-4">
            <Link to="/" className="text-xl font-black tracking-tight">
              Kwak Finance
            </Link>
            <Link to="/accounts" className={NAV_LINK} activeProps={{ className: "text-accent" }}>
              Accounts
            </Link>
            <Link
              to="/transactions"
              className={NAV_LINK}
              activeProps={{ className: "text-accent" }}
            >
              Transactions
            </Link>
            <Link to="/budget" className={NAV_LINK} activeProps={{ className: "text-accent" }}>
              Budget
            </Link>
            <Link to="/categories" className={NAV_LINK} activeProps={{ className: "text-accent" }}>
              Categories
            </Link>
            <Link to="/members" className={NAV_LINK} activeProps={{ className: "text-accent" }}>
              Members
            </Link>
          </nav>
          <div className="flex items-center gap-3">
            <span className="text-sm">{user.display_name}</span>
            <ThemeToggle />
            <Button variant="ghost" onClick={signOut}>
              Sign out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-10">
        <Outlet />
      </main>
    </div>
  );
}
