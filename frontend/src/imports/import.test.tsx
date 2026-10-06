import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => vi.unstubAllGlobals());

const account = {
  id: "a1",
  name: "Compte courant",
  institution: "Société Générale",
  type: "checking",
  visibility: "shared",
  owner_id: owner.id,
  owner_name: "Wilson",
  opening_balance: "336.95",
  opening_date: "2026-03-01",
  closed_on: null,
  balance: "1234.56",
};
const row = (line: number, label: string, amount: string, status: string) => ({
  line,
  booked_on: "2026-03-14",
  label,
  amount,
  status,
});
const preview = {
  format: "societe_generale_checking",
  format_label: "Société Générale — checking account (CSV)",
  period: { start: "2026-03-01", end: "2026-03-14" },
  bank_balance: { on: "2026-03-14", amount: "1234.56" },
  counts: { new: 2, duplicate: 1, before_opening: 1, error: 1 },
  rows: [
    row(4, "CARTE BOULANGERIE", "-4.20", "new"),
    row(5, "VIR RECU SALAIRE", "2480.15", "new"),
    row(6, "CARTE CAFE", "-1.10", "duplicate"),
    { ...row(7, "OLD", "-3.00", "before_opening"), booked_on: "2026-02-27" },
  ],
  errors: [{ line: 8, message: "invalid date '32/03/2026', expected DD/MM/YYYY" }],
  already_imported_at: null,
};
const batch = {
  id: "b1",
  format: "societe_generale_checking",
  file_name: "export.csv",
  created_at: "2026-03-15T10:00:00Z",
  imported_count: 2,
  duplicate_count: 1,
  skipped_count: 1,
  error_count: 1,
  period: { start: "2026-03-01", end: "2026-03-14" },
  rolled_back_at: null as string | null,
  balance_check: { on: "2026-03-14", bank: "1234.56", computed: "1234.56", difference: "0.00" },
};

function api(extra: Record<string, (body: unknown) => Response> = {}) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/accounts": () => Response.json([account]),
    "GET /api/accounts/a1/imports": () => Response.json([]),
    "POST /api/accounts/a1/imports/preview": () => Response.json(preview),
    ...extra,
  });
}

const csv = () => new File(["fake"], "export.csv", { type: "text/csv" });

async function choose() {
  const user = userEvent.setup();
  await user.upload(await screen.findByLabelText("Bank export (CSV)"), csv());
  return user;
}

test("the accounts page shows the current balance and an import link", async () => {
  api();
  render(<TestApp path="/accounts" />);

  const row = (await screen.findByRole("list", { name: "Société Générale" })).querySelector("li");
  expect(row).toHaveTextContent("1 234,56 €");
  expect(row).toHaveTextContent("opening 336,95 € on 1 Mar 2026");
  const user = userEvent.setup();
  await user.click(screen.getByRole("link", { name: "Import into Compte courant" }));
  expect(
    await screen.findByRole("heading", { name: "Import into Compte courant" }),
  ).toBeInTheDocument();
});

test("the preview shows what will be imported, skipped and why", async () => {
  const calls = api();
  render(<TestApp path="/accounts/a1/import" />);

  await choose();

  expect(await screen.findByText("Société Générale — checking account (CSV)")).toBeInTheDocument();
  expect(
    screen.getByText("2 new · 1 already imported · 1 before the opening date · 1 error"),
  ).toBeInTheDocument();
  const table = screen.getByRole("table", { name: "Rows in the file" });
  expect(within(table).getAllByRole("row")).toHaveLength(5);
  expect(within(table).getByText("2 480,15 €")).toBeInTheDocument();
  expect(screen.getByText(/Line 8: invalid date/)).toBeInTheDocument();
  const sent = calls.find((c) => c.route === "POST /api/accounts/a1/imports/preview")?.body;
  // jsdom's File reaches undici as a nameless Blob; browsers keep the name (checked in Chrome).
  expect(sent).toContain('Content-Disposition: form-data; name="file"');
});

