import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { spendingHandlers } from "./spending/fixtures";
import { fakeApi, owner } from "./test/fakeApi";
import { TestApp } from "./test/TestApp";

afterEach(() => vi.unstubAllGlobals());

function api() {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "PATCH /api/auth/me": (body) => Response.json({ ...owner, ...(body as object) }),
    ...spendingHandlers(),
    "GET /api/household/members": () => Response.json([owner]),
    "GET /api/invites": () => Response.json([]),
    "GET /api/household/settings": () => Response.json({ warn_at: "0.80", wealth_start: null }),
  });
}

test("the main tabs lead to the everyday pages, the current one marked", async () => {
  api();
  render(<TestApp path="/spending?month=2026-10" />);

  const main = await screen.findByRole("navigation", { name: "Main" });
  const tabs = within(main).getAllByRole("link");
  expect(tabs.map((tab) => tab.textContent)).toEqual(["Lines", "Budget", "Reports", "Forecast"]);
  expect(within(main).getByRole("link", { name: "Lines" })).toHaveAttribute("aria-current", "page");
  // Spending is the space shown; wealth and goals are one click away.
  const spaces = screen.getByRole("navigation", { name: "Spaces" });
  expect(
    within(spaces)
      .getAllByRole("link")
      .map((link) => link.textContent),
  ).toEqual(["Spending", "Wealth", "Goals"]);
  expect(within(spaces).getByRole("link", { name: "Wealth" })).toHaveAttribute("href", "/wealth");
  expect(within(spaces).getByRole("link", { name: "Goals" })).toHaveAttribute("href", "/goals");
});

test("on a phone, a bar at the bottom leads to the overview and the three spaces", async () => {
  api();
  render(<TestApp path="/budget" />);

  const bar = await screen.findByRole("navigation", { name: "Sections" });
  const links = within(bar).getAllByRole("link");
  expect(links.map((link) => link.textContent)).toEqual(["Home", "Spending", "Wealth", "Goals"]);
  expect(links.map((link) => link.getAttribute("href"))).toEqual([
    "/",
    "/spending",
    "/wealth",
    "/goals",
  ]);
  expect(within(bar).getByRole("link", { name: "Spending" })).toHaveAttribute(
    "aria-current",
    "true",
  );
  expect(within(bar).getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-current");
});

test("the guide stands apart from the main tabs", async () => {
  api();
  render(<TestApp path="/spending?month=2026-10" />);

  const main = await screen.findByRole("navigation", { name: "Main" });
  expect(within(main).queryByRole("link", { name: "Guide" })).toBeNull();
  expect(screen.getByRole("link", { name: "Guide" })).toHaveAttribute("href", "/guide");
});

test("the account menu holds the household settings and preferences", async () => {
  api();
  render(<TestApp path="/spending?month=2026-10" />);

  const user = userEvent.setup();
  const button = await screen.findByRole("button", { name: "Account menu: Wilson" });
  expect(button).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("link", { name: "Categories" })).toBeNull();

  await user.click(button);
  expect(button).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByText("owner@example.com")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Categories" })).toHaveAttribute(
    "href",
    "/spending/categories",
  );
  expect(screen.getByRole("link", { name: "Members" })).toHaveAttribute("href", "/members");
  expect(screen.queryByRole("link", { name: "Accounts" })).toBeNull();
  expect(screen.getByRole("link", { name: "Activity log" })).toHaveAttribute("href", "/activity");
  expect(screen.getByRole("button", { name: "Dark theme" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();

  await user.keyboard("{Escape}");
  expect(button).toHaveAttribute("aria-expanded", "false");
  expect(button).toHaveFocus();
});

test("following a link from the account menu closes it", async () => {
  api();
  render(<TestApp path="/members" />);

  const user = userEvent.setup();
  const button = await screen.findByRole("button", { name: "Account menu: Wilson" });
  await user.click(button);
  await user.click(screen.getByRole("link", { name: "Categories" }));

  expect(await screen.findByRole("heading", { name: "Spending categories" })).toBeInTheDocument();
  expect(button).toHaveAttribute("aria-expanded", "false");
  // The household pages belong to no space.
  expect(screen.queryByRole("navigation", { name: "Main" })).toBeNull();
});

test("the logo stands next to the app's name in the header", async () => {
  api();
  render(<TestApp path="/members" />);

  const home = await screen.findByRole("link", { name: "Kwak Finance" });
  expect(home.querySelector("img")).toHaveAttribute("src", "/logo.png");
});

test("the sign-in page opens with the logo and the app's name", async () => {
  fakeApi({ "GET /api/auth/me": () => Response.json({ detail: "x" }, { status: 401 }) });
  render(<TestApp path="/login" />);

  await screen.findByRole("heading", { name: "Sign in" });
  expect(document.querySelector('img[src="/logo.png"]')?.parentElement).toHaveTextContent(
    "Kwak Finance",
  );
});

function bareApi() {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "PATCH /api/auth/me": (body) => Response.json({ ...owner, ...(body as object) }),
  });
}

