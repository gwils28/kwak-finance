import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => vi.unstubAllGlobals());

const account = {
  institution: "Société Générale",
  type: "checking",
  visibility: "shared",
  owner_id: owner.id,
  owner_name: "Wilson",
  opening_balance: "0.00",
  opening_date: "2026-03-01",
  closed_on: null,
  balance: "100.00",
};
const mine = { ...account, id: "a1", name: "Compte perso" };
const joint = { ...account, id: "a2", name: "Compte commun", visibility: "joint" };
const row = {
  account_id: "a1",
  account_name: "Compte perso",
  booked_on: "2026-03-10",
  source: "manual",
  bank_label: null,
  category_id: null,
  category_name: null,
  transfer_group_id: null,
  transfer_account_name: null,
  budget_month: "2026-03",
  budget_month_set: false,
  parts: [],
  note: null,
};
const share = { ...row, id: "t1", amount: "-500.00", label: "VIR QUOTE-PART" };
const side = (id: string, account: typeof mine, amount: string, label: string) => ({
  id,
  account_id: account.id,
  account_name: account.name,
  booked_on: "2026-03-12",
  amount,
  label,
});

type Handler = (body: unknown) => Response;

function api(extra: Record<string, Handler> = {}, items: object[] = [share]) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/accounts": () => Response.json([mine, joint]),
    "GET /api/categories": () => Response.json([]),
    "GET /api/transactions": () => Response.json({ items, total: items.length }),
    "GET /api/transfers/suggestions": () => Response.json([]),
    ...extra,
  });
}

const created = () =>
  Response.json(
    {
      group_id: "g1",
      outflow: side("t8", mine, "-500.00", "x"),
      inflow: side("t9", joint, "500.00", "y"),
    },
    { status: 201 },
  );

async function openTransferForm() {
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Add a transaction" }));
  const form = screen.getByRole("form", { name: "New transaction" });
  await user.click(within(form).getByRole("radio", { name: "Transfer" }));
  return { user, form };
}

test("a transfer is entered in one go, labelled after its accounts", async () => {
  const calls = api({ "POST /api/transfers/entries": created });
  render(<TestApp path="/transactions" />);

  const { user, form } = await openTransferForm();
  expect(within(form).queryByLabelText("Category")).not.toBeInTheDocument();
  expect(within(form).getByLabelText("From account")).toHaveValue("a1");
  expect(within(form).getByLabelText("To account")).toHaveValue("a2");
  await user.clear(within(form).getByLabelText("Date"));
  await user.type(within(form).getByLabelText("Date"), "2026-03-12");
  await user.type(within(form).getByLabelText("Amount (€)"), "500");
  await user.click(within(form).getByRole("button", { name: "Save" }));

  expect(calls.find((c) => c.route === "POST /api/transfers/entries")?.body).toEqual({
    source_account_id: "a1",
    destination_account_id: "a2",
    booked_on: "2026-03-12",
    amount: "500.00",
    outflow_label: "Transfer to Compte commun",
    inflow_label: "Transfer from Compte perso",
  });
});

test("a label given to a transfer goes on both sides", async () => {
  const calls = api({ "POST /api/transfers/entries": created });
  render(<TestApp path="/transactions" />);

  const { user, form } = await openTransferForm();
  await user.type(within(form).getByLabelText(/^Label/), "Quote-part mars");
  await user.type(within(form).getByLabelText("Amount (€)"), "500");
  await user.click(within(form).getByRole("button", { name: "Save" }));

  const body = calls.find((c) => c.route === "POST /api/transfers/entries")?.body;
  expect(body).toMatchObject({ outflow_label: "Quote-part mars", inflow_label: "Quote-part mars" });
});

test("a transfer needs two different accounts", async () => {
  const calls = api();
  render(<TestApp path="/transactions" />);

  const { user, form } = await openTransferForm();
  await user.selectOptions(within(form).getByLabelText("To account"), "a1");
  await user.type(within(form).getByLabelText("Amount (€)"), "500");
  await user.click(within(form).getByRole("button", { name: "Save" }));

  expect(within(form).getByRole("alert")).toHaveTextContent(/two different accounts/);
  expect(calls.some((c) => c.route === "POST /api/transfers/entries")).toBe(false);
});

test("a side of a transfer is edited without changing its direction", async () => {
  const linked = {
    ...share,
    label: "Transfer to Compte commun",
    transfer_group_id: "g1",
    transfer_account_name: "Compte commun",
  };
  api({}, [linked]);
  render(<TestApp path="/transactions" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Edit Transfer to Compte commun" }));
  const form = screen.getByRole("form", { name: "Edit transaction" });
  expect(within(form).queryByRole("radio")).not.toBeInTheDocument();
  expect(form).toHaveTextContent("Transfer to Compte commun: the other side follows");
});

test("a transaction is linked by hand to one of the same amount the other way", async () => {
  const calls = api({
    "GET /api/transfers/candidates/t1": () =>
      Response.json([side("t7", joint, "500.00", "VIR RECU WILSON")]),
    "POST /api/transfers": () => Response.json({ group_id: "g1" }, { status: 201 }),
  });
  render(<TestApp path="/transactions" />);

  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("button", { name: "Link VIR QUOTE-PART to a transfer" }),
  );
  const panel = screen.getByRole("region", { name: "Link to a transfer" });
  await user.click(
    await within(panel).findByRole("button", { name: "Link with VIR RECU WILSON of 12 Mar 2026" }),
  );

  expect(calls.find((c) => c.route === "POST /api/transfers")?.body).toEqual({
    outflow_id: "t1",
    inflow_id: "t7",
  });
  expect(await screen.findByText(/1 transfer linked/)).toBeInTheDocument();
});

test("linking by hand says when nothing matches", async () => {
  api({ "GET /api/transfers/candidates/t1": () => Response.json([]) });
  render(<TestApp path="/transactions" />);

  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("button", { name: "Link VIR QUOTE-PART to a transfer" }),
  );

  const panel = screen.getByRole("region", { name: "Link to a transfer" });
  expect(
    await within(panel).findByText(/No transaction of the opposite amount/),
  ).toBeInTheDocument();
});

test("in French, a transfer is labelled in French", async () => {
  const calls = api({
    "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }),
    "POST /api/transfers/entries": created,
  });
  render(<TestApp path="/transactions" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Ajouter une opération" }));
  const form = screen.getByRole("form", { name: "Nouvelle opération" });
  await user.click(within(form).getByRole("radio", { name: "Virement" }));
  await user.type(within(form).getByLabelText("Montant (€)"), "500");
  await user.click(within(form).getByRole("button", { name: "Enregistrer" }));

  expect(calls.find((c) => c.route === "POST /api/transfers/entries")?.body).toMatchObject({
    outflow_label: "Virement vers Compte commun",
    inflow_label: "Virement depuis Compte perso",
  });
});

test("a link that fails says so", async () => {
  api({
    "GET /api/transfers/candidates/t1": () =>
      Response.json([side("t7", joint, "500.00", "VIR RECU WILSON")]),
    "POST /api/transfers": () =>
      Response.json({ detail: "already part of a transfer" }, { status: 409 }),
  });
  render(<TestApp path="/transactions" />);

  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("button", { name: "Link VIR QUOTE-PART to a transfer" }),
  );
  const panel = screen.getByRole("region", { name: "Link to a transfer" });
  await user.click(
    await within(panel).findByRole("button", { name: "Link with VIR RECU WILSON of 12 Mar 2026" }),
  );

  expect(await within(panel).findByRole("alert")).toHaveTextContent(/already part of a transfer/);
});
