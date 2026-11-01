import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";
import type { ForecastOut, ForecastPageOut } from "../api/generated";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

const band = (low: string, point: string, high: string) => ({ low, point, high });
const flat = (point: string) => band(point, point, point);
const ahead = Array.from({ length: 12 }, (_, k) => {
  const month = `${k < 3 ? 2026 : 2027}-${String(((k + 9) % 12) + 1).padStart(2, "0")}`;
  return {
    month,
    income: band("3000.00", "3200.00", "3400.00"),
    spent: band("2100.00", "2400.00", "2700.00"),
    saved: flat("400.00"),
    rest: band("100.00", "400.00", "700.00"),
    fixed: "900.00",
  };
});
const history = Array.from({ length: 24 }, (_, k) => {
  const index = 2024 * 12 + 9 + k; // Oct 2024 to Sep 2026
  return {
    month: `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`,
    income: "3200.00",
    spent: "2350.00",
    saved: "400.00",
    fixed: "900.00",
    rest: "450.00",
  };
});
const groceries = {
  category_id: "c-groceries",
  name: "Groceries",
  kind: "expense" as const,
  point: "640.00",
  band: band("560.00", "640.00", "720.00"),
  target: "550.00",
  risk: "likely" as const,
  chance: "0.8800",
  to_date: null,
};
const forecast: ForecastOut = {
  origin: "2026-09",
  history,
  ahead,
  totals: {
    income: band("37000.00", "38400.00", "39800.00"),
    spent: band("26000.00", "28800.00", "31000.00"),
    saved: flat("4800.00"),
    rest: band("2000.00", "4800.00", "7000.00"),
    banded: true,
  },
  month: {
    month: "2026-10",
    entered: "1500.00",
    expected: band("2100.00", "2400.00", "2700.00"),
    elapsed: "0.9032",
  },
  rest_above: "165.00",
  band: { none: false, widened_from: null },
  targets: [
    groceries,
    { ...groceries, category_id: "c-leisure", name: "Leisure", risk: "unlikely", chance: "0.1" },
  ],
  objectives: [
    {
      ...groceries,
      category_id: "c-pea",
      name: "PEA",
      kind: "savings",
      point: "300.00",
      target: "300.00",
      risk: "possible",
      chance: "0.4",
    },
  ],
  year: 2026,
  year_targets: [{ ...groceries, point: "6800.00", target: "6600.00", to_date: "5200.00" }],
  income: [
    { category_id: "c-salary", name: "Salary", band: band("3000.00", "3200.00", "3400.00") },
  ],
  reliability: [
    {
      category_id: "c-groceries",
      name: "Groceries",
      kind: "expense",
      method: { model: "trees", contest: true, features: ["lag1", "mean6"], set_aside: null },
      known: "0.00",
      mase: "0.8123",
      wape: "0.1200",
      versus: "0.1500",
      bias: "0.0300",
      optimism: "0.0300",
      coverage: "0.8000",
    },
  ],
  bias_limit: "0.05",
  scores: [
    {
      name: "income",
      mase: "0.5",
      wape: "0.02",
      rmsse: "0.6",
      bias_share: "0",
      bias_per_month: null,
    },
    {
      name: "spent",
      mase: "0.9",
      wape: "0.1",
      rmsse: "1",
      bias_share: "0.03",
      bias_per_month: null,
    },
    { name: "saved", mase: null, wape: null, rmsse: null, bias_share: null, bias_per_month: null },
    {
      name: "rest",
      mase: "1.1",
      wape: null,
      rmsse: "1.2",
      bias_share: null,
      bias_per_month: "-165.00",
    },
  ],
  backtest: [
    {
      name: "spent",
      points: [{ month: "2025-10", entered: "2300.00", forecast: "2250.00" }],
    },
  ],
  engine: { cuts: 12, months: 36, seed: 20261028, version: 2, models: {} },
};

function serve(page: ForecastPageOut, language = "en") {
  fakeApi({
    "GET /api/auth/me": () => Response.json({ ...owner, language }),
    "GET /api/forecast": () => Response.json(page),
  });
}

test("the forecast is a tab of the spending and answers first in tiles", async () => {
  serve({ complete_months: 36, needed: 12, forecast });
  render(<TestApp path="/forecast" />);

  expect(await screen.findByRole("heading", { name: "Forecast" })).toBeVisible();
  const tab = screen.getByRole("link", { name: "Forecast" });
  expect(tab).toHaveAttribute("aria-current", "page");

  const rest = await screen.findByLabelText(/^Rest, Oct 2026 to Sept? 2027$/); // "Sep" or "Sept", by ICU version;
  expect(within(rest).getByText("€4,800")).toBeVisible();
  expect(
    within(rest).getByText(/leaving a rest of €4,800 \(between €2,000 and €7,000/),
  ).toBeVisible();
  expect(screen.getByText(/this forecast put the rest/)).toHaveTextContent(
    "this forecast put the rest €165 a month above what was left",
  );
  const month = screen.getByLabelText("Oct 2026 so far");
  expect(
    within(month).getByText("€1,500 spent so far in Oct 2026, €2,400 expected for the month."),
  ).toBeVisible();
  const targets = screen.getByLabelText("Targets this month");
  expect(within(targets).getByText("1 at risk of 2")).toBeVisible();
  expect(within(targets).getByText("1 likely over")).toBeVisible();
  expect(screen.getByLabelText("Targets in 2026")).toHaveTextContent("Groceries");
});

test("each chart has its table and the method is folded", async () => {
  serve({ complete_months: 36, needed: 12, forecast });
  render(<TestApp path="/forecast" />);

  expect(
    await screen.findByRole("img", { name: /Each expense category's forecast/ }),
  ).toBeVisible();
  const table = screen.getByRole("table", { name: "Against the targets" });
  expect(within(table).getByText("90%")).toBeInTheDocument();
  expect(within(table).getAllByText("likely over")[0]).toBeInTheDocument();
  expect(screen.getByText("PEA: €300 for €300, may fall short")).toBeVisible();

  const methods = screen.getByRole("table", { name: "What the forecast rests on" });
  expect(
    within(methods).getByText(
      "trees learnt on all the categories, mostly from the last month, the 6-month average",
    ),
  ).toBeInTheDocument();
  expect(within(methods).getByText("0.81")).toBeInTheDocument();
  expect(within(methods).getByText("errs 15% less")).toBeInTheDocument();
  expect(within(methods).getByText("3% less spending than was entered")).toBeInTheDocument();
  expect(screen.getByText("the rest €165 a month above what was left")).toBeInTheDocument();
  expect(screen.getByText(/Foundation models not installed/)).toBeInTheDocument();
});

test("a new household is told how many months it has", async () => {
  serve({ complete_months: 3, needed: 12, forecast: null });
  render(<TestApp path="/forecast" />);

  expect(
    await screen.findByText(
      "A forecast needs 12 complete months of spending; there are 3 so far. Open the demo from the account menu to try it.",
    ),
  ).toBeVisible();
});

test("the forecast follows the language", async () => {
  serve({ complete_months: 36, needed: 12, forecast }, "fr");
  render(<TestApp path="/forecast" />);

  expect(await screen.findByRole("heading", { name: "Prévision" })).toBeVisible();
  expect(await screen.findByLabelText("Le reste, oct. 2026 à sept. 2027")).toBeVisible();
  expect(screen.getByRole("heading", { name: "Face aux objectifs" })).toBeVisible();
  const methods = screen.getByRole("table", { name: "Sur quoi repose la prévision" });
  expect(within(methods).getByText("0,81")).toBeInTheDocument();
});
