import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import type { AuditOut } from "../api/generated";
import { MESSAGES } from "../i18n";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";
import { buildDocument, labelText, toMarkdown } from "./document";

afterEach(() => vi.unstubAllGlobals());

const plain = (text: string | null | undefined) => text?.replace(/[  ]/g, " ");

const spread = (total: string, average: string) => ({
  total,
  average,
  lowest_month: "2026-09",
  lowest: average,
  highest_month: "2026-10",
  highest: average,
});

function auditOut(overrides: Partial<AuditOut> = {}): AuditOut {
  return {
    audience: "banker",
    scope: "household",
    language: "en",
    privacy: { named_members: true, named_lines: true, exact_amounts: true },
    generated_at: "2026-11-14T12:00:00Z",
    period: { start: "2026-09", end: "2026-10", months: 2, shortened: true },
    household: {
      name: "Home",
      members: [{ label: { name: "Wilson" }, age: 34 }],
    },
    money: {
      months: [
        { month: "2026-09", income: "3000.00", spent: "1355.00", saved: "0.00", rest: "1645.00" },
        { month: "2026-10", income: "3300.00", spent: "1355.00", saved: "0.00", rest: "1945.00" },
      ],
      income: spread("6300.00", "3150.00"),
      spent: spread("2710.00", "1355.00"),
      saved: spread("0.00", "0.00"),
      rest: spread("3590.00", "1795.00"),
      no_income: [],
      income_by_category: [{ name: "Salaries", amount: "6000.00" }],
      spending_by_category: [{ name: "Housing", amount: "1800.00" }],
      spending_rest: "910.00",
      fixed: [{ category: "Housing", frequency: "monthly", monthly: "900.00" }],
      fixed_monthly: "900.00",
      savings_rate: "57.0",
      saved_share: "0.0",
      capacity: "1795.00",
      capacity_start: "2026-09",
      capacity_end: "2026-10",
      capacity_set: false,
      years: [
        {
          year: 2026,
          months: 2,
          partial: true,
          income: "6300.00",
          spent: "2710.00",
          saved: "0.00",
          rest: "3590.00",
        },
      ],
    },
    wealth: {
      month: "2026-10",
      categories: [
        {
          name: "Stocks",
          kind: "asset",
          colour: "stocks",
          value: "15000.00",
          share: "100.0",
          liquid: true,
        },
      ],
      lines: [
        {
          label: { name: "PEA Fortuneo" },
          category: "Stocks",
          kind: "asset",
          holder: { name: "Wilson" },
          value: "15000.00",
          carried: false,
          envelope: "pea",
          opening_year: 2019,
          age: 7,
          milestone: "reached",
          regulated: null,
          ceiling: null,
        },
      ],
      gross: "15000.00",
      debts: "0.00",
      net: "15000.00",
      liquid: "15000.00",
      illiquid: "0.00",
      start_month: "2026-08",
      start_net: "14000.00",
      change: "1000.00",
      holders: [{ holder: { name: "Wilson" }, net: "15000.00" }],
      debt_lines: [],
      carried: false,
    },
    ratio: {
      income: "3000.00",
      counted: ["Salaries"],
      left_out: ["Refunds"],
      payments: "1234.56",
      ratio: "41.2",
      above_ceiling: true,
      withholding: null,
      before_tax_ratio: null,
      before_tax_above: false,
      remaining: "1765.44",
      debts: [
        {
          label: { name: "Crédit auto" },
          owed: "12000.00",
          payment: "1224.56",
          insurance: "10.00",
          rate: "4.00",
          ends: "2027-08",
        },
      ],
      left_out_debts: [],
    },
    goals: { goals: [], precaution: "0.00", precaution_months: null },
    retirement: [],
    assumptions: [],
    project: null,
    ...overrides,
  };
}

const categories = [
  { id: "salaries", name: "Salaries", kind: "income", one_off: false, position: 0 },
  { id: "refunds", name: "Refunds", kind: "income", one_off: false, position: 1 },
];

function api(respond: (body: { audience: string; language: string }) => AuditOut) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/spending/categories": () => Response.json(categories),
    "POST /api/audit-document": (body) =>
      Response.json(respond(body as { audience: string; language: string })),
    "POST /api/audit-document/issued": () => new Response(null, { status: 204 }),
  });
}