test("the wealth space has its own tabs, retirement and the audit among them", async () => {
  bareApi();
  render(<TestApp path="/wealth/analysis" />);

  const spaces = await screen.findByRole("navigation", { name: "Spaces" });
  expect(within(spaces).getByRole("link", { name: "Wealth" })).toHaveAttribute(
    "aria-current",
    "true",
  );
  expect(within(spaces).getByRole("link", { name: "Spending" })).toHaveAttribute(
    "href",
    "/spending",
  );
  const main = screen.getByRole("navigation", { name: "Main" });
  expect(
    within(main)
      .getAllByRole("link")
      .map((tab) => tab.textContent),
  ).toEqual(["Monthly tracking", "Analysis", "Projection", "Retirement", "Audit"]);
  expect(within(main).getByRole("link", { name: "Analysis" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(within(main).getByRole("link", { name: "Monthly tracking" })).not.toHaveAttribute(
    "aria-current",
  );
});

test.each([
  ["/wealth/retirement", "Retirement"],
  ["/wealth/projection/retirement", "Retirement"],
  ["/wealth/audit", "Audit"],
  ["/audit", "Audit"],
])("%s opens the wealth tab %s, marked", async (path, tab) => {
  bareApi();
  render(<TestApp path={path} />);

  const main = await screen.findByRole("navigation", { name: "Main" });
  expect(within(main).getByRole("link", { name: tab })).toHaveAttribute("aria-current", "page");
  expect(within(main).getByRole("link", { name: "Projection" })).not.toHaveAttribute(
    "aria-current",
  );
  // The projection no longer has views of its own.
  expect(screen.queryByRole("navigation", { name: "Projection views" })).toBeNull();
});

test("the audit is a wealth tab, no longer next to the guide", async () => {
  api();
  render(<TestApp path="/spending?month=2026-10" />);

  await screen.findByRole("navigation", { name: "Main" });
  expect(screen.queryByRole("link", { name: "Audit" })).toBeNull();
});

test("the goals space has its pyramid and its analysis", async () => {
  fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "PATCH /api/auth/me": (body) => Response.json({ ...owner, ...(body as object) }),
  });
  render(<TestApp path="/goals" />);

  const spaces = await screen.findByRole("navigation", { name: "Spaces" });
  expect(within(spaces).getByRole("link", { name: "Goals" })).toHaveAttribute("aria-current");
  const tabs = screen.getByRole("navigation", { name: "Main" });
  expect(
    within(tabs)
      .getAllByRole("link")
      .map((l) => l.textContent),
  ).toEqual(["Pyramid", "Analysis"]);
  expect(within(tabs).getByRole("link", { name: "Pyramid" })).toHaveClass("border-accent");
});

test("the overview is the app's name, apart from every space", async () => {
  api();
  render(<TestApp path="/members" />);

  // The app's name leads to the overview; no switch nor tab repeats it.
  expect(await screen.findByRole("link", { name: "Kwak Finance" })).toHaveAttribute("href", "/");
  const spaces = screen.getByRole("navigation", { name: "Spaces" });
  expect(within(spaces).queryByRole("link", { name: "Overview" })).toBeNull();
  // Members is a household page, in the account menu: neither space is marked.
  expect(within(spaces).getByRole("link", { name: "Spending" })).not.toHaveAttribute(
    "aria-current",
  );
  expect(within(spaces).getByRole("link", { name: "Wealth" })).not.toHaveAttribute("aria-current");
  expect(screen.queryByRole("navigation", { name: "Main" })).toBeNull();
});
