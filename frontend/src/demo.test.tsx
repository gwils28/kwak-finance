import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { spendingHandlers } from "./spending/fixtures";
import { fakeApi, owner } from "./test/fakeApi";
import { TestApp } from "./test/TestApp";

afterEach(() => vi.unstubAllGlobals());

const demoOwner = {
  ...owner,
  id: "0192f0a0-0000-7000-8000-0000000000d1",
  household_id: "0192f0a0-0000-7000-8000-0000000000d2",
  email: "camille.0192f0a00000@demo.invalid",
  display_name: "Camille",
  demo: true,
};

/** The API as the demo's routes change it: /me answers whoever the session acts as. */
function api(startInDemo = false, language = "en") {
  let inDemo = startInDemo;
  const me = () => Response.json({ ...(inDemo ? demoOwner : { ...owner, demo: false }), language });
  const calls = fakeApi({
    "GET /api/auth/me": me,
    ...spendingHandlers(),
    "GET /api/household/members": () => Response.json([owner]),
    "POST /api/demo/enter": () => {
      inDemo = true;
      return me();
    },
    "POST /api/demo/leave": () => {
      inDemo = false;
      return me();
    },
    "POST /api/demo/reset": () => me(),
  });
  return calls;
}

async function openMenu(name: string) {
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: `Account menu: ${name}` }));
  return user;
}

test("the demo opens from the account menu, next to the activity log", async () => {
  const calls = api();
  render(<TestApp path="/spending?month=2026-10" />);

  const user = await openMenu("Wilson");
  const items = screen.getAllByRole("link").concat(screen.getAllByRole("button"));
  expect(items.map((item) => item.textContent)).toContain("Open the demo");
  await user.click(screen.getByRole("button", { name: "Open the demo" }));

  const banner = await screen.findByRole("region", { name: "You are in the demo" });
  expect(banner).toHaveTextContent("shared by every member");
  expect(calls.some((c) => c.route === "POST /api/demo/enter")).toBe(true);
  expect(await screen.findByRole("button", { name: "Account menu: Camille" })).toBeInTheDocument();
});

test("outside the demo there is no banner", async () => {
  api();
  render(<TestApp path="/spending?month=2026-10" />);

  await screen.findByRole("button", { name: "Account menu: Wilson" });
  expect(screen.queryByRole("region", { name: "You are in the demo" })).toBeNull();
});

test("the banner leads back to the household", async () => {
  const calls = api(true);
  render(<TestApp path="/spending?month=2026-10" />);

  const banner = await screen.findByRole("region", { name: "You are in the demo" });
  const user = userEvent.setup();
  await user.click(within(banner).getByRole("button", { name: "Back to my household" }));

  expect(await screen.findByRole("button", { name: "Account menu: Wilson" })).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "You are in the demo" })).toBeNull();
  expect(calls.some((c) => c.route === "POST /api/demo/leave")).toBe(true);
});

test("resetting the demo asks first", async () => {
  const calls = api(true);
  render(<TestApp path="/spending?month=2026-10" />);

  const banner = await screen.findByRole("region", { name: "You are in the demo" });
  const user = userEvent.setup();
  await user.click(within(banner).getByRole("button", { name: "Reset the demo" }));
  const confirm = screen.getByRole("alertdialog", { name: "Reset the demo" });
  await user.click(within(confirm).getByRole("button", { name: "Cancel" }));
  expect(calls.some((c) => c.route === "POST /api/demo/reset")).toBe(false);

  await user.click(within(banner).getByRole("button", { name: "Reset the demo" }));
  await user.click(
    within(screen.getByRole("alertdialog", { name: "Reset the demo" })).getByRole("button", {
      name: "Reset",
    }),
  );
  expect(calls.some((c) => c.route === "POST /api/demo/reset")).toBe(true);
});

test("in the demo the menu leaves it and hides the members", async () => {
  api(true);
  render(<TestApp path="/spending?month=2026-10" />);

  await openMenu("Camille");
  // The menu's way back, beside the banner's.
  expect(screen.getAllByRole("button", { name: "Back to my household" })).toHaveLength(2);
  expect(screen.queryByRole("button", { name: "Open the demo" })).toBeNull();
  expect(screen.queryByRole("link", { name: "Members" })).toBeNull();
  expect(screen.getByRole("link", { name: "Activity log" })).toBeInTheDocument();
});

test("every change says which household the page shows", async () => {
  const calls = api(true);
  render(<TestApp path="/spending?month=2026-10" />);

  const banner = await screen.findByRole("region", { name: "You are in the demo" });
  const user = userEvent.setup();
  await user.click(within(banner).getByRole("button", { name: "Back to my household" }));

  const leave = calls.find((c) => c.route === "POST /api/demo/leave");
  expect(leave?.headers.get("X-Kwak-Household")).toBe(demoOwner.household_id);
});

test("the demo is in French too", async () => {
  api(true, "fr");
  render(<TestApp path="/spending?month=2026-10" language="fr" />);

  const banner = await screen.findByRole("region", { name: "Vous êtes dans la démo" });
  expect(within(banner).getByRole("button", { name: "Revenir à mon foyer" })).toBeInTheDocument();
});
