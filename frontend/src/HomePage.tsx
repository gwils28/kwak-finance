import { useSuspenseQuery } from "@tanstack/react-query";
import { meQuery } from "./auth/session";

export function HomePage() {
  const { data: user } = useSuspenseQuery(meQuery);
  return (
    <>
      <h1 className="text-3xl font-black tracking-tight">Welcome, {user.display_name}</h1>
      <p className="mt-2 text-muted">
        Accounts, imports and budgets will appear here as they are built.
      </p>
    </>
  );
}