test("importing reports the result and the balance check", async () => {
  const calls = api({
    "POST /api/accounts/a1/imports": () => Response.json(batch, { status: 201 }),
  });
  render(<TestApp path="/accounts/a1/import" />);

  const user = await choose();
  await user.click(await screen.findByRole("button", { name: "Import 2 new operations" }));

  expect(await screen.findByText("2 operations imported.")).toBeInTheDocument();
  expect(
    screen.getByText(/The balance matches the bank: 1 234,56 € on 14 Mar 2026/),
  ).toBeInTheDocument();
  expect(calls.some((c) => c.route === "POST /api/accounts/a1/imports")).toBe(true);
});

test("a balance that differs from the bank is flagged", async () => {
  api({
    "POST /api/accounts/a1/imports": () =>
      Response.json(
        {
          ...batch,
          balance_check: {
            on: "2026-03-14",
            bank: "1234.56",
            computed: "1197.61",
            difference: "-36.95",
          },
        },
        { status: 201 },
      ),
  });
  render(<TestApp path="/accounts/a1/import" />);

  const user = await choose();
  await user.click(await screen.findByRole("button", { name: "Import 2 new operations" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The computed balance (1 197,61 €) differs from the bank's (1 234,56 €) by -36,95 €",
  );
});

test("a file already imported is announced and cannot add anything", async () => {
  api({
    "POST /api/accounts/a1/imports/preview": () =>
      Response.json({
        ...preview,
        counts: { new: 0, duplicate: 3, before_opening: 0, error: 0 },
        rows: preview.rows.slice(0, 3).map((r) => ({ ...r, status: "duplicate" })),
        errors: [],
        already_imported_at: "2026-03-15T10:00:00Z",
      }),
  });
  render(<TestApp path="/accounts/a1/import" />);

  await choose();

  expect(
    await screen.findByText(/This file was already imported on 15 Mar 2026/),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Nothing new to import" })).toBeDisabled();
});

test("a file the API cannot read is explained", async () => {
  api({
    "POST /api/accounts/a1/imports/preview": () =>
      Response.json(
        {
          detail: "unrecognised file format: export a CSV of the operations from Société Générale",
        },
        { status: 422 },
      ),
  });
  render(<TestApp path="/accounts/a1/import" />);

  await choose();

  expect(await screen.findByRole("alert")).toHaveTextContent("Unrecognised file format");
});

test("an import can be rolled back after confirming", async () => {
  let batches = [batch];
  const calls = api({
    "GET /api/accounts/a1/imports": () => Response.json(batches),
    "DELETE /api/imports/b1": () => {
      batches = [{ ...batch, rolled_back_at: "2026-03-16T09:00:00Z" }];
      return new Response(null, { status: 204 });
    },
  });
  render(<TestApp path="/accounts/a1/import" />);

  const user = userEvent.setup();
  const history = await screen.findByRole("list", { name: "Previous imports" });
  expect(history).toHaveTextContent("export.csv");
  await user.click(within(history).getByRole("button", { name: "Roll back" }));
  expect(calls.some((c) => c.route === "DELETE /api/imports/b1")).toBe(false);
  await user.click(
    within(history).getByRole("button", { name: "Confirm: delete its 2 operations" }),
  );

  expect(await within(history).findByText(/Rolled back on 16 Mar 2026/)).toBeInTheDocument();
  expect(calls.some((c) => c.route === "DELETE /api/imports/b1")).toBe(true);
});

test("rows before the opening date are explained and the account can be opened earlier", async () => {
  let previews = 0;
  const calls = api({
    "POST /api/accounts/a1/imports/preview": () => {
      previews += 1;
      return Response.json(preview);
    },
    "PATCH /api/accounts/a1": (body) => Response.json({ ...account, ...(body as object) }),
  });
  render(<TestApp path="/accounts/a1/import" />);

  const user = await choose();

  expect(
    await screen.findByText(/1 operation is before the account's opening date \(1 Mar 2026\)/),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Open the account on 27 Feb 2026" }));

  await vi.waitFor(() => expect(previews).toBe(2));
  expect(calls.find((c) => c.route === "PATCH /api/accounts/a1")?.body).toEqual({
    opening_date: "2026-02-27",
  });
});
