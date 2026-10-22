import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

beforeAll(() => {
  // Recharts measures its container; jsdom has no layout engine.
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
});
beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 9, 14));
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const plain = (text: string | null) => text?.replace(/[  ]/g, " ");

const figures = (income: string, spent: string, saved: string, rest: string) => ({
  income,
  spent,
  saved,
  rest,
  savings_rate: "0.3000",
});
const row = (section: string, id: string, name: string, extra: object) => ({
  section,
  category_id: id,
  name,
  monthly_average: "0.00",
  share: null,
  previous: "0.00",
  change: null,
  ...extra,
});
const report = {
  start: "2026-01",
  end: "2026-12",
  to_date: false,
  first_month: "2024-01",
  months: 12,
  previous_start: "2025-01",
  previous_end: "2025-12",
  compared: true,
  totals: figures("30000.00", "21000.00", "200.00", "8800.00"),
  previous: figures("29000.00", "20000.00", "200.00", "8800.00"),
  changes: { income: "0.0345", spent: "0.0500", saved: "0.0000", rest: null },
  sections: [
    {
      section: "spending",
      amount: "21000.00",
      monthly_average: "1750.00",
      previous: "20000.00",
      change: "0.0500",
    },
    {
      section: "savings",
      amount: "200.00",
      monthly_average: "16.67",
      previous: "200.00",
      change: "0.0000",
    },
  ],
  rows: [
    row("spending", "c-housing", "Housing", {
      amount: "12000.00",
      monthly_average: "1000.00",
      share: "0.5714",
      previous: "10000.00",
      change: "0.2000",
    }),
    row("spending", "c-groceries", "Groceries", {
      amount: "9000.00",
      monthly_average: "750.00",
      share: "0.4286",
      previous: "10000.00",
      change: "-0.1000",
    }),
    row("savings", "c-savings", "Savings", {
      amount: "200.00",
      monthly_average: "16.67",
      share: "1.0000",
      previous: "200.00",
      change: "0.0000",
    }),
  ],
  monthly: Array.from({ length: 12 }, (_, i) => ({
    month: `2026-${String(i + 1).padStart(2, "0")}`,
    income: "2500.00",
    spent: "1750.00",
    saved: "16.67",
    rest: "733.33",
    by_category: [],
  })),
  flows: [
    { kind: "income", side: "in", amount: "30000.00", category_id: null, name: null, over: false },
    {
      kind: "spending",
      side: "out",
      amount: "12000.00",
      category_id: "c-housing",
      name: "Housing",
      over: true,
    },
    {
      kind: "spending",
      side: "out",
      amount: "9000.00",
      category_id: "c-groceries",
      name: "Groceries",
      over: false,
    },
    { kind: "saved", side: "out", amount: "200.00", category_id: null, name: null, over: false },
    {
      kind: "unallocated",
      side: "out",
      amount: "8800.00",
      category_id: null,
      name: null,
      over: false,
    },
  ],
};

function api(answer: (url: URL) => object = () => report) {
  const asked: URL[] = [];
  fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/spending/report": (_, url) => {
      asked.push(url);
      return Response.json(answer(url));
    },
  });
  return asked;
}

test("the reports tab shows this year's totals against the year before", async () => {
  const asked = api();
  render(<TestApp path="/reports" />);

  const summary = await screen.findByRole("region", { name: "Totals" });
  expect(plain(summary.textContent)).toContain("Spending€21,000+5% vs the period before");
  expect(plain(summary.textContent)).toContain("Savings rate30%");
  expect(plain(summary.textContent)).toContain("Saved€2000% vs the period before");
  expect(plain(summary.textContent)).toContain("Rest+€8,800Nothing the period before");
  expect(screen.getByText(/Compared with Jan 2025 – Dec 2025/)).toBeInTheDocument();
  expect(asked[0]?.searchParams.get("start")).toBe("2026-01");
  expect(asked[0]?.searchParams.get("end")).toBe("2026-12");
  expect(asked[0]?.searchParams.has("scope")).toBe(false);
});

