import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => vi.unstubAllGlobals());

const checking = {
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
const category = (id: string, name: string, parent_id: string | null = null) => ({
  id,
  name,
  kind: "expense",
  parent_id,
  shift_day: null,
  one_off: null,
});
const categories = [
  category("c-food", "Food"),
  category("c-groceries", "Groceries", "c-food"),
  category("c-health", "Health"),
  category("c-pharmacy", "Pharmacy", "c-health"),
  category("c-home", "Home and garden"),
];
const receipt = {
  id: "t1",
  account_id: "a1",
  account_name: "Compte courant",
  booked_on: "2026-03-14",
  amount: "-84.30",
  label: "CARREFOUR",
  source: "import",
  bank_label: null,
  category_id: null,
  category_name: null,
  transfer_group_id: null,
  transfer_account_name: null,
  budget_month: "2026-03",
  budget_month_set: false,
  parts: [],
  note: null,
};
const split = {
  ...receipt,
  parts: [
    { category_id: "c-groceries", category_name: "Groceries", amount: "-60.00" },
    { category_id: "c-pharmacy", category_name: "Pharmacy", amount: "-24.30" },
  ],
  note: "Anniversaire de Léa",
};

type Handler = (body: unknown) => Response;

function api(extra: Record<string, Handler> = {}, items: object[] = [receipt]) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/accounts": () => Response.json([checking]),
    "GET /api/categories": () => Response.json(categories),
    "GET /api/transactions": () => Response.json({ items, total: items.length }),
    "GET /api/transfers/suggestions": () => Response.json([]),
    ...extra,
  });
}

async function openDetails(label = "CARREFOUR") {
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: `Details of ${label}` }));
  return { user, panel: screen.getByRole("form", { name: "Details" }) };
}

test("a transaction is split, the last part taking the rest", async () => {
  const calls = api({ "PUT /api/transactions/t1/split": () => Response.json(split) });
  render(<TestApp path="/transactions" />);

  const { user, panel } = await openDetails();
  await user.click(within(panel).getByRole("button", { name: "Split it" }));
  await user.selectOptions(within(panel).getByLabelText("Category of part 1"), "c-groceries");
  await user.type(within(panel).getByLabelText("Amount of part 1 (€)"), "60");
  await user.click(within(panel).getByRole("button", { name: "Add a part" }));
  await user.selectOptions(within(panel).getByLabelText("Category of part 2"), "c-home");
  await user.type(within(panel).getByLabelText("Amount of part 2 (€)"), "15,50");
  await user.selectOptions(within(panel).getByLabelText("Category of the rest"), "c-pharmacy");
  expect(within(panel).getByText("Rest: €8.80")).toBeInTheDocument();
  await user.click(within(panel).getByRole("button", { name: "Save" }));

  expect(calls.find((c) => c.route === "PUT /api/transactions/t1/split")?.body).toEqual({
    parts: [
      { category_id: "c-groceries", amount: "-60.00" },
      { category_id: "c-home", amount: "-15.50" },
    ],
    rest_category_id: "c-pharmacy",
  });
});

test("parts leaving no rest are refused before sending", async () => {
  const calls = api();
  render(<TestApp path="/transactions" />);

  const { user, panel } = await openDetails();
  await user.click(within(panel).getByRole("button", { name: "Split it" }));
  await user.selectOptions(within(panel).getByLabelText("Category of part 1"), "c-groceries");
  await user.type(within(panel).getByLabelText("Amount of part 1 (€)"), "90");
  await user.click(within(panel).getByRole("button", { name: "Save" }));

  expect(within(panel).getByRole("alert")).toHaveTextContent(/leave a rest/);
  expect(calls.some((c) => c.route === "PUT /api/transactions/t1/split")).toBe(false);
});

test("a split transaction shows its parts and its note", async () => {
  api({}, [split]);
  render(<TestApp path="/transactions" />);

  const row = (await screen.findByText("CARREFOUR")).closest("tr") as HTMLElement;
  expect(row).toHaveTextContent("Split");
  expect(row).toHaveTextContent("Groceries -€60.00");
  expect(row).toHaveTextContent("Pharmacy -€24.30");
  expect(row).toHaveTextContent("Anniversaire de Léa");
  expect(within(row).queryByRole("combobox")).not.toBeInTheDocument();
});

test("the split can be removed", async () => {
  const calls = api({ "DELETE /api/transactions/t1/split": () => Response.json(receipt) }, [split]);
  render(<TestApp path="/transactions" />);

  const { user, panel } = await openDetails();
  expect(within(panel).getByLabelText("Category of part 1")).toHaveValue("c-groceries");
  await user.click(within(panel).getByRole("button", { name: "Remove the split" }));

  expect(calls.map((c) => c.route)).toContain("DELETE /api/transactions/t1/split");
});

