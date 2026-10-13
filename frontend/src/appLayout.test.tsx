import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner } from "./test/fakeApi";
import { TestApp } from "./test/TestApp";

afterEach(() => vi.unstubAllGlobals());

function api() {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "PATCH /api/auth/me": (body) => Response.json({ ...owner, ...(body as object) }),
    "GET /api/accounts": () => Response.json([]),
  });
}

test("the main tabs lead to the everyday pages, the current one marked", async () => {
  api();
  render(<TestApp path="/accounts" />);

  const main = await screen.findByRole("navigation", { name: "Main" });
  const tabs = within(main).getAllByRole("link");
  expect(tabs.map((tab) => tab.textContent)).toEqual([
    "Overview",
    "Accounts",
    "Transactions",
    "Budget",
  ]);
  expect(within(main).getByRole("link", { name: "Accounts" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(within(main).getByRole("link", { name: "Overview" })).not.toHaveAttribute("aria-current");
});

test("the guide stands apart from the main tabs", async () => {
  api();
  render(<TestApp path="/accounts" />);

  const main = await screen.findByRole("navigation", { name: "Main" });
  expect(within(main).queryByRole("link", { name: "Guide" })).toBeNull();
  expect(screen.getByRole("link", { name: "Guide" })).toHaveAttribute("href", "/guide");
});

test("the account menu holds the household settings and preferences", async () => {
  api();
  render(<TestApp path="/accounts" />);

  const user = userEvent.setup();
  const button = await screen.findByRole("button", { name: "Account menu: Wilson" });
  expect(button).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("link", { name: "Categories" })).toBeNull();

  await user.click(button);
  expect(button).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByText("owner@example.com")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Categories" })).toHaveAttribute("href", "/categories");
  expect(screen.getByRole("link", { name: "Members" })).toHaveAttribute("href", "/members");
  expect(screen.getByRole("button", { name: "Dark theme" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();

  await user.keyboard("{Escape}");
  expect(button).toHaveAttribute("aria-expanded", "false");
  expect(button).toHaveFocus();
});

test("following a link from the account menu closes it", async () => {
  api();
  render(<TestApp path="/accounts" />);

  const user = userEvent.setup();
  const button = await screen.findByRole("button", { name: "Account menu: Wilson" });
  await user.click(button);
  await user.click(screen.getByRole("link", { name: "Categories" }));

  expect(await screen.findByRole("heading", { name: "Categories" })).toBeInTheDocument();
  expect(button).toHaveAttribute("aria-expanded", "false");
});

test("the logo stands next to the app's name in the header", async () => {
  api();
  render(<TestApp path="/accounts" />);

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
