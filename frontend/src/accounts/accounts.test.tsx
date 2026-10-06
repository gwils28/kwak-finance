import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => vi.unstubAllGlobals());

const checking = {
  id: "a1",
  name: "Compte courant",
  institution: "Société Générale",
  type: "checking",
  visibility: "shared",
  owner_id: owner.id,
  owner_name: "Wilson",
  opening_balance: "1234.56",
  opening_date: "2026-01-01",
  closed_on: null,
};
const partnerSavings = {
  ...checking,
  id: "a2",
  name: "Livret Jeune",
  type: "savings",
  owner_id: "someone-else",
  owner_name: "Partner",
  opening_balance: "-20.00",
};

function api(accounts: unknown[], extra: Record<string, (body: unknown) => Response> = {}) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/accounts": () => Response.json(accounts),
    "GET /api/institutions": () => Response.json(["Société Générale"]),
    ...extra,
  });
}

async function openForm() {
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Add an account" }));
  return user;
}

async function fillForm(user: ReturnType<typeof userEvent.setup>, balance: string) {
  await user.type(screen.getByLabelText("Account name"), "Livret A");
  await user.type(screen.getByLabelText("Institution"), "Société Générale");
  await user.selectOptions(screen.getByLabelText("Type"), "savings");
  await user.clear(screen.getByLabelText("Opening balance (€)"));
  await user.type(screen.getByLabelText("Opening balance (€)"), balance);
  await user.clear(screen.getByLabelText("Opening date"));
  await user.type(screen.getByLabelText("Opening date"), "2026-01-01");
  await user.click(screen.getByRole("button", { name: "Save" }));
}

test("accounts are grouped by institution with their opening balance", async () => {
  api([checking, partnerSavings]);
  render(<TestApp path="/accounts" />);

  const group = await screen.findByRole("list", { name: "Société Générale" });
  const rows = within(group).getAllByRole("listitem");
  expect(rows).toHaveLength(2);
  expect(rows[0]).toHaveTextContent("Compte courant");
  expect(rows[0]).toHaveTextContent("Checking");
  expect(rows[0]).toHaveTextContent("Shared");
  expect(rows[0]).toHaveTextContent("1 234,56 €");
  expect(rows[0]).not.toHaveTextContent("Partner");
  expect(rows[1]).toHaveTextContent("Savings");
  expect(rows[1]).toHaveTextContent("Partner");
  expect(rows[1]).toHaveTextContent("-20,00 €");
});

test("an empty household is invited to add its first account", async () => {
  api([]);
  render(<TestApp path="/accounts" />);
  expect(await screen.findByText(/No accounts yet/)).toBeInTheDocument();
});

test("adding an account accepts a French decimal comma", async () => {
  let accounts: unknown[] = [];
  const calls = api(accounts, {
    "GET /api/accounts": () => Response.json(accounts),
    "POST /api/accounts": (body) => {
      accounts = [{ ...checking, ...(body as object), id: "a3", institution: "Société Générale" }];
      return Response.json(accounts[0], { status: 201 });
    },
  });
  render(<TestApp path="/accounts" />);

  const user = await openForm();
  await fillForm(user, "1 500,5");

  expect(await screen.findByText("Livret A")).toBeInTheDocument();
  expect(calls.find((c) => c.route === "POST /api/accounts")?.body).toEqual({
    name: "Livret A",
    institution_name: "Société Générale",
    type: "savings",
    visibility: "private",
    opening_balance: "1500.50",
    opening_date: "2026-01-01",
  });
});

test("an amount with more than two decimals is refused before sending", async () => {
  const calls = api([]);
  render(<TestApp path="/accounts" />);

  const user = await openForm();
  await fillForm(user, "12,345");

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Enter an amount in euros with at most 2 decimals, e.g. 1234,56.",
  );
  expect(calls.some((c) => c.route === "POST /api/accounts")).toBe(false);
});

test("a duplicate name is explained", async () => {
  api([checking], {
    "POST /api/accounts": () =>
      Response.json(
        { detail: "this institution already has an account with this name" },
        { status: 409 },
      ),
  });
  render(<TestApp path="/accounts" />);

  const user = await openForm();
  await fillForm(user, "0");

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "This institution already has an account with this name.",
  );
});

test("an account can be renamed", async () => {
  const calls = api([checking], {
    "PATCH /api/accounts/a1": (body) => Response.json({ ...checking, ...(body as object) }),
  });
  render(<TestApp path="/accounts" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Edit Compte courant" }));
  const name = screen.getByLabelText("Account name");
  await user.clear(name);
  await user.type(name, "Main account");
  await user.click(screen.getByRole("button", { name: "Save" }));

  expect(calls.find((c) => c.route === "PATCH /api/accounts/a1")?.body).toMatchObject({
    name: "Main account",
  });
});

test("only the owner can change who sees an account", async () => {
  api([partnerSavings]);
  render(<TestApp path="/accounts" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Edit Livret Jeune" }));

  expect(screen.getByLabelText("Visible to")).toBeDisabled();
  expect(screen.getByText("Only Partner can change this.")).toBeInTheDocument();
});

test("closing an account hides it until closed accounts are shown", async () => {
  let current = { ...checking };
  const calls = api([], {
    "GET /api/accounts": () => Response.json(current.closed_on ? [] : [current]),
    "PATCH /api/accounts/a1": (body) => {
      current = { ...current, ...(body as object) };
      return Response.json(current);
    },
  });
  render(<TestApp path="/accounts" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Close Compte courant" }));

  expect(await screen.findByText(/No accounts yet/)).toBeInTheDocument();
  const body = calls.find((c) => c.route === "PATCH /api/accounts/a1")?.body as {
    closed_on: string;
  };
  expect(body.closed_on).toMatch(/^\d{4}-\d{2}-\d{2}$/);
});

test("the header links to the accounts page", async () => {
  api([]);
  render(<TestApp path="/" />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("link", { name: "Accounts" }));
  expect(await screen.findByRole("heading", { name: "Accounts" })).toBeInTheDocument();
});
