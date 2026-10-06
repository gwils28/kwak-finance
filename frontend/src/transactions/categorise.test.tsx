import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => vi.unstubAllGlobals());

const account = {
  id: "a1",
  name: "Compte courant",
  institution: "Société Générale",
  type: "checking",
  visibility: "shared",
  owner_id: owner.id,
  owner_name: "Wilson",
  opening_balance: "0.00",
  opening_date: "2026-03-01",
  closed_on: null,
  balance: "100.00",
};
const categories = [
  { id: "c-food", name: "Food", kind: "expense", parent_id: null },
  { id: "c-bakery", name: "Bakery and coffee", kind: "expense", parent_id: "c-food" },
  { id: "c-groceries", name: "Groceries", kind: "expense", parent_id: "c-food" },
  { id: "c-income", name: "Income", kind: "income", parent_id: null },
  { id: "c-salary", name: "Salary", kind: "income", parent_id: "c-income" },
];
const tx = (id: string, label: string, amount: string, category: string | null = null) => ({
  id,
  account_id: "a1",
  account_name: "Compte courant",
  booked_on: "2026-03-14",
  amount,
  label,
  source: "import",
  category_id: category,
  category_name: categories.find((c) => c.id === category)?.name ?? null,
});
const bakery = tx("t1", "CARTE X0000 13/03 BOULANGERIE DU PARC 100000000000001IOPD", "-4.20");
const cafe = tx("t2", "CARTE X0000 13/03 CAFE DE LA GARE 100000000000002IOPD", "-1.10", "c-bakery");

type Handler = (body: unknown, url: URL) => Response;

function api(extra: Record<string, Handler> = {}) {
  const calls = fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/accounts": () => Response.json([account]),
    "GET /api/categories": () => Response.json(categories),
    "GET /api/transactions": () => Response.json({ items: [bakery, cafe], total: 2 }),
    ...extra,
  });
  return calls;
}

function lastListQuery(): URLSearchParams | undefined {
  return vi
    .mocked(fetch)
    .mock.calls.map(([r]) => new URL((r as Request).url))
    .filter((u) => u.pathname === "/api/transactions" && u.searchParams.get("limit") !== "1")
    .at(-1)?.searchParams;
}

test("each row shows its category and changing it saves at once", async () => {
  const calls = api({
    "PATCH /api/transactions/t1": (body) => Response.json({ ...bakery, ...(body as object) }),
  });
  render(<TestApp path="/transactions" />);

  const select = await screen.findByLabelText(
    "Category of CARTE X0000 13/03 BOULANGERIE DU PARC 100000000000001IOPD",
  );
  expect(select).toHaveValue("");
  expect(
    screen.getByLabelText("Category of CARTE X0000 13/03 CAFE DE LA GARE 100000000000002IOPD"),
  ).toHaveValue("c-bakery");
  await userEvent.setup().selectOptions(select, "c-bakery");

  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "PATCH /api/transactions/t1")?.body).toEqual({
      category_id: "c-bakery",
    }),
  );
});

test("the to-categorise counter filters the list", async () => {
  api({
    "GET /api/transactions": (_b, url) =>
      Response.json(
        url.searchParams.get("uncategorised")
          ? { items: [bakery], total: 1 }
          : { items: [bakery, cafe], total: 2 },
      ),
  });
  render(<TestApp path="/transactions" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "1 to categorise" }));

  await vi.waitFor(() => expect(lastListQuery()?.get("uncategorised")).toBe("true"));
  expect(screen.getByLabelText("Category", { selector: "select#category-filter" })).toHaveValue(
    "none",
  );
});

test("the category filter asks for one category", async () => {
  api();
  render(<TestApp path="/transactions" />);

  const user = userEvent.setup();
  await screen.findAllByRole("option", { name: "Groceries" });
  await user.selectOptions(
    screen.getByLabelText("Category", { selector: "select#category-filter" }),
    "c-groceries",
  );

  await vi.waitFor(() => expect(lastListQuery()?.get("category_id")).toBe("c-groceries"));
});

test("several rows can be categorised at once", async () => {
  const calls = api({
    "POST /api/transactions/categorise": () => Response.json({ updated: 2 }),
  });
  render(<TestApp path="/transactions" />);

  const user = userEvent.setup();
  await user.click(await screen.findByLabelText("Select all on this page"));
  const bar = screen.getByRole("region", { name: "2 selected" });
  await user.selectOptions(within(bar).getByLabelText("Category for the selection"), "c-groceries");
  await user.click(within(bar).getByRole("button", { name: "Apply" }));

  expect(await screen.findByText("2 transactions categorised.")).toBeInTheDocument();
  expect(calls.find((c) => c.route === "POST /api/transactions/categorise")?.body).toEqual({
    transaction_ids: ["t1", "t2"],
    category_id: "c-groceries",
  });
});

test("a rule can be created from a transaction, previewed and applied", async () => {
  const calls = api({
    "POST /api/rules/preview": () => Response.json({ matching: 3, uncategorised: 2, examples: [] }),
    "POST /api/rules": (body) =>
      Response.json(
        { id: "r1", priority: 10, category_name: "Bakery and coffee", ...(body as object) },
        { status: 201 },
      ),
    "POST /api/rules/apply": () => Response.json({ updated: 2 }),
  });
  render(<TestApp path="/transactions" />);

  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("button", {
      name: "Create a rule from CARTE X0000 13/03 BOULANGERIE DU PARC 100000000000001IOPD",
    }),
  );
  const panel = screen.getByRole("form", { name: "New rule" });
  expect(within(panel).getByLabelText("Label contains")).toHaveValue("BOULANGERIE DU PARC");
  await user.selectOptions(within(panel).getByLabelText("Category"), "c-bakery");

  expect(
    await within(panel).findByText("3 transactions match, 2 not yet categorised."),
  ).toBeInTheDocument();
  await user.click(within(panel).getByRole("button", { name: "Create the rule and apply it" }));

  expect(await screen.findByText("Rule created: 2 transactions categorised.")).toBeInTheDocument();
  expect(calls.find((c) => c.route === "POST /api/rules")?.body).toEqual({
    category_id: "c-bakery",
    label_contains: "BOULANGERIE DU PARC",
  });
  expect(calls.find((c) => c.route === "POST /api/rules/apply")?.body).toEqual({
    only_uncategorised: true,
  });
});