test("a preset or a custom period changes the months asked for", async () => {
  const asked = api();
  render(<TestApp path="/reports" />);
  const user = userEvent.setup();
  await screen.findByRole("region", { name: "Totals" });

  await user.selectOptions(screen.getByLabelText("Period"), "lastYear");
  await vi.waitFor(() => expect(asked.at(-1)?.searchParams.get("start")).toBe("2025-01"));
  await user.selectOptions(screen.getByLabelText("Period"), "thisQuarter");
  await vi.waitFor(() => expect(asked.at(-1)?.searchParams.get("end")).toBe("2026-12"));
  expect(asked.at(-1)?.searchParams.get("start")).toBe("2026-10");
  await user.selectOptions(screen.getByLabelText("Period"), "last12");
  await vi.waitFor(() => expect(asked.at(-1)?.searchParams.get("start")).toBe("2025-11"));

  await user.selectOptions(screen.getByLabelText("Period"), "custom");
  // jsdom cannot type into <input type="month">: set the value as the picker would.
  fireEvent.change(screen.getByLabelText("First month"), { target: { value: "2024-03" } });
  await vi.waitFor(() => expect(asked.at(-1)?.searchParams.get("start")).toBe("2024-03"));
  expect(asked.at(-1)?.searchParams.get("end")).toBe("2026-10");
});

test("a custom period ending before it starts is not asked for", async () => {
  const asked = api();
  render(<TestApp path="/reports" />);
  const user = userEvent.setup();
  await screen.findByRole("region", { name: "Totals" });
  await user.selectOptions(screen.getByLabelText("Period"), "custom");
  const count = asked.length;
  fireEvent.change(screen.getByLabelText("Last month"), { target: { value: "2020-01" } });

  expect(screen.getByRole("alert")).toHaveTextContent(/must come before/);
  expect(asked.length).toBe(count);
});

test("the table lists the spending and savings categories with their totals", async () => {
  api();
  render(<TestApp path="/reports" />);
  const table = await screen.findByRole("table", { name: "By category" });

  const rows = within(table)
    .getAllByRole("row")
    .map((r) => plain(r.textContent));
  expect(rows).toContain("Housing€12,000€1,00057%€10,000+20%");
  expect(rows).toContain("Groceries€9,000€75043%€10,000-10%");
  expect(rows).toContain("Total spending€21,000€1,750100%€20,000+5%");
  expect(rows).toContain("Savings€200€17100%€2000%");
});

test("the money flows mark the spending over its targets, in colour and in words", async () => {
  api();
  render(<TestApp path="/reports" />);
  const flows = await screen.findByRole("region", { name: "Money flows" });
  const legend = within(flows).getByRole("list", { name: "Colours" });
  expect(legend).toHaveTextContent("Spending over its targets");
  expect(legend).toHaveTextContent("Spending within its targets, or without one");
  const table = within(flows).getByRole("table", { name: "Money flows" });
  const rows = within(table)
    .getAllByRole("row")
    .map((r) => plain(r.textContent));
  expect(rows).toContain("OutHousing€12,00040%over its targets");
  expect(rows).toContain("OutGroceries€9,00030%within its targets, or without one");
  expect(rows).toContain("InIncome€30,000100%");
  expect(rows).toContain("OutUnallocated€8,80029%");
});

test("the spending chart has its table, the largest category first", async () => {
  api();
  render(<TestApp path="/reports" />);
  const chart = await screen.findByRole("region", { name: "Spending by category" });
  const table = within(chart).getByRole("table", { name: "Spending by category over the period" });
  const rows = within(table).getAllByRole("row");
  expect(plain(rows[1]?.textContent ?? "")).toBe("Housing€12,00057%");
});

test("a period without lines says so", async () => {
  api(() => ({ ...report, rows: [], flows: [] }));
  render(<TestApp path="/reports" />);
  expect(await screen.findByText("No lines in this period.")).toBeInTheDocument();
});

test("in French, the reports speak French", async () => {
  fakeApi({
    "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }),
    "GET /api/spending/report": () => Response.json(report),
  });
  render(<TestApp path="/reports" language="fr" />);
  expect(await screen.findByRole("heading", { name: "Rapports" })).toBeInTheDocument();
  expect(await screen.findByRole("region", { name: "Totaux" })).toHaveTextContent("Taux d'épargne");
});

test("a running period says it is shown so far", async () => {
  api(() => ({ ...report, end: "2026-10", to_date: true, months: 10, previous_end: "2025-10" }));
  render(<TestApp path="/reports" />);
  expect(
    await screen.findByText(/Jan 2026 – Oct 2026 so far · Compared with Jan 2025 – Oct 2025/),
  ).toBeInTheDocument();
});

test("a link can open the report of given months", async () => {
  const asked = api();
  render(<TestApp path="/reports?start=2026-03&end=2026-03" />);
  await screen.findByRole("region", { name: "Totals" });
  expect(asked[0]?.searchParams.get("start")).toBe("2026-03");
  expect(asked[0]?.searchParams.get("end")).toBe("2026-03");
  expect(screen.getByLabelText("Period")).toHaveValue("custom");
});

