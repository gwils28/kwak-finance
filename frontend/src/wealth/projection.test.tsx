import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => {
  vi.unstubAllGlobals();
});

const stocks = {
  id: "c-stocks",
  name: "Stocks",
  colour: "stocks",
  preset: "stocks",
  ret: "0.070",
  volatility: "0.160",
  default_ret: "0.070",
  default_volatility: "0.160",
  median_growth: "0.058",
  own: false,
  contribution: null,
  contribution_indexed: true,
};
const loan = {
  id: "l-loan",
  name: "Crédit immobilier",
  owner_name: "Wilson",
  visibility: "shared",
  owed: "180000.00",
  payment: null,
  rate: "0.0000",
  insurance: "0.00",
  grows: false,
};
const assumptions = {
  inflation: "0.020",
  default_inflation: "0.020",
  categories: [stocks],
  debts: [loan],
};

test("the advanced assumptions are set in their fold", async () => {
  const calls = fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/projection/assumptions": () => Response.json(assumptions),
    "PUT /api/projection/categories/c-stocks": () =>
      Response.json({
        ...assumptions,
        categories: [{ ...stocks, ret: "0.065", median_growth: "0.053", own: true }],
      }),
    "PUT /api/projection/debts/l-loan": () =>
      Response.json({ ...assumptions, debts: [{ ...loan, payment: "300.00", grows: true }] }),
    "PUT /api/projection/inflation": () => Response.json({ ...assumptions, inflation: "0.025" }),
  });
  const user = userEvent.setup();
  render(<TestApp path="/wealth/projection" />);

  await user.click(await screen.findByText("Advanced assumptions: inflation, volatilities, debts"));
  const ret = await screen.findByRole("textbox", { name: "Return of Stocks" });
  expect(ret).toHaveValue("7");
  expect(screen.getByRole("textbox", { name: "Volatility of Stocks" })).toHaveValue("16");
  expect(screen.getByText("5.8%")).toBeVisible();

  await user.clear(ret);
  await user.type(ret, "6.55");
  await user.click(screen.getByRole("button", { name: "Save the assumption of Stocks" }));
  expect(await screen.findByText(/to 0.1 at most/)).toBeVisible();

  await user.clear(ret);
  await user.type(ret, "6.5");
  await user.click(screen.getByRole("button", { name: "Save the assumption of Stocks" }));
  await waitFor(() =>
    expect(calls.find((c) => c.route === "PUT /api/projection/categories/c-stocks")?.body).toEqual({
      ret: "0.065",
      volatility: "0.16",
    }),
  );
  expect(await screen.findByText("5.3%")).toBeVisible();

  await user.type(
    screen.getByRole("textbox", { name: "Monthly payment of Crédit immobilier" }),
    "300",
  );
  await user.click(screen.getByRole("button", { name: "Save the repayment of Crédit immobilier" }));
  await waitFor(() =>
    expect(calls.find((c) => c.route === "PUT /api/projection/debts/l-loan")?.body).toEqual({
      payment: "300.00",
      rate: "0",
      insurance: "0.00",
    }),
  );
  expect(
    await screen.findByText("The payment does not cover the month's interest: this debt grows."),
  ).toBeVisible();

  const inflation = screen.getByRole("textbox", { name: "Inflation (% a year)" });
  await user.clear(inflation);
  await user.type(inflation, "2.5");
  await user.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(calls.find((c) => c.route === "PUT /api/projection/inflation")?.body).toEqual({
      inflation: "0.025",
    }),
  );
});

const livret = {
  ...stocks,
  id: "c-livret",
  name: "Savings accounts",
  colour: "savings",
  preset: "savings",
  ret: "0.017",
  volatility: "0.000",
  default_ret: "0.017",
  default_volatility: "0.000",
  median_growth: "0.017",
  contribution: "150.00",
  contribution_indexed: false,
};
const crypto = {
  ...stocks,
  id: "c-crypto",
  name: "Crypto",
  colour: "crypto",
  preset: "crypto",
  ret: "0.080",
  volatility: "0.600",
  median_growth: "-0.056",
};
const withContributions = {
  ...assumptions,
  categories: [{ ...stocks, contribution: "300.00" }, livret, crypto],
};

