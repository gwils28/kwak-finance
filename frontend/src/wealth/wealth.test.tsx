import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import type { WealthCategoryOut, WealthMatrixLineOut, WealthMatrixOut } from "../api/generated";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 11, 10));
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const plain = (text: string | null) => text?.replace(/[  ]/g, " ");

const category = (
  id: string,
  name: string,
  colour: string,
  extra: Partial<WealthCategoryOut> = {},
): WealthCategoryOut => ({
  id,
  name,
  kind: "asset",
  colour,
  position: 0,
  holds: null,
  ...extra,
});
const categories = [
  category("c-savings", "Savings accounts", "savings", { holds: "savings" }),
  category("c-current", "Current accounts", "current", { holds: "checking" }),
  category("c-stocks", "Stocks", "stocks"),
  category("c-debts", "Debts", "debts", { kind: "debt" }),
];
const cell = (amount: string, carried = false) => ({ amount, carried });
const matrix: WealthMatrixOut = {
  months: ["2026-10", "2026-11", "2026-12"],
  categories: [
    {
      ...category("c-savings", "Savings accounts", "savings"),
      subtotals: ["0.00", "0.00", "0.00"],
      share: "0.0000",
      lines: [],
    },
    {
      ...category("c-current", "Current accounts", "current"),
      subtotals: ["1000.00", "750.00", "800.00"],
      share: "0.0702",
      lines: [
        {
          id: "a1",
          name: "Compte courant",
          owner_id: owner.id,
          owner_name: "Wilson",
          visibility: "shared",
          automatic: true,
          account_id: "a1",
          closed_from: null,
          cells: [cell("1000.00"), cell("750.00"), cell("800.00")],
          share: "0.0702",
        },
      ],
    },
    {
      ...category("c-stocks", "Stocks", "stocks"),
      subtotals: ["10000.00", "10000.00", "10600.00"],
      share: "0.9298",
      lines: [
        {
          id: "l-pea",
          name: "PEA Fortuneo",
          owner_id: owner.id,
          owner_name: "Wilson",
          visibility: "shared",
          automatic: false,
          account_id: null,
          closed_from: null,
          cells: [cell("10000.00"), cell("10000.00", true), cell("10600.00")],
          share: "0.9298",
        },
      ],
    },
    {
      ...category("c-debts", "Debts", "debts", { kind: "debt" }),
      subtotals: ["3000.00", "3000.00", "3000.00"],
      share: null,
      lines: [
        {
          id: "l-loan",
          name: "Prêt auto",
          owner_id: owner.id,
          owner_name: "Wilson",
          visibility: "private",
          automatic: false,
          account_id: null,
          closed_from: null,
          cells: [cell("3000.00"), cell("3000.00", true), cell("3000.00", true)],
          share: null,
        },
      ],
    },
  ],
  gross: ["11000.00", "10750.00", "11400.00"],
  debts: ["3000.00", "3000.00", "3000.00"],
  net: ["8000.00", "7750.00", "8400.00"],
  change: [null, "-250.00", "650.00"],
  change_ratio: [null, "-0.0313", "0.0839"],
};
const lines = [
  {
    id: "l-pea",
    category_id: "c-stocks",
    name: "PEA Fortuneo",
    owner_id: owner.id,
    owner_name: "Wilson",
    visibility: "shared",
    closed_from: null,
  },
  {
    id: "l-loan",
    category_id: "c-debts",
    name: "Prêt auto",
    owner_id: owner.id,
    owner_name: "Wilson",
    visibility: "private",
    closed_from: null,
  },
];

type Handler = (body: unknown, url: URL) => Response;

function api(extra: Record<string, Handler> = {}, data: object = matrix) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/accounts": () => Response.json([]),
    "GET /api/wealth/categories": () => Response.json(categories),
    "GET /api/wealth/lines": () => Response.json(lines),
    "GET /api/wealth/matrix": () => Response.json(data),
    ...extra,
  });
}