test("the reports tab goes back to this year after a link to one month", async () => {
  const asked = api();
  render(<TestApp path="/reports?start=2026-03&end=2026-03" />);
  await screen.findByRole("region", { name: "Totals" });
  await userEvent.setup().click(screen.getByRole("link", { name: "Reports" }));

  await vi.waitFor(() => expect(screen.getByLabelText("Period")).toHaveValue("thisYear"));
  expect(asked.at(-1)?.searchParams.get("start")).toBe("2026-01");
});

test("a link with an impossible month opens this year instead", async () => {
  const asked = api();
  render(<TestApp path="/reports?start=2026-13&end=2026-13" />);
  await screen.findByRole("region", { name: "Totals" });
  expect(screen.getByLabelText("Period")).toHaveValue("thisYear");
  expect(asked[0]?.searchParams.get("start")).toBe("2026-01");
});

test("a report starting at the first month says so, and compares nothing before it", async () => {
  api(() => ({
    ...report,
    start: "2026-10",
    first_month: "2026-10",
    compared: false,
    changes: { income: null, spent: null, saved: null, rest: null },
  }));
  render(<TestApp path="/reports" />);
  expect(
    await screen.findByText(
      "Oct 2026 is the first month with a line or an income: earlier months are left out.",
    ),
  ).toBeInTheDocument();
  expect(screen.getByText(/nothing is compared/)).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Totals" })).not.toHaveTextContent("vs the period");
});

test("a shortfall comes in as a deficit, savings taken back as such, and the rest goes negative", async () => {
  api(() => ({
    ...report,
    totals: figures("1000.00", "1500.00", "-200.00", "-300.00"),
    flows: [
      { kind: "income", side: "in", amount: "1000.00", category_id: null, name: null, over: false },
      {
        kind: "from_savings",
        side: "in",
        amount: "200.00",
        category_id: null,
        name: null,
        over: false,
      },
      {
        kind: "spending",
        side: "out",
        amount: "1500.00",
        category_id: "c-housing",
        name: "Housing",
        over: false,
      },
      { kind: "deficit", side: "in", amount: "300.00", category_id: null, name: null, over: false },
    ],
  }));
  render(<TestApp path="/reports" />);

  const summary = await screen.findByRole("region", { name: "Totals" });
  expect(plain(summary.textContent)).toContain("Rest-€300");
  const flows = screen.getByRole("region", { name: "Money flows" });
  const rows = within(within(flows).getByRole("table", { name: "Money flows" }))
    .getAllByRole("row")
    .map((r) => plain(r.textContent));
  expect(rows).toContain("InTaken from savings€20013%");
  expect(rows).toContain("InDeficit€30020%");
  expect(rows).toContain("OutHousing€1,500100%within its targets, or without one");
  expect(within(flows).getByRole("list", { name: "Colours" })).toHaveTextContent("Deficit");
});

test("a period not compared leaves the period before blank in the table", async () => {
  api(() => ({
    ...report,
    start: "2026-06",
    first_month: "2026-01",
    compared: false,
    changes: { income: null, spent: null, saved: null, rest: null },
    rows: report.rows.map((r) => ({ ...r, previous: "0.00", change: null })),
  }));
  render(<TestApp path="/reports" />);

  expect(
    await screen.findByText(/The period before starts before Jan 2026, the first month/),
  ).toBeInTheDocument();
  const table = screen.getByRole("table", { name: "By category" });
  const housing = within(table)
    .getAllByRole("row")
    .map((r) => plain(r.textContent))
    .find((text) => text?.startsWith("Housing"));
  expect(housing).toBe("Housing€12,000€1,00057%");
});

test("a custom period that has not started is not asked for", async () => {
  const asked = api();
  render(<TestApp path="/reports" />);
  const user = userEvent.setup();
  await screen.findByRole("region", { name: "Totals" });
  await user.selectOptions(screen.getByLabelText("Period"), "custom");
  const count = asked.length;
  fireEvent.change(screen.getByLabelText("First month"), { target: { value: "2027-03" } });
  fireEvent.change(screen.getByLabelText("Last month"), { target: { value: "2027-04" } });

  expect(screen.getByRole("alert")).toHaveTextContent(/choose a first month that has started/);
  expect(asked.length).toBe(count);
});