const month = (m: string, p50: number, parts: [number, number, number, number]) => ({
  month: m,
  p10: String(p50 * 0.8),
  p25: String(p50 * 0.9),
  p50: String(p50),
  p75: String(p50 * 1.1),
  p90: String(p50 * 1.3),
  today: String(parts[0]),
  contributed: String(parts[1]),
  repaid: String(parts[2]),
  gains: String(parts[3]),
  debts: "0.00",
  shortfall: "0.00",
});

const run = {
  start_month: "2026-11",
  months: [
    month("2026-11", 84300, [84300, 0, 0, 0]),
    month("2027-11", 100000, [84300, 5400, 4000, 6300]),
  ],
  savings: {
    source: "declared",
    mode: "contributions",
    monthly: "450.00",
    capacity: "600.00",
    capacity_set: false,
    capacity_months: 6,
    share_of_capacity: "0.7500",
  },
  horizon: {
    median: "100000.00",
    p10: "80000.00",
    p90: "130000.00",
    income_median: "200.00",
    income_low: "150.00",
  },
  reach: { chance: "0.4200", half: "2027-09", ninety: null },
  shortfall_share: "0.0000",
  categories: [
    { id: "c-stocks", name: "Stocks", colour: "stocks", medians: ["22000.00", "30000.00"] },
  ],
  what_ifs: [],
  ceiling_note: false,
  paths: 5000,
  seed: 20261022,
  engine_version: 1,
};

function simulator(extra: Record<string, (body: unknown) => Response> = {}) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/projection/assumptions": () => Response.json(withContributions),
    "POST /api/projection/run": () => Response.json(run),
    ...extra,
  });
}

test("the simulator answers first: the median, its range, the income and its parts", async () => {
  simulator();
  render(<TestApp path="/wealth/projection" />);
  expect((await screen.findAllByText("€100,000"))[0]).toBeVisible();
  expect(screen.getByText("8 times in 10 between €80,000 and €130,000")).toBeVisible();
  expect(
    screen.getByText(
      "About €200 a month in half of the outcomes, €150 in nine in ten, at a 4% withdrawal rate.",
    ),
  ).toBeVisible();
  const parts = screen.getByRole("list", { name: "Where the money comes from" });
  expect(parts).toHaveTextContent("Contributions €5,400");
  expect(parts).toHaveTextContent("Debts repaid €4,000");
  expect(parts).toHaveTextContent("Gains after inflation €6,300");
  expect(
    screen.getByText(
      "To compare: your measured capacity is €600 a month, over 6 months. It is not used in the projection.",
    ),
  ).toBeVisible();
  // A volatile category says how little its median grows.
  expect(screen.queryByText(/Crypto swings a lot/)).toBeNull();
  expect(screen.getByRole("textbox", { name: "Monthly amount for Stocks" })).toHaveValue("300");
  expect(
    screen.getByRole("checkbox", { name: "Savings accounts follows prices" }),
  ).not.toBeChecked();
  // The month as Intl writes it ("Sep 2027" or "Sept 2027", by ICU version).
  expect(await screen.findByText(/^Sept? 2027$/)).toBeVisible();
  expect(screen.getAllByText("42%")[0]).toBeVisible();
});

test("typing a contribution reruns the projection without saving it, then saves it", async () => {
  const calls = simulator({
    "PUT /api/projection/contributions": () =>
      Response.json({
        ...withContributions,
        categories: [{ ...stocks, contribution: "400.00" }, livret, crypto],
      }),
  });
  const user = userEvent.setup();
  render(<TestApp path="/wealth/projection" />);

  const amount = await screen.findByRole("textbox", { name: "Monthly amount for Stocks" });
  await user.clear(amount);
  await user.type(amount, "400");
  expect(screen.getByText("Not saved")).toBeVisible();
  await waitFor(() =>
    expect(calls.filter((c) => c.route === "POST /api/projection/run").at(-1)?.body).toMatchObject({
      years: 20,
      today: true,
      contributions: [
        { category_id: "c-stocks", amount: "400.00", indexed: true },
        { category_id: "c-livret", amount: "150.00", indexed: false },
      ],
      returns: [],
    }),
  );
  expect(calls.some((c) => c.route === "PUT /api/projection/contributions")).toBe(false);

  await user.click(screen.getByRole("button", { name: "Save the contributions" }));
  await waitFor(() =>
    expect(calls.find((c) => c.route === "PUT /api/projection/contributions")?.body).toEqual({
      contributions: [
        { category_id: "c-stocks", amount: "400.00", indexed: true, ret: null },
        { category_id: "c-livret", amount: "150.00", indexed: false, ret: null },
      ],
      savings_source: null,
    }),
  );
  expect(await screen.findByText("Saved.")).toBeVisible();
});

