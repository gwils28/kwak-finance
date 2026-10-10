import type { QueryClient } from "@tanstack/react-query";
import {
  createRootRouteWithContext,
  createRoute,
  createRouter,
  Outlet,
  type RouterHistory,
  redirect,
} from "@tanstack/react-router";
import { AppLayout } from "./AppLayout";
import { AccountsPage } from "./accounts/AccountsPage";
import { LoginPage } from "./auth/LoginPage";
import { meQuery } from "./auth/session";
import { BudgetPage } from "./budget/BudgetPage";
import { CategoriesPage } from "./categories/CategoriesPage";
import { HomePage } from "./HomePage";
import { AcceptInvitePage } from "./household/AcceptInvitePage";
import { MembersPage } from "./household/MembersPage";
import { ImportPage } from "./imports/ImportPage";
import { RunGuidePage } from "./runGuide/RunGuidePage";
import { parseTransactionSearch, TransactionsPage } from "./transactions/TransactionsPage";

const rootRoute = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: Outlet,
});

async function isSignedIn(queryClient: QueryClient): Promise<boolean> {
  try {
    await queryClient.ensureQueryData(meQuery);
    return true;
  } catch {
    return false;
  }
}

/** Every page below requires a fully verified session (password + TOTP). */
const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "app",
  beforeLoad: async ({ context }) => {
    if (!(await isSignedIn(context.queryClient))) throw redirect({ to: "/login" });
  },
  component: AppLayout,
});

const homeRoute = createRoute({ getParentRoute: () => appRoute, path: "/", component: HomePage });

const membersRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/members",
  component: MembersPage,
});

const accountsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/accounts",
  component: AccountsPage,
});

const importRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/accounts/$accountId/import",
  component: ImportPage,
});

const transactionsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/transactions",
  validateSearch: parseTransactionSearch,
  component: TransactionsPage,
});

const budgetRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/budget",
  component: BudgetPage,
});

const categoriesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/categories",
  component: CategoriesPage,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  beforeLoad: async ({ context }) => {
    if (await isSignedIn(context.queryClient)) throw redirect({ to: "/" });
  },
  component: LoginPage,
});

const acceptInviteRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/invite/$token",
  component: AcceptInvitePage,
});

/** Public: it explains how to start the app, so it must not need an account. */
const runGuideRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/run",
  component: RunGuidePage,
});

const routeTree = rootRoute.addChildren([
  appRoute.addChildren([
    homeRoute,
    accountsRoute,
    importRoute,
    transactionsRoute,
    budgetRoute,
    categoriesRoute,
    membersRoute,
  ]),
  loginRoute,
  acceptInviteRoute,
  runGuideRoute,
]);

export function createAppRouter(queryClient: QueryClient, history?: RouterHistory) {
  return createRouter({ routeTree, context: { queryClient }, history });
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>;
  }
}