test("the wealth tab leads to the banker's document, printed and logged", async () => {
  const calls = api(() => auditOut());
  const print = vi.fn();
  vi.stubGlobal("print", print);
  render(<TestApp path="/wealth" />);
  const user = userEvent.setup();
  const tabs = await screen.findByRole("navigation", { name: "Main" });
  await user.click(within(tabs).getByRole("link", { name: "Audit" }));

  const doc = await screen.findByRole("article");
  expect(
    within(doc).getByRole("heading", { name: "Financial file for a mortgage application" }),
  ).toBeInTheDocument();
  const sections = within(doc)
    .getAllByRole("heading", { level: 2 })
    .map((h) => h.textContent);
  expect(sections).toEqual([
    "Contents",
    "1. Household",
    "2. Income and spending, month by month",
    "3. Fixed expenses",
    "4. Running loans",
    "5. Debt ratio and remaining income",
    "6. Savings capacity",
    "7. Liquid wealth and emergency fund",
    "8. Definitions",
  ]);
  expect(plain(doc.textContent)).toContain(
    "Debt ratio after withholding: 41.2 %, above the 35 % ceiling.",
  );
  expect(plain(doc.textContent)).toContain("€1,234.56");
  expect(doc.textContent).toContain("not financial advice");

  await user.click(screen.getByRole("button", { name: "Print or save as PDF" }));
  expect(print).toHaveBeenCalled();
  await waitFor(() =>
    expect(calls.find((c) => c.route === "POST /api/audit-document/issued")?.body).toEqual({
      audience: "banker",
      scope: "household",
      start: "2026-09",
      end: "2026-10",
      how: "print",
    }),
  );
});

test("the AI chat gets an anonymised Markdown document with its prompt", async () => {
  const calls = api((body) =>
    auditOut({
      audience: body.audience as AuditOut["audience"],
      privacy: { named_members: false, named_lines: false, exact_amounts: true },
      household: { name: null, members: [{ label: { group: "member", key: "A" }, age: 34 }] },
    }),
  );
  render(<TestApp path="/wealth/audit" />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("radio", { name: "An AI chat" }));
  expect(screen.getByRole("checkbox", { name: "Members by name" })).not.toBeChecked();
  expect(screen.getByRole("checkbox", { name: "Exact amounts" })).toBeChecked();
  await waitFor(() =>
    expect(
      calls.some(
        (c) =>
          c.route === "POST /api/audit-document" &&
          (c.body as { audience: string }).audience === "ai",
      ),
    ).toBe(true),
  );
  const sent = calls.filter((c) => c.route === "POST /api/audit-document").at(-1)?.body as {
    privacy: object;
  };
  expect(sent.privacy).toEqual({
    named_members: false,
    named_lines: false,
    exact_amounts: true,
  });

  await screen.findByText("Member A, 34 years old");
  await user.click(screen.getByRole("button", { name: "Copy as Markdown" }));
  await screen.findByRole("button", { name: "Copied" });
  // user-event puts its own clipboard on the page.
  const markdown = await navigator.clipboard.readText();
  expect(markdown.startsWith("# Request")).toBe(true);
  expect(markdown).toContain("Do not name specific financial products or providers");
  expect(markdown).toContain("## Household");
  expect(markdown).toContain("| Line | Category | Holder | Envelope | Opened | Value |");
  expect(markdown).not.toContain("Home");
});

test("a French document follows its own language, the form the interface's", () => {
  const doc = buildDocument(auditOut({ language: "fr" }));
  expect(doc.title).toBe("Dossier financier pour une demande de prêt immobilier");
  const ratio = doc.sections.find((s) => s.id === "ratio");
  const text = plain(ratio?.blocks.map((b) => ("text" in b ? b.text : "")).join(" "));
  expect(text).toContain(
    "Taux d'endettement après prélèvement : 41,2 %, au-dessus du plafond de 35 %.",
  );
  expect(text).toContain("1 234,56 €");
});

test("pseudonyms are written in the document's language", () => {
  const en = MESSAGES.en.audit.doc;
  const fr = MESSAGES.fr.audit.doc;
  expect(labelText({ group: "member", key: "B" }, fr)).toBe("Membre B");
  expect(labelText({ group: "envelope", key: "life_insurance", number: 2 }, en)).toBe(
    "Life insurance 2",
  );
  expect(labelText({ group: "category", key: "Livrets", number: 1 }, fr)).toBe("Livrets 1");
  expect(labelText({ group: "tier", key: "long", number: 1 }, en)).toBe("Long-term goal 1");
  expect(labelText({ group: "tier", key: "long", number: 1 }, fr)).toBe("Objectif long terme 1");
});

test("the Markdown has one figure a cell and the closing statement", () => {
  const md = toMarkdown(buildDocument(auditOut({ audience: "notary" })), "Request", "Contents");
  expect(md).not.toContain("# Request");
  expect(md).toContain("# Wealth inventory for an accountant or notary");
  expect(md).toContain("| PEA Fortuneo | Stocks | Wilson | €15,000.00 |");
  expect(md).toContain("not its legal ownership");
  expect(md.trim().endsWith("not financial advice._")).toBe(true);
});
