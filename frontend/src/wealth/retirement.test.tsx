import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => {
  delete document.documentElement.dataset.theme;
});

const nobody = {
  birth: null,
  retirement: null,
  earnings: null,
  pension_month: null,
  pension: null,
  age_at_retirement: null,
  age_at_pension: null,
};
const retirement = {
  members: [
    { user_id: "u-me", display_name: "Wilson", me: true, ...nobody },
    {
      user_id: "u-partner",
      display_name: "Camille",
      me: false,
      birth: "1992-05",
      retirement: "2056-05",
      earnings: "2200.00",
      pension_month: "2056-05",
      pension: "1500.00",
      age_at_retirement: 64,
      age_at_pension: 64,
    },
  ],
  settings: {
    spending_share: "0.80",
    spending_amount: null,
    indexation: "-0.003",
    horizon_age: 95,
    default_spending_share: "0.80",
    default_indexation: "-0.003",
    default_horizon_age: 95,
  },
  spending: {
    average: "3200.00",
    debt_payments: "950.00",
    base: "2250.00",
    months: 6,
    retirement_spending: "1800.00",
  },
};

test("each member enters their retirement and anyone the household's settings", async () => {
  document.documentElement.dataset.theme = "dark";
  const calls = fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/retirement": () => Response.json(retirement),
    "PUT /api/retirement/me": () => Response.json(retirement),
    "PATCH /api/retirement/settings": () => Response.json(retirement),
    "GET /api/retirement/run": () => Response.json({ problem: "no_member", plan: null }),
  });
  const user = userEvent.setup();
  render(<TestApp path="/wealth/retirement" />);

  expect(await screen.findByRole("heading", { name: "Retirement" })).toBeVisible();
  expect(await screen.findByText(/Enter your birth month, your retirement/)).toBeVisible();
  expect(
    await screen.findByText(
      "Camille: stops working in May 2056 at 64, a pension of €1,500 a month.",
    ),
  ).toBeVisible();
  expect(screen.getByText(/of which €950 of loans, so €2,250 outside them/)).toBeVisible();

  fireEvent.change(screen.getByLabelText("Birth month"), { target: { value: "1990-03" } });
  fireEvent.change(screen.getByLabelText("Month I stop working"), {
    target: { value: "2054-03" },
  });
  await user.type(screen.getByLabelText("Net earnings that stop then (€ a month)"), "2500");
  await user.type(screen.getByLabelText("Net pension (€ a month)"), "1800");
  await user.click(screen.getByRole("button", { name: "Save my retirement" }));
  await waitFor(() =>
    expect(calls.find((c) => c.route === "PUT /api/retirement/me")?.body).toEqual({
      birth: "1990-03",
      retirement: "2054-03",
      earnings: "2500.00",
      pension_month: null,
      pension: "1800.00",
    }),
  );

  const share = screen.getByLabelText("Share (%)");
  expect(share).toHaveValue("80");
  await user.clear(share);
  await user.type(share, "90");
  const horizon = screen.getByLabelText("Horizon: the youngest member's age");
  await user.clear(horizon);
  await user.type(horizon, "120");
  await user.click(screen.getByRole("button", { name: "Save the settings" }));
  expect(await screen.findByText("The horizon is an age from 85 to 105.")).toBeVisible();
  await user.clear(horizon);
  await user.type(horizon, "90");
  await user.click(screen.getByRole("button", { name: "Save the settings" }));
  await waitFor(() =>
    expect(calls.find((c) => c.route === "PATCH /api/retirement/settings")?.body).toEqual({
      spending_share: "0.9",
      indexation: "-0.003",
      horizon_age: 90,
    }),
  );
});

const months = Array.from({ length: 13 }, (_, k) => ({
  month: `${2026 + Math.floor((11 + k) / 12)}-${String(((11 + k) % 12) + 1).padStart(2, "0")}`,
  p10: "100000.00",
  p25: "110000.00",
  p50: "120000.00",
  p75: "130000.00",
  p90: "140000.00",
  liquid: "120000.00",
}));
const plan = {
  this_month: "2026-12",
  retired: "2026-12",
  horizon: "2027-12",
  horizon_age: 95,
  youngest: "Wilson",
  youngest_age_at_horizon: 67,
  living: {
    pensions: "1000.00",
    withdrawal: "300.00",
    withdrawal_half: "320.00",
    spending: "1000.00",
    later_pension: false,
  },
  lasts: { chance: "0.9950", ten_age: null, half_age: null, shortfall: false },
  months,
  income: months.slice(1).map((m) => ({
    month: m.month,
    pensions: "1000.00",
    withdrawal: "300.00",
    spending: "1000.00",
  })),
  people: [
    {
      name: "Wilson",
      birth: "1960-12",
      retirement: "2026-12",
      age_at_retirement: 66,
      earnings: "0.00",
      pension_month: "2026-12",
      age_at_pension: 66,
      pension: "1000.00",
    },
  ],
  left_out: ["Camille"],
  spending: { retirement: "1000.00", share: null, base: "2250.00", months: 6 },
  indexation: "-0.003",
  engine: { paths: 5000, seed: 20261022, version: 1 },
};

test("the plan answers first: the standard of living, the share covered, how long it lasts", async () => {
  fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/retirement": () => Response.json(retirement),
    "GET /api/retirement/run": () => Response.json({ problem: null, plan }),
  });
  render(<TestApp path="/wealth/retirement" />);

  const living = await screen.findByLabelText("Standard of living from Dec 2026, 9 in 10");
  expect(within(living).getByText("€1,300 a month")).toBeVisible();
  expect(within(living).getByText("Pensions €1,000")).toBeVisible();
  expect(within(living).getByText("Withdrawal €300")).toBeVisible();
  expect(within(living).getByText("Spending €1,000")).toBeVisible();
  expect(
    within(living).getByText(
      /pensions of €1,000 and a sustainable withdrawal of €300 a month give €1,300 a month in 9 outcomes in 10 \(€1,300 in half of them\), for spending of €1,000: 130% covered\./,
    ),
  ).toBeVisible();
  const covered = screen.getByLabelText("Spending covered");
  expect(within(covered).getByText("130%")).toBeVisible();
  expect(within(covered).getByText("covered")).toBeVisible();
  const lasts = screen.getByLabelText("The wealth lasts to the horizon");
  expect(within(lasts).getByText("more than 99%")).toBeVisible();
  expect(within(lasts).getByText(/does not run out before 95\./)).toBeVisible();
  expect(screen.getByText("Pension €1,000")).toBeVisible();
  expect(screen.getByText("Left out, without a retirement entered: Camille.")).toBeVisible();
  expect(screen.getByText(/check yours on info-retraite\.fr/)).toBeVisible();
});
