import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => vi.unstubAllGlobals());

const tx = (id: string, account: string, amount: string, label: string, extra: object = {}) => ({
  id,
  account_id: account === "Compte courant" ? "a1" : "a2",
  account_name: account,
  booked_on: "2026-03-10",
  amount,
  label,
  source: "import",
  category_id: null,
  category_name: null,
  transfer_group_id: null,
  transfer_account_name: null,
  ...extra,
});
const outflow = tx("t1", "Compte courant", "-150.00", "000001 VIR PERM POUR: JEAN DUPONT");
const inflow = tx("t2", "Livret A", "150.00", "VIR RECU EPARGNE");
const side = (t: ReturnType<typeof tx>) => ({
  id: t.id,
  account_id: t.account_id,
  account_name: t.account_name,
  booked_on: t.booked_on,
  amount: t.amount,
  label: t.label,
});

function api(
  suggestions: unknown[],
  items: unknown[] = [outflow, inflow],
  extra: Record<string, (body: unknown, url: URL) => Response> = {},
) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/accounts": () => Response.json([]),
    "GET /api/categories": () => Response.json([]),
    "GET /api/transactions": () => Response.json({ items, total: items.length }),
    "GET /api/transfers/suggestions": () => Response.json(suggestions),
    ...extra,
  });
}

test("suggested transfers are announced and can be linked one by one", async () => {
  const calls = api([{ outflow: side(outflow), inflow: side(inflow) }], [outflow, inflow], {
    "POST /api/transfers": () => Response.json({ group_id: "g1" }, { status: 201 }),
  });
  render(<TestApp path="/transactions" />);

  const banner = await screen.findByRole("region", { name: "Transfers between your accounts" });
  expect(banner).toHaveTextContent("1 transfer between your accounts found");
  const user = userEvent.setup();
  await user.click(within(banner).getByRole("button", { name: "Review" }));
  const pair = within(banner).getByRole("listitem");
  expect(pair).toHaveTextContent("Compte courant");
  expect(pair).toHaveTextContent("Livret A");
  expect(pair).toHaveTextContent("150,00 €");
  await user.click(within(pair).getByRole("button", { name: "Link" }));

  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "POST /api/transfers")?.body).toEqual({
      outflow_id: "t1",
      inflow_id: "t2",
    }),
  );
});

test("every suggestion can be linked at once", async () => {
  const calls = api([{ outflow: side(outflow), inflow: side(inflow) }], [outflow, inflow], {
    "POST /api/transfers/accept-suggestions": () => Response.json({ linked: 1 }),
  });
  render(<TestApp path="/transactions" />);

  const banner = await screen.findByRole("region", { name: "Transfers between your accounts" });
  await userEvent.setup().click(within(banner).getByRole("button", { name: "Link all" }));

  expect(
    await screen.findByText("1 transfer linked: it no longer counts as spending."),
  ).toBeInTheDocument();
  expect(calls.some((c) => c.route === "POST /api/transfers/accept-suggestions")).toBe(true);
});

test("no banner without suggestions", async () => {
  api([]);
  render(<TestApp path="/transactions" />);
  await screen.findByRole("table", { name: "Transactions" });
  expect(screen.queryByRole("region", { name: "Transfers between your accounts" })).toBeNull();
});

test("a linked transfer shows its other account instead of a category, and can be unlinked", async () => {
  const linkedOut = { ...outflow, transfer_group_id: "g1", transfer_account_name: "Livret A" };
  const linkedIn = { ...inflow, transfer_group_id: "g1", transfer_account_name: "Compte courant" };
  const calls = api([], [linkedOut, linkedIn], {
    "DELETE /api/transfers/g1": () => new Response(null, { status: 204 }),
  });
  render(<TestApp path="/transactions" />);

  const table = await screen.findByRole("table", { name: "Transactions" });
  expect(within(table).getByText("Transfer to Livret A")).toBeInTheDocument();
  expect(within(table).getByText("Transfer from Compte courant")).toBeInTheDocument();
  expect(within(table).queryByLabelText(/^Category of/)).toBeNull();

  await userEvent.setup().click(
    within(table).getByRole("button", {
      name: "Unlink the transfer of 000001 VIR PERM POUR: JEAN DUPONT",
    }),
  );
  await vi.waitFor(() =>
    expect(calls.some((c) => c.route === "DELETE /api/transfers/g1")).toBe(true),
  );
});
