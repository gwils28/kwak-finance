import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { logout } from "./api/generated";
import { meQuery } from "./auth/session";
import { ThemeToggle } from "./components/ThemeToggle";
import { Button } from "./components/ui";

export function HomePage() {
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
          <span className="text-xl font-black tracking-tight">Kwak Finance</span>
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
        <h1 className="text-3xl font-black tracking-tight">Welcome, {user.display_name}</h1>
        <p className="mt-2 text-muted">
          Accounts, imports and budgets will appear here as they are built.
        </p>
      </main>
    </div>
  );
}