test("a contribution can be added, warned of, and refused out of bounds", async () => {
  simulator();
  const user = userEvent.setup();
  render(<TestApp path="/wealth/projection" />);

  await user.click(await screen.findByRole("button", { name: /Add a contribution/ }));
  expect(
    await screen.findByText(/Crypto swings a lot: its median grows by only -5.6%/),
  ).toBeVisible();
  const amount = screen.getByRole("textbox", { name: "Monthly amount for Crypto" });
  await user.clear(amount);
  await user.type(amount, "0.5");
  expect(screen.getByText("A contribution is from €1 to €100,000 a month.")).toBeVisible();
  expect(screen.getByRole("button", { name: "Save the contributions" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Remove Crypto" }));
  expect(screen.queryByRole("textbox", { name: "Monthly amount for Crypto" })).toBeNull();
});

test("a what-if is posted with the fields typed and drawn dashed", async () => {
  const calls = simulator();
  const user = userEvent.setup();
  render(<TestApp path="/wealth/projection" />);

  await user.click(await screen.findByRole("checkbox", { name: "Compare what-if 1" }));
  await user.type(
    screen.getAllByRole("textbox", { name: "Total a month (€)" })[0] as HTMLElement,
    "800",
  );
  await waitFor(() =>
    expect(calls.filter((c) => c.route === "POST /api/projection/run").at(-1)?.body).toMatchObject({
      what_ifs: [{ savings: "800.00", inflation: null, category_id: null }],
    }),
  );
});

test("without wealth the simulator asks for it, in French", async () => {
  fakeApi({
    "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }),
    "GET /api/projection/assumptions": () => Response.json(assumptions),
    "POST /api/projection/run": () => Response.json({ detail: "no wealth" }, { status: 404 }),
  });
  render(<TestApp path="/wealth/projection" />);
  expect(await screen.findByRole("heading", { name: "Projection du patrimoine" })).toBeVisible();
  expect(await screen.findByText(/Aucune ligne de patrimoine dans ce périmètre/)).toBeVisible();
  expect(screen.getByText(/la capacité est répartie comme votre patrimoine/)).toBeVisible();
});

test("the savings can come from the history or from the contributions alone", async () => {
  const calls = simulator({
    "PUT /api/projection/contributions": () =>
      Response.json({ ...withContributions, savings_source: "measured" }),
  });
  const user = userEvent.setup();
  render(<TestApp path="/wealth/projection" />);

  await screen.findByRole("textbox", { name: "Monthly amount for Stocks" });
  expect(screen.getByRole("button", { name: "Declared" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByText(/uses only the contributions below/)).toBeVisible();

  await user.click(screen.getByRole("button", { name: "Measured" }));
  await waitFor(() =>
    expect(calls.filter((c) => c.route === "POST /api/projection/run").at(-1)?.body).toMatchObject({
      savings_source: "measured",
    }),
  );
  expect(screen.getByRole("heading", { name: "Split of the savings" })).toBeVisible();
  expect(
    screen.getByText(/Measured over 6 months only: one exceptional month skews it/),
  ).toBeVisible();
  expect(screen.getByText("Not saved")).toBeVisible();

  await user.click(screen.getByRole("button", { name: "Save the contributions" }));
  await waitFor(() =>
    expect(calls.find((c) => c.route === "PUT /api/projection/contributions")?.body).toMatchObject({
      savings_source: "measured",
    }),
  );
});