test("the wealth tab shows net worth and its change", async () => {
  api();
  render(<TestApp path="/" />);
  await userEvent.setup().click(await screen.findByRole("link", { name: "Wealth" }));

  const net = await screen.findByRole("region", { name: "Net worth" });
  expect(plain(net.textContent)).toContain("€8,400");
  expect(plain(net.textContent)).toContain("+€650 · +8% vs last month");
  expect(plain(screen.getByRole("region", { name: "Gross assets" }).textContent)).toContain(
    "€11,400",
  );
  expect(plain(screen.getByRole("region", { name: "Debts" }).textContent)).toContain("€3,000");
});

test("the matrix groups lines by category, carried and automatic values marked", async () => {
  api();
  render(<TestApp path="/wealth" />);
  const table = await screen.findByRole("table", { name: "Wealth by month" });
  const rows = within(table)
    .getAllByRole("row")
    .map((r) => plain(r.textContent));

  expect(rows).toContain("Stocks€10,000€10,000€10,60093%");
  expect(rows.find((r) => r?.startsWith("PEA Fortuneo"))).toContain(
    "€10,000 (carried from an earlier month)",
  );
  expect(rows.find((r) => r?.startsWith("Compte courant"))).toContain("automatic");
  expect(rows).toContain("Net worth€8,000€7,750€8,400");
  expect(rows).toContain("Change-€250 · -3%+€650 · +8%");
  // An empty category keeps no row of noise.
  expect(rows.some((r) => r?.startsWith("Savings accounts"))).toBe(false);
});

test("a manual cell opens its value, saved for its month", async () => {
  const calls = api({
    "PUT /api/wealth/lines/l-pea/values/2026-11": () => new Response(null, { status: 204 }),
  });
  render(<TestApp path="/wealth" />);
  const user = userEvent.setup();
  // The value is read out with the line and the month.
  await user.click(
    await screen.findByRole("button", {
      name: "Value of PEA Fortuneo, Nov 2026: €10,000 (carried from an earlier month)",
    }),
  );

  const form = screen.getByRole("form", { name: "PEA Fortuneo, Nov 2026" });
  const amount = within(form).getByLabelText("Value (€)");
  expect(amount).toHaveValue("10000");
  await user.clear(amount);
  await user.type(amount, "10 250,50");
  await user.click(within(form).getByRole("button", { name: "Save" }));

  expect(calls.find((c) => c.route === "PUT /api/wealth/lines/l-pea/values/2026-11")?.body).toEqual(
    {
      amount: "10250.50",
    },
  );
  expect(screen.queryByRole("button", { name: /Value of Compte courant/ })).not.toBeInTheDocument();
});

