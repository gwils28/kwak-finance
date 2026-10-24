import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => {
  delete document.documentElement.dataset.theme;
});

test("the projection embeds the Dash page in the app's language and theme", async () => {
  document.documentElement.dataset.theme = "dark";
  fakeApi({ "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }) });
  render(<TestApp path="/wealth/projection" />);

  expect(await screen.findByRole("heading", { name: "Projection du patrimoine" })).toBeVisible();
  const frame = screen.getByTitle("Les graphiques de la projection");
  expect(frame).toHaveAttribute("src", "/dash/projection?lang=fr&theme=dark");

  // Switching the theme reloads the page in the new one.
  document.documentElement.dataset.theme = "light";
  await waitFor(() => expect(frame).toHaveAttribute("src", "/dash/projection?lang=fr&theme=light"));
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

test("the assumptions are set under the charts and reload them", async () => {
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

  const frame = await screen.findByTitle("The projection's charts");
  const source = frame.getAttribute("src");
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
  // The Dash page is loaded again with the new assumptions.
  expect(screen.getByTitle("The projection's charts")).not.toBe(frame);
  expect(screen.getByTitle("The projection's charts").getAttribute("src")).toBe(source);

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
