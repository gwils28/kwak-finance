import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import type { RestoreOut } from "../api/generated";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => vi.unstubAllGlobals());

const summary = (changes: Partial<RestoreOut> = {}): RestoreOut => ({
  language: "en",
  created: ["Holidays"],
  renamed: [],
  merged: [{ from: "Courses", to: "Groceries" }],
  moved: [],
  deleted: ["Pets", "Vet"],
  transactions_to_categorise: 12,
  rules_deleted: 2,
  plan_targets_deleted: 3,
  locked_plans_affected: 1,
  ...changes,
});

function api(user = owner, preview = summary()) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(user),
    "GET /api/categories": () => Response.json([]),
    "GET /api/rules": () => Response.json([]),
    "GET /api/categories/restore": () => Response.json(preview),
    "POST /api/categories/restore": () => Response.json(preview),
  });
}

const section = () => screen.findByRole("region", { name: "Default categories" });

test("restoring shows what it implies before anything changes", async () => {
  const calls = api();
  render(<TestApp path="/categories" />);

  const user = userEvent.setup();
  await user.click(
    within(await section()).getByRole("button", { name: "Restore the default categories…" }),
  );

  const warning = await screen.findByRole("alert");
  expect(warning).toHaveTextContent("12 transactions go back to “to categorise”");
  expect(warning).toHaveTextContent("2 rules are deleted");
  expect(warning).toHaveTextContent("3 plan targets are deleted, in 1 plan already locked");
  expect(warning).toHaveTextContent(/backup/);
  const region = await section();
  expect(region).toHaveTextContent("Deleted (2): Pets, Vet");
  expect(region).toHaveTextContent("Merged (1): Courses → Groceries");
  expect(region).toHaveTextContent("Created (1): Holidays");
  expect(calls.some((c) => c.route === "POST /api/categories/restore")).toBe(false);

  await user.click(within(region).getByRole("button", { name: "Restore now" }));

  await vi.waitFor(() =>
    expect(calls.some((c) => c.route === "POST /api/categories/restore")).toBe(true),
  );
  expect(await screen.findByText("Default categories restored.")).toBeInTheDocument();
});

test("the restore can be cancelled", async () => {
  const calls = api();
  render(<TestApp path="/categories" />);

  const user = userEvent.setup();
  const region = await section();
  await user.click(within(region).getByRole("button", { name: "Restore the default categories…" }));
  await user.click(await within(region).findByRole("button", { name: "Cancel" }));

  expect(within(region).queryByRole("button", { name: "Restore now" })).toBeNull();
  expect(calls.some((c) => c.route === "POST /api/categories/restore")).toBe(false);
});

test("nothing to restore says so", async () => {
  api(
    owner,
    summary({
      created: [],
      merged: [],
      deleted: [],
      transactions_to_categorise: 0,
      rules_deleted: 0,
      plan_targets_deleted: 0,
      locked_plans_affected: 0,
    }),
  );
  render(<TestApp path="/categories" />);

  const user = userEvent.setup();
  const region = await section();
  await user.click(within(region).getByRole("button", { name: "Restore the default categories…" }));

  expect(
    await within(region).findByText("Your categories already match the defaults."),
  ).toBeInTheDocument();
  expect(within(region).queryByRole("button", { name: "Restore now" })).toBeNull();
});

test("only the owner sees the restore", async () => {
  api({ ...owner, role: "member" });
  render(<TestApp path="/categories" />);

  expect(await screen.findByRole("heading", { name: "Categories" })).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Default categories" })).toBeNull();
});
