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
  ...extra,
});
const categories = [
  category("c-savings", "Savings accounts", "savings"),
  category("c-current", "Current accounts", "current"),
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
          id: "l-current",
          name: "Compte courant",
          owner_id: owner.id,
          owner_name: "Wilson",
          visibility: "shared",
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

test("the months shown can be chosen, back to the last 12", async () => {
  const asked: URL[] = [];
  api({
    "GET /api/wealth/matrix": (_, url) => {
      asked.push(url);
      return Response.json(matrix);
    },
  });
  render(<TestApp path="/wealth" />);
  const from = await screen.findByLabelText("From");
  const to = screen.getByLabelText("To");
  // The fields show the months on screen.
  await vi.waitFor(() => expect(from).toHaveValue("2026-10"));
  expect(to).toHaveValue("2026-12");
  expect(asked[0]?.searchParams.get("start")).toBeNull();

  // jsdom cannot type into <input type="month">: set the value as the picker would.
  fireEvent.change(from, { target: { value: "2026-01" } });
  await vi.waitFor(() => expect(asked.at(-1)?.searchParams.get("start")).toBe("2026-01"));
  expect(asked.at(-1)?.searchParams.get("end")).toBe("2026-12");

  await userEvent.setup().click(screen.getByRole("button", { name: "Last 12 months" }));
  await vi.waitFor(() => expect(asked.at(-1)?.searchParams.get("start")).toBeNull());
});

test("a period ending before it starts is not asked for", async () => {
  const asked: URL[] = [];
  api({
    "GET /api/wealth/matrix": (_, url) => {
      asked.push(url);
      return Response.json(matrix);
    },
  });
  render(<TestApp path="/wealth" />);
  const from = await screen.findByLabelText("From");
  await vi.waitFor(() => expect(from).toHaveValue("2026-10"));
  fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-05" } });
  expect(await screen.findByText("The period ends before it starts.")).toBeInTheDocument();
  expect(asked.some((u) => u.searchParams.get("end") === "2026-05")).toBe(false);
});

test("the matrix groups lines by category, carried values marked", async () => {
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
  // A bank account's line is entered by hand like any other.
  expect(within(table).getByRole("button", { name: "Edit Compte courant" })).toBeInTheDocument();
  expect(
    within(table).getByRole("button", { name: /^Value of Compte courant, Dec 2026/ }),
  ).toBeInTheDocument();
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

test("a line is added in any category, the bank accounts' ones too", async () => {
  const calls = api({ "POST /api/wealth/lines": () => Response.json(lines[0], { status: 201 }) });
  render(<TestApp path="/wealth" />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Add a line" }));

  const form = screen.getByRole("form", { name: "New line" });
  const select = within(form).getByLabelText("Category");
  expect(within(select).getByRole("option", { name: "Current accounts" })).toBeInTheDocument();
  expect(within(select).getByRole("option", { name: "Savings accounts" })).toBeInTheDocument();
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
    // Two members: something may be held jointly.
    "GET /api/household/members": () => Response.json([{ id: "u1" }, { id: "u2" }]),
    "GET /api/wealth/matrix": (_, url) => {
      asked.push(url);
      return Response.json(matrix);
    },
  });
  render(<TestApp path="/wealth" />);
  const user = userEvent.setup();
  await screen.findByRole("option", { name: "Joint" });
  await user.selectOptions(screen.getByLabelText("Scope"), "joint");
  await vi.waitFor(() => expect(asked.at(-1)?.searchParams.get("scope")).toBe("joint"));
});

test("a one-member household is not offered the joint scope", async () => {
  api({ "GET /api/household/members": () => Response.json([{ id: "u1" }]) });
  render(<TestApp path="/wealth" />);
  const scope = await screen.findByLabelText("Scope");
  await screen.findByRole("table", { name: "Wealth by month" });
  expect(within(scope).queryByRole("option", { name: "Joint" })).toBeNull();
  expect(within(scope).getByRole("option", { name: "Only mine" })).toBeInTheDocument();
});

test("in French, amounts and months read French", async () => {
  api({ "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }) });
  render(<TestApp path="/wealth" language="fr" />);
  const net = await screen.findByRole("region", { name: "Patrimoine net" });
  expect(plain(net.textContent)).toContain("8 400 €");
  expect(await screen.findByRole("columnheader", { name: "déc. 2026" })).toBeInTheDocument();
});

test("the tiles add the change over the months shown and the debt ratio", async () => {
  api();
  render(<TestApp path="/wealth" />);
  const net = await screen.findByRole("region", { name: "Net worth" });
  expect(plain(net.textContent)).toContain("+€400 · +5% since Oct 2026");
  expect(plain(screen.getByRole("region", { name: "Debts" }).textContent)).toContain(
    "26% of gross assets",
  );
});

test("the monthly tracking page keeps to the table, the charts are on the analysis page", async () => {
  api();
  render(<TestApp path="/wealth" />);
  await screen.findByRole("table", { name: "Wealth by month" });
  expect(screen.queryByRole("region", { name: "Net worth over time" })).not.toBeInTheDocument();

  await userEvent.setup().click(screen.getByRole("link", { name: "Analysis" }));
  expect(await screen.findByRole("heading", { name: "Wealth analysis" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Net worth" })).toBeInTheDocument();
  expect(screen.getByLabelText("From")).toBeInTheDocument();
  expect(screen.queryByRole("table", { name: "Wealth by month" })).not.toBeInTheDocument();
});

test("the charts read the matrix: allocation, mosaic, and what moved net worth", async () => {
  api();
  render(<TestApp path="/wealth/analysis" />);
  const user = userEvent.setup();
  expect(await screen.findByRole("region", { name: "Net worth over time" })).toBeInTheDocument();

  // The sunburst reads the pointed ring out.
  const allocation = screen.getByRole("region", { name: "Allocation" });
  await user.hover(within(allocation).getByRole("img", { name: "Stocks: €10,600 · 93%" }));
  expect(within(allocation).getByText("Stocks: €10,600 · 93%")).toBeInTheDocument();
  expect(
    within(allocation).getByRole("img", { name: "PEA Fortuneo: €10,600 · 93%" }),
  ).toBeInTheDocument();

  // The mosaic gives each category a tile.
  const mosaic = screen.getByRole("region", { name: "Mosaic" });
  expect(
    within(mosaic).getByRole("img", { name: "Current accounts: €800 · 7%" }),
  ).toBeInTheDocument();
  expect(within(mosaic).queryByRole("img", { name: /PEA Fortuneo/ })).not.toBeInTheDocument();

  // Both read the month chosen, the last one by default.
  await user.selectOptions(
    screen.getByLabelText("Month shown in the allocation and the mosaic"),
    "2026-10",
  );
  expect(within(allocation).getByText(/What you own in Oct 2026/)).toBeInTheDocument();
  expect(within(mosaic).getByRole("img", { name: "Stocks: €10,000 · 91%" })).toBeInTheDocument();

  // The bridge goes from October's net worth to December's.
  const bridge = within(screen.getByRole("region", { name: "What moved net worth" })).getByRole(
    "table",
    { hidden: true },
  );
  const rows = within(bridge)
    .getAllByRole("row", { hidden: true })
    .map((r) => plain(r.textContent));
  expect(rows).toEqual([
    "CategoryContribution",
    "Oct 2026€8,000",
    "Current accounts-€200",
    "Stocks+€600",
    "Dec 2026€8,400",
  ]);
});

test("categories are renamed, recoloured, moved, added and deleted", async () => {
  const calls = api({
    "PATCH /api/wealth/categories/c-stocks": () => Response.json(categories[2]),
    "POST /api/wealth/categories": () => Response.json(categories[2], { status: 201 }),
    "DELETE /api/wealth/categories/c-savings": () =>
      Response.json(
        {
          detail:
            "it still holds lines (perhaps a member's private ones): move or delete them first",
        },
        { status: 409 },
      ),
  });
  render(<TestApp path="/wealth" />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Manage categories" }));
  const panel = screen.getByRole("region", { name: "Categories" });

  const name = within(panel).getByLabelText("Name of Stocks");
  await user.clear(name);
  await user.type(name, "Actions");
  await user.selectOptions(within(panel).getByLabelText("Colour of Stocks"), "exotic");
  await user.click(within(panel).getByRole("button", { name: "Save Stocks" }));
  expect(calls.find((c) => c.route === "PATCH /api/wealth/categories/c-stocks")?.body).toEqual({
    name: "Actions",
    colour: "exotic",
  });

  // The first one cannot go up; Stocks goes one row up.
  expect(within(panel).getByRole("button", { name: "Move Savings accounts up" })).toBeDisabled();
  await user.click(within(panel).getByRole("button", { name: "Move Stocks up" }));
  expect(
    calls.filter((c) => c.route === "PATCH /api/wealth/categories/c-stocks").at(-1)?.body,
  ).toEqual({ position: 1 });

  // A category still holding lines stays, and the server says why.
  await user.click(within(panel).getByRole("button", { name: "Delete Savings accounts" }));
  expect(await within(panel).findByRole("alert")).toHaveTextContent(
    "It still holds lines (perhaps a member's private ones): move or delete them first.",
  );

  const form = within(panel).getByRole("form", { name: "New category" });
  await user.type(within(form).getByLabelText("Name"), "Montres");
  await user.selectOptions(within(form).getByLabelText("Colour"), "gold");
  await user.click(within(form).getByRole("button", { name: "Add" }));
  expect(calls.find((c) => c.route === "POST /api/wealth/categories")?.body).toEqual({
    name: "Montres",
    kind: "asset",
    colour: "gold",
  });
});

test("the matrix keeps its months and its line names in view while scrolling", async () => {
  api();
  render(<TestApp path="/wealth" />);
  const table = await screen.findByRole("table", { name: "Wealth by month" });
  // Its own scroll area, both ways, so the header row and the first column can stick.
  expect(table.parentElement?.className).toMatch(/overflow-auto/);
  expect(table.parentElement?.className).toMatch(/max-h-/);
  for (const header of within(table).getAllByRole("columnheader")) {
    expect(header.className).toMatch(/sticky/);
    expect(header.className).toMatch(/top-0/);
  }
  for (const header of within(table).getAllByRole("rowheader")) {
    expect(header.className).toMatch(/sticky/);
    expect(header.className).toMatch(/left-0/);
  }
});

test("each line says what goals set aside on it", async () => {
  const setAside = (amount: string) => () =>
    Response.json([
      {
        line_id: "l-pea",
        line_name: "PEA Fortuneo",
        worth: "9000.00",
        set_aside: amount,
        free: "0",
      },
    ]);
  api({ "GET /api/goals/lines": setAside("2500.00") });
  const { unmount } = render(<TestApp path="/wealth" />);
  expect(await screen.findByText("€2,500 set aside for goals")).toBeInTheDocument();
  unmount();

  api({
    "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }),
    "GET /api/goals/lines": setAside("2500.00"),
  });
  render(<TestApp path="/wealth" language="fr" />);
  expect(plain((await screen.findByText(/réservés aux objectifs/)).textContent)).toBe(
    "2 500 € réservés aux objectifs",
  );
});
