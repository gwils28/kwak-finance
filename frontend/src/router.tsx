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
import { ActivityPage } from "./activity/ActivityPage";
import type { Scope } from "./api/generated";
import { LoginPage } from "./auth/LoginPage";
import { meQuery } from "./auth/session";
import { AnalysisPage as GoalAnalysisPage } from "./goals/AnalysisPage";
import { GoalPage } from "./goals/GoalPage";
import { GoalsPage } from "./goals/GoalsPage";
import { GuidePage } from "./guide/GuidePage";
import { HomePage } from "./HomePage";
import { AcceptInvitePage } from "./household/AcceptInvitePage";
import { MembersPage } from "./household/MembersPage";
import { isMonth } from "./lib/months";
import { ReportsPage } from "./reports/ReportsPage";
import { RunGuidePage } from "./runGuide/RunGuidePage";
import { BudgetPage, parseBudgetSearch } from "./spending/BudgetPage";
import { CategoriesPage as SpendingCategoriesPage } from "./spending/CategoriesPage";
import { FixedPage } from "./spending/FixedPage";
import { GridPage, parseGridSearch } from "./spending/GridPage";
import { WealthAnalysisPage } from "./wealth/WealthAnalysisPage";
import { WealthPage } from "./wealth/WealthPage";
import { WealthProjectionPage } from "./wealth/WealthProjectionPage";
import { WealthRetirementPage } from "./wealth/WealthRetirementPage";

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

const spendingRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/spending",
  validateSearch: parseGridSearch,
  component: GridPage,
});

const fixedRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/spending/fixed",
  component: FixedPage,
});

const spendingCategoriesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/spending/categories",
  component: SpendingCategoriesPage,
});

const budgetRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/budget",
  validateSearch: parseBudgetSearch,
  component: BudgetPage,
});

const reportsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/reports",
  validateSearch: (search: Record<string, unknown>): { start?: string; end?: string } =>
    typeof search.start === "string" &&
    typeof search.end === "string" &&
    isMonth(search.start) &&
    isMonth(search.end)
      ? { start: search.start, end: search.end }
      : // Explicit: the parent's raw search would otherwise show through.
        { start: undefined, end: undefined },
  component: function Reports() {
    const { start, end } = reportsRoute.useSearch();
    // Keyed by the link: following another one, or the tab without one, starts afresh.
    return (
      <ReportsPage key={`${start}-${end}`} initial={start && end ? { start, end } : undefined} />
    );
  },
});

const wealthRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/wealth",
  component: WealthPage,
});

const wealthAnalysisRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/wealth/analysis",
  component: WealthAnalysisPage,
});

const wealthProjectionRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/wealth/projection",
  component: WealthProjectionPage,
});

const wealthRetirementRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/wealth/retirement",
  component: WealthRetirementPage,
});

const goalsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/goals",
  component: GoalsPage,
});

const goalAnalysisRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/goals/analysis",
  validateSearch: (search: Record<string, unknown>): { scope?: Scope } =>
    SCOPES.includes(search.scope as Scope) ? { scope: search.scope as Scope } : {},
  component: function GoalAnalysis() {
    const { scope } = goalAnalysisRoute.useSearch();
    return <GoalAnalysisPage key={scope ?? "household"} initialScope={scope} />;
  },
});

const SCOPES: Scope[] = ["household", "mine", "joint"];

const goalRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/goals/$goalId",
  component: function Goal() {
    const { goalId } = goalRoute.useParams();
    return <GoalPage key={goalId} goalId={goalId} />;
  },
});

const activityRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/activity",
  component: ActivityPage,
});

const guideRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/guide",
  component: GuidePage,
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
    spendingRoute,
    fixedRoute,
    spendingCategoriesRoute,
    budgetRoute,
    wealthRoute,
    wealthAnalysisRoute,
    wealthProjectionRoute,
    wealthRetirementRoute,
    goalsRoute,
    goalAnalysisRoute,
    goalRoute,
    reportsRoute,
    membersRoute,
    activityRoute,
    guideRoute,
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
