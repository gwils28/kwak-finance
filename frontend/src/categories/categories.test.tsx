import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => vi.unstubAllGlobals());

const categories = [
  { id: "c-food", name: "Food", kind: "expense", parent_id: null },
  { id: "c-bakery", name: "Bakery and coffee", kind: "expense", parent_id: "c-food" },
  { id: "c-groceries", name: "Groceries", kind: "expense", parent_id: "c-food" },
  { id: "c-housing", name: "Housing", kind: "expense", parent_id: null },
  { id: "c-income", name: "Income", kind: "income", parent_id: null },
  { id: "c-salary", name: "Salary", kind: "income", parent_id: "c-income" },
];
const rule = (id: string, priority: number, extra: object) => ({
  id,
  priority,
  category_id: "c-bakery",
  category_name: "Bakery and coffee",
  label_contains: null,
  amount_min: null,
  amount_max: null,
  account_id: null,
  ...extra,
});
const rules = [
  rule("r1", 10, { label_contains: "BOULANGERIE" }),
  rule("r2", 20, { label_contains: "CAFE", amount_min: "1.00", amount_max: "10.00" }),
];

type Handler = (body: unknown, url: URL) => Response;

function api(extra: Record<string, Handler> = {}) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/categories": () => Response.json(categories),
    "GET /api/rules": () => Response.json(rules),
    "GET /api/accounts": () => Response.json([]),
    ...extra,
  });
}

test("categories are shown as a tree, spending then income", async () => {
  api();
  render(<TestApp path="/categories" />);

  const spending = await screen.findByRole("list", { name: "Spending categories" });
  const food = within(spending).getByRole("listitem", { name: "Food" });
  expect(within(food).getByRole("list", { name: "Subcategories of Food" })).toHaveTextContent(
    /Bakery and coffee.*Groceries/,
  );
  expect(screen.getByRole("list", { name: "Income categories" })).toHaveTextContent("Salary");
});

test("a category is renamed in place", async () => {
  const calls = api({
    "PATCH /api/categories/c-housing": (body) =>
      Response.json({ ...categories[3], ...(body as object) }),
  });
  render(<TestApp path="/categories" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Rename Housing" }));
  const input = screen.getByLabelText("New name for Housing");
  await user.clear(input);
  await user.type(input, "Home{Enter}");

  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "PATCH /api/categories/c-housing")?.body).toEqual({
      name: "Home",
    }),
  );
});

test("a subcategory is added under its parent", async () => {
  const calls = api({
    "POST /api/categories": (body) =>
      Response.json({ id: "c-new", kind: "expense", ...(body as object) }, { status: 201 }),
  });
  render(<TestApp path="/categories" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Add a subcategory to Food" }));
  await user.type(screen.getByLabelText("New subcategory of Food"), "Wine{Enter}");

  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "POST /api/categories")?.body).toEqual({
      name: "Wine",
      kind: "expense",
      parent_id: "c-food",
    }),
  );
});

test("a new top-level category picks its kind", async () => {
  const calls = api({
    "POST /api/categories": (body) =>
      Response.json({ id: "c-new", ...(body as object) }, { status: 201 }),
  });
  render(<TestApp path="/categories" />);

  const user = userEvent.setup();
  const form = await screen.findByRole("form", { name: "New category" });
  await user.type(within(form).getByLabelText("Name"), "Side business");
  await user.selectOptions(within(form).getByLabelText("Kind"), "income");
  await user.click(within(form).getByRole("button", { name: "Add" }));

  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "POST /api/categories")?.body).toEqual({
      name: "Side business",
      kind: "income",
      parent_id: null,
    }),
  );
});

test("a subcategory moves to another parent", async () => {
  const calls = api({
    "PATCH /api/categories/c-bakery": (body) =>
      Response.json({ ...categories[1], ...(body as object) }),
  });
  render(<TestApp path="/categories" />);

  await userEvent
    .setup()
    .selectOptions(await screen.findByLabelText("Move Bakery and coffee to"), "c-housing");

  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "PATCH /api/categories/c-bakery")?.body).toEqual({
      parent_id: "c-housing",
    }),
  );
});

test("deleting asks for confirmation and explains a refusal", async () => {
  const calls = api({
    "DELETE /api/categories/c-food": () =>
      Response.json({ detail: "move or delete its subcategories first" }, { status: 409 }),
  });
  render(<TestApp path="/categories" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Delete Food" }));
  expect(calls.some((c) => c.route.startsWith("DELETE"))).toBe(false);
  await user.click(screen.getByRole("button", { name: "Confirm: delete Food" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Move or delete its subcategories first.",
  );
});

test("rules are listed in order with their conditions in words", async () => {
  api();
  render(<TestApp path="/categories" />);

  const list = await screen.findByRole("list", { name: "Rules, in the order they run" });
  const items = within(list).getAllByRole("listitem");
  expect(items[0]).toHaveTextContent('Label contains "BOULANGERIE"');
  expect(items[0]).toHaveTextContent("Bakery and coffee");
  expect(items[1]).toHaveTextContent(/Label contains "CAFE" · from €1.00 to €10.00/);
});

test("moving a rule up swaps its priority with the one above", async () => {
  const calls = api({
    "PATCH /api/rules/r1": (body) => Response.json({ ...rules[0], ...(body as object) }),
    "PATCH /api/rules/r2": (body) => Response.json({ ...rules[1], ...(body as object) }),
  });
  render(<TestApp path="/categories" />);

  await userEvent
    .setup()
    .click(await screen.findByRole("button", { name: 'Run the rule "CAFE" earlier' }));

  await vi.waitFor(() => {
    expect(calls.find((c) => c.route === "PATCH /api/rules/r2")?.body).toEqual({ priority: 10 });
    expect(calls.find((c) => c.route === "PATCH /api/rules/r1")?.body).toEqual({ priority: 20 });
  });
});

test("a rule is edited, deleted, and all rules can be re-applied", async () => {
  const calls = api({
    "PATCH /api/rules/r1": (body) => Response.json({ ...rules[0], ...(body as object) }),
    "DELETE /api/rules/r2": () => new Response(null, { status: 204 }),
    "POST /api/rules/apply": () => Response.json({ updated: 4 }),
  });
  render(<TestApp path="/categories" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: 'Edit the rule "BOULANGERIE"' }));
  const form = screen.getByRole("form", { name: 'Edit the rule "BOULANGERIE"' });
  const label = within(form).getByLabelText("Label contains");
  await user.clear(label);
  await user.type(label, "BOULANGERIE DU PARC");
  await user.click(within(form).getByRole("button", { name: "Save" }));
  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "PATCH /api/rules/r1")?.body).toMatchObject({
      label_contains: "BOULANGERIE DU PARC",
    }),
  );

  await user.click(screen.getByRole("button", { name: 'Delete the rule "CAFE"' }));
  await vi.waitFor(() => expect(calls.some((c) => c.route === "DELETE /api/rules/r2")).toBe(true));

  await user.click(screen.getByRole("button", { name: "Apply the rules to past transactions" }));
  expect(await screen.findByText("4 transactions categorised.")).toBeInTheDocument();
  expect(calls.find((c) => c.route === "POST /api/rules/apply")?.body).toEqual({
    only_uncategorised: true,
  });
});

test("the header links to the categories", async () => {
  api({ "GET /api/dashboard": () => Response.json({}, { status: 500 }) });
  render(<TestApp path="/" />);
  await userEvent.setup().click(await screen.findByRole("link", { name: "Categories" }));
  expect(await screen.findByRole("heading", { name: "Categories" })).toBeInTheDocument();
});