test("update this month pre-fills the last values and saves what is filled", async () => {
  const calls = api({
    "GET /api/wealth/update": () =>
      Response.json([
        {
          line_id: "l-pea",
          name: "PEA Fortuneo",
          category_id: "c-stocks",
          category_name: "Stocks",
          last_value: "10600.00",
        },
        {
          line_id: "l-btc",
          name: "Kraken",
          category_id: "c-crypto",
          category_name: "Crypto",
          last_value: null,
        },
      ]),
    "POST /api/wealth/update": () => new Response(null, { status: 204 }),
  });
  render(<TestApp path="/wealth" />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Update this month" }));

  const form = await screen.findByRole("form", { name: "Values for Dec 2026" });
  expect(within(form).getByLabelText("PEA Fortuneo (Stocks)")).toHaveValue("10600");
  await user.click(within(form).getByRole("button", { name: "Save" }));

  expect(calls.find((c) => c.route === "POST /api/wealth/update")?.body).toEqual({
    month: "2026-12",
    values: [{ line_id: "l-pea", amount: "10600.00" }],
  });
});

test("a line is added in a category the user fills by hand", async () => {
  const calls = api({ "POST /api/wealth/lines": () => Response.json(lines[0], { status: 201 }) });
  render(<TestApp path="/wealth" />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Add a line" }));

  const form = screen.getByRole("form", { name: "New line" });
  const select = within(form).getByLabelText("Category");
  // The cash accounts' categories fill themselves.
  expect(
    within(select).queryByRole("option", { name: "Current accounts" }),
  ).not.toBeInTheDocument();
  await user.selectOptions(select, "c-stocks");
  await user.type(within(form).getByLabelText("Name"), "CTO Trade Republic");
  await user.selectOptions(within(form).getByLabelText("Who sees it"), "private");
  await user.click(within(form).getByRole("button", { name: "Save" }));

  expect(calls.find((c) => c.route === "POST /api/wealth/lines")?.body).toEqual({
    category_id: "c-stocks",
    name: "CTO Trade Republic",
    visibility: "private",
  });
});

test("a line is closed from a month, or deleted", async () => {
  const calls = api({
    "PATCH /api/wealth/lines/l-loan": () => Response.json(lines[1]),
    "DELETE /api/wealth/lines/l-loan": () => new Response(null, { status: 204 }),
  });
  render(<TestApp path="/wealth" />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Edit Prêt auto" }));
  const form = screen.getByRole("form", { name: "Edit Prêt auto" });
  // jsdom cannot type into <input type="month">: set the value as the picker would.
  fireEvent.change(within(form).getByLabelText("Closed from"), { target: { value: "2026-12" } });
  await user.click(within(form).getByRole("button", { name: "Save" }));
  expect(calls.find((c) => c.route === "PATCH /api/wealth/lines/l-loan")?.body).toMatchObject({
    closed_from: "2026-12",
  });

  await user.click(await screen.findByRole("button", { name: "Edit Prêt auto" }));
  await user.click(await screen.findByRole("button", { name: "Delete the line" }));
  // Every value goes with it: a second click confirms.
  expect(calls.map((c) => c.route)).not.toContain("DELETE /api/wealth/lines/l-loan");
  await user.click(screen.getByRole("button", { name: "Delete it and its values" }));
  expect(calls.map((c) => c.route)).toContain("DELETE /api/wealth/lines/l-loan");
});

test("without any line, the page says where to start", async () => {
  api({}, { ...matrix, categories: matrix.categories.map((c) => ({ ...c, lines: [] })) });
  render(<TestApp path="/wealth" />);
  expect(await screen.findByText(/No line yet/)).toBeInTheDocument();
});

test("in French, wealth speaks French", async () => {
  api({ "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }) });
  render(<TestApp path="/wealth" language="fr" />);
  expect(await screen.findByRole("heading", { name: "Patrimoine" })).toBeInTheDocument();
  expect(await screen.findByRole("region", { name: "Patrimoine net" })).toBeInTheDocument();
});

test("another member's line shows its owner, without the owner's controls", async () => {
  const theirs = {
    ...lines[0],
    id: "l-theirs",
    name: "Livret Léa",
    owner_id: "m1",
    owner_name: "Léa",
  };
  const data = structuredClone(matrix);
  data.categories[2]?.lines.push({
    ...(data.categories[2]?.lines[0] as WealthMatrixLineOut),
    id: "l-theirs",
    name: "Livret Léa",
    owner_id: "m1",
    owner_name: "Léa",
  });
  const calls = api(
    {
      "GET /api/wealth/lines": () => Response.json([...lines, theirs]),
      "PATCH /api/wealth/lines/l-theirs": () => Response.json(theirs),
    },
    data,
  );
  render(<TestApp path="/wealth" />);
  const user = userEvent.setup();
  const table = await screen.findByRole("table", { name: "Wealth by month" });
  const rows = within(table)
    .getAllByRole("row")
    .map((r) => plain(r.textContent));
  expect(rows.find((r) => r?.startsWith("Livret Léa"))).toContain("Léa's");
  expect(rows.find((r) => r?.startsWith("Prêt auto"))).toContain("only you");

  await user.click(screen.getByRole("button", { name: "Edit Livret Léa" }));
  const form = await screen.findByRole("form", { name: "Edit Livret Léa" });
  expect(within(form).queryByLabelText("Who sees it")).not.toBeInTheDocument();
  expect(within(form).queryByRole("button", { name: "Delete the line" })).not.toBeInTheDocument();
  await user.click(within(form).getByRole("button", { name: "Save" }));
  expect(
    calls.find((c) => c.route === "PATCH /api/wealth/lines/l-theirs")?.body,
  ).not.toHaveProperty("visibility");
});

test("a negative or unreadable value is refused before sending", async () => {
  const calls = api();
  render(<TestApp path="/wealth" />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: /^Value of Prêt auto, Oct 2026/ }));
  const form = screen.getByRole("form", { name: "Prêt auto, Oct 2026" });
  expect(form).toHaveTextContent("What is still owed.");
  const amount = within(form).getByLabelText("Value (€)");
  await user.clear(amount);
  await user.type(amount, "-5");
  await user.click(within(form).getByRole("button", { name: "Save" }));
  expect(within(form).getByRole("alert")).toBeInTheDocument();
  expect(calls.some((c) => c.route.startsWith("PUT"))).toBe(false);
});

test("a month's value can be removed, and the server's reason is shown", async () => {
  const calls = api({
    "DELETE /api/wealth/lines/l-pea/values/2026-12": () =>
      Response.json({ detail: "PEA Fortuneo is closed in 2026-12" }, { status: 422 }),
  });
  render(<TestApp path="/wealth" />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: /^Value of PEA Fortuneo, Dec 2026/ }));
  await user.click(screen.getByRole("button", { name: "Remove this month's value" }));
  expect(calls.map((c) => c.route)).toContain("DELETE /api/wealth/lines/l-pea/values/2026-12");
  expect(await screen.findByRole("alert")).toHaveTextContent(/closed in 2026-12/);
});

test("a closed line can be reopened, and its closed months take no value", async () => {
  const closed = { ...lines[1], closed_from: "2026-12" };
  const data = structuredClone(matrix);
  const loan = data.categories[3]?.lines[0] as { closed_from: string | null; cells: unknown[] };
  loan.closed_from = "2026-12";
  loan.cells[2] = null;
  const calls = api(
    {
      "GET /api/wealth/lines": () => Response.json([lines[0], closed]),
      "PATCH /api/wealth/lines/l-loan": () => Response.json(lines[1]),
    },
    data,
  );
  render(<TestApp path="/wealth" />);
  const user = userEvent.setup();
  await screen.findByRole("table", { name: "Wealth by month" });
  expect(
    screen.queryByRole("button", { name: /^Value of Prêt auto, Dec 2026/ }),
  ).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Edit Prêt auto" }));
  const form = await screen.findByRole("form", { name: "Edit Prêt auto" });
  await user.click(within(form).getByRole("button", { name: "Reopen" }));
  await user.click(within(form).getByRole("button", { name: "Save" }));
  expect(calls.find((c) => c.route === "PATCH /api/wealth/lines/l-loan")?.body).toMatchObject({
    closed_from: null,
  });
});

test("the view follows the scope", async () => {
  const asked: URL[] = [];
  api({
    "GET /api/accounts": () => Response.json([{ id: "a9", type: "checking", visibility: "joint" }]),
    "GET /api/wealth/matrix": (_, url) => {
      asked.push(url);
      return Response.json(matrix);
    },
  });
  render(<TestApp path="/wealth" />);
  const user = userEvent.setup();
  await screen.findByRole("option", { name: "Joint accounts" });
  await user.selectOptions(screen.getByLabelText("Accounts"), "joint");
  await vi.waitFor(() => expect(asked.at(-1)?.searchParams.get("scope")).toBe("joint"));
});

test("in French, amounts and months read French", async () => {
  api({ "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }) });
  render(<TestApp path="/wealth" language="fr" />);
  const net = await screen.findByRole("region", { name: "Patrimoine net" });
  expect(plain(net.textContent)).toContain("8 400 €");
  expect(await screen.findByRole("columnheader", { name: "déc. 2026" })).toBeInTheDocument();
});
