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
import { LoginPage } from "./auth/LoginPage";
import { meQuery } from "./auth/session";
import { HomePage } from "./HomePage";
import { AcceptInvitePage } from "./household/AcceptInvitePage";
import { MembersPage } from "./household/MembersPage";

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

const routeTree = rootRoute.addChildren([
  appRoute.addChildren([homeRoute, membersRoute]),
  loginRoute,
  acceptInviteRoute,
]);

export function createAppRouter(queryClient: QueryClient, history?: RouterHistory) {
  return createRouter({ routeTree, context: { queryClient }, history });
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>;
  }
}
