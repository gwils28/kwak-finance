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

const totals = (spent: string, income: string, net: string) => ({
  spent,
  income,
  paid_in: "0.00",
  paid_out: "0.00",
  net,
  saved: "200.00",
  savings_rate: "0.3000",
});
const row = (extra: object) => ({
  category_id: null,
  name: null,
  monthly_average: "0.00",
  share: null,
  previous: "0.00",
  change: null,
  children: [],
  ...extra,
});
const report = {
  start: "2026-01",
  end: "2026-12",
  to_date: false,
  months: 12,
  previous_start: "2025-01",
  previous_end: "2025-12",
  totals: totals("21000.00", "30000.00", "9000.00"),
  previous: totals("20000.00", "29000.00", "9000.00"),
  changes: { income: "0.0345", spent: "0.0500", net: "0.0000", saved: null },
  sections: [
    {
      section: "income",
      amount: "30000.00",
      monthly_average: "2500.00",
      previous: "29000.00",
      change: "0.0345",
    },
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
    row({
      section: "income",
      category_id: "c-income",
      name: "Income",
      amount: "30000.00",
      monthly_average: "2500.00",
      share: "1.0000",
      previous: "29000.00",
      change: "0.0345",
      children: [
        row({
          section: "income",
          category_id: "c-salary",
          name: "Salary",
          amount: "30000.00",
          monthly_average: "2500.00",
          share: "1.0000",
          previous: "29000.00",
          change: "0.0345",
        }),
      ],
    }),
    row({
      section: "spending",
      category_id: "c-housing",
      name: "Housing",
      amount: "12000.00",
      monthly_average: "1000.00",
      share: "0.5714",
      previous: "10000.00",
      change: "0.2000",
    }),
    row({
      section: "spending",
      amount: "9000.00",
      monthly_average: "750.00",
      share: "0.4286",
      previous: "10000.00",
      change: "-0.1000",
    }),
  ],
  monthly: Array.from({ length: 12 }, (_, i) => ({
    month: `2026-${String(i + 1).padStart(2, "0")}`,
    income: "2500.00",
    spent: "1750.00",
    net: "750.00",
  })),
  flows: [
    {
      kind: "income",
      side: "in",
      amount: "30000.00",
      category_id: "c-salary",
      name: "Salary",
      parent_id: "c-income",
      parent_name: "Income",
    },
    {
      kind: "spending",
      side: "out",
      amount: "12000.00",
      category_id: "c-housing",
      name: "Housing",
      parent_id: null,
      parent_name: null,
    },
    {
      kind: "uncategorised",
      side: "out",
      amount: "9000.00",
      category_id: null,
      name: null,
      parent_id: null,
      parent_name: null,
    },
    {
      kind: "unallocated",
      side: "out",
      amount: "9000.00",
      category_id: null,
      name: null,
      parent_id: null,
      parent_name: null,
    },
  ],
};

function api(answer: (url: URL) => object = () => report) {
  const asked: URL[] = [];
  fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/accounts": () => Response.json([]),
    "GET /api/reports": (_, url) => {
      asked.push(url);
      return Response.json(answer(url));
    },
  });
  return asked;
}

test("the reports tab shows this year's totals against the year before", async () => {
  const asked = api();
  render(<TestApp path="/" />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("link", { name: "Reports" }));

  const summary = await screen.findByRole("region", { name: "Totals" });
  expect(plain(summary.textContent)).toContain("Spending€21,000+5% vs the period before");
  expect(plain(summary.textContent)).toContain("Savings rate30%");
  expect(plain(summary.textContent)).toContain("Of which saved€200Nothing the period before");
  expect(screen.getByText(/Compared with Jan 2025 – Dec 2025/)).toBeInTheDocument();
  expect(asked[0]?.searchParams.get("start")).toBe("2026-01");
  expect(asked[0]?.searchParams.get("end")).toBe("2026-12");
  expect(asked[0]?.searchParams.get("scope")).toBe("household");
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

test("the table lists each section's categories with their subcategories", async () => {
  api();
  render(<TestApp path="/reports" />);
  const table = await screen.findByRole("table", { name: "By category" });

  const rows = within(table)
    .getAllByRole("row")
    .map((r) => plain(r.textContent));
  expect(rows).toContain("Income€30,000€2,500100%€29,000+3%");
  expect(rows).toContain("Salary€30,000€2,500100%€29,000+3%");
  expect(rows).toContain("Housing€12,000€1,00057%€10,000+20%");
  expect(rows).toContain("To categorise€9,000€75043%€10,000-10%");
  expect(rows).toContain("Total spending€21,000€1,750100%€20,000+5%");
});

test("the money flows of the period have no status", async () => {
  api();
  render(<TestApp path="/reports" />);
  const flows = await screen.findByRole("region", { name: "Money flows" });
  expect(within(flows).getByRole("list", { name: "Colours" })).toHaveTextContent("Spending");
  expect(within(flows).queryByText("Status")).not.toBeInTheDocument();
});

test("a period without transactions says so", async () => {
  api(() => ({ ...report, rows: [], flows: [] }));
  render(<TestApp path="/reports" />);
  expect(await screen.findByText("No transactions in this period.")).toBeInTheDocument();
});

test("in French, the reports speak French", async () => {
  fakeApi({
    "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }),
    "GET /api/accounts": () => Response.json([]),
    "GET /api/reports": () => Response.json(report),
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