test("a note is added to an imported transaction", async () => {
  const calls = api({
    "PATCH /api/transactions/t1": (body) => Response.json({ ...receipt, ...(body as object) }),
  });
  render(<TestApp path="/transactions" />);

  const { user, panel } = await openDetails();
  await user.type(within(panel).getByLabelText("Note"), "Cadeau");
  await user.click(within(panel).getByRole("button", { name: "Save" }));

  expect(calls.find((c) => c.route === "PATCH /api/transactions/t1")?.body).toEqual({
    note: "Cadeau",
  });
  expect(calls.some((c) => c.route === "PUT /api/transactions/t1/split")).toBe(false);
});

test("a new transaction can carry a note", async () => {
  const calls = api({
    "POST /api/transactions": (body) =>
      Response.json({ ...receipt, id: "t9", ...(body as object) }, { status: 201 }),
  });
  render(<TestApp path="/transactions" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Add a transaction" }));
  const form = screen.getByRole("form", { name: "New transaction" });
  await user.type(within(form).getByLabelText("Amount (€)"), "12");
  await user.type(within(form).getByLabelText("Label"), "Marché");
  await user.type(within(form).getByLabelText("Note"), "Légumes");
  await user.click(within(form).getByRole("button", { name: "Save" }));

  // Sent with the entry itself: no second call that could fail after the entry exists.
  expect(calls.find((c) => c.route === "POST /api/transactions")?.body).toMatchObject({
    note: "Légumes",
  });
  expect(calls.some((c) => c.route.startsWith("PATCH"))).toBe(false);
});

test("in French, the details speak French", async () => {
  api({ "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }) }, [split]);
  render(<TestApp path="/transactions" />);

  const row = (await screen.findByText("CARREFOUR")).closest("tr") as HTMLElement;
  expect(row).toHaveTextContent("Ventilée");
  const user = userEvent.setup();
  await user.click(within(row).getByRole("button", { name: "Détails de CARREFOUR" }));
  expect(screen.getByRole("form", { name: "Détails" })).toHaveTextContent("Reste");
});

test("a refused split says why", async () => {
  api({
    "PUT /api/transactions/t1/split": () =>
      Response.json({ detail: "a transfer cannot be split: unlink it first" }, { status: 409 }),
  });
  render(<TestApp path="/transactions" />);

  const { user, panel } = await openDetails();
  await user.click(within(panel).getByRole("button", { name: "Split it" }));
  await user.selectOptions(within(panel).getByLabelText("Category of part 1"), "c-groceries");
  await user.type(within(panel).getByLabelText("Amount of part 1 (€)"), "60");
  await user.click(within(panel).getByRole("button", { name: "Save" }));

  expect(await within(panel).findByRole("alert")).toHaveTextContent(/cannot be split/);
});

test("changing only the note of a split transaction leaves its parts alone", async () => {
  const calls = api(
    { "PATCH /api/transactions/t1": (body) => Response.json({ ...split, ...(body as object) }) },
    [split],
  );
  render(<TestApp path="/transactions" />);

  const { user, panel } = await openDetails();
  await user.clear(within(panel).getByLabelText("Note"));
  await user.click(within(panel).getByRole("button", { name: "Save" }));

  expect(calls.find((c) => c.route === "PATCH /api/transactions/t1")?.body).toEqual({ note: null });
  expect(calls.some((c) => c.route === "PUT /api/transactions/t1/split")).toBe(false);
});

test("a part can be removed, its amount going back to the rest", async () => {
  api();
  render(<TestApp path="/transactions" />);

  const { user, panel } = await openDetails();
  await user.click(within(panel).getByRole("button", { name: "Split it" }));
  await user.type(within(panel).getByLabelText("Amount of part 1 (€)"), "60");
  await user.click(within(panel).getByRole("button", { name: "Add a part" }));
  await user.type(within(panel).getByLabelText("Amount of part 2 (€)"), "20");
  expect(within(panel).getByText("Rest: €4.30")).toBeInTheDocument();
  await user.click(within(panel).getByRole("button", { name: "Remove part 2" }));

  expect(within(panel).getByText("Rest: €24.30")).toBeInTheDocument();
});

test("a transfer side says why it cannot be split", async () => {
  api({}, [{ ...receipt, transfer_group_id: "g1", transfer_account_name: "Livret A" }]);
  render(<TestApp path="/transactions" />);

  const { panel } = await openDetails();
  expect(within(panel).queryByRole("button", { name: "Split it" })).not.toBeInTheDocument();
  expect(panel).toHaveTextContent(/A transfer cannot be split/);
});
