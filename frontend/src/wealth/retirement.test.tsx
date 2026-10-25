import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  });
  const user = userEvent.setup();
  render(<TestApp path="/wealth/retirement" />);

  expect(await screen.findByRole("heading", { name: "Retirement" })).toBeVisible();
  expect(screen.getByTitle("The retirement's charts")).toHaveAttribute(
    "src",
    "/dash/retirement?lang=en&theme=dark",
  );
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
