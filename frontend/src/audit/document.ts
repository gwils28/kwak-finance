/**
 * The audit document (§4.15) as plain blocks, in its own language: the page lays them out for
 * printing, the AI chat gets them as Markdown. Both read the same blocks, so they never differ.
 */
import type {
  Audience,
  AuditDebtOut,
  AuditLabelOut,
  AuditOut,
  AuditSpreadOut,
  Language,
} from "../api/generated";
import { MESSAGES } from "../i18n";
import { formatDateTimeIn } from "../lib/dates";
import {
  formatEurIn,
  formatEurWholeIn,
  formatRatePercentIn,
  formatTenthIn,
  formatTenthPercentIn,
} from "../lib/money";
import { monthLabelIn } from "../lib/months";

export type Block =
  | { kind: "p"; text: string }
  | { kind: "note"; text: string }
  | { kind: "list"; items: string[] }
  | { kind: "table"; head: string[]; rows: string[][]; numeric: boolean[] };

export type Section = { id: string; title: string; blocks: Block[] };

export type AuditDoc = {
  title: string;
  household: string;
  meta: [string, string][];
  prompt: string[] | null;
  sections: Section[];
  closing: string;
};

type Messages = (typeof MESSAGES)["en"];
type D = Messages["audit"]["doc"];

/** The sections each audience reads, in order (F-AUD-3); definitions close every document. */
const ORDER: Record<Audience, string[]> = {
  banker: [
    "household",
    "income",
    "fixed",
    "loans",
    "ratio",
    "capacity",
    "liquidity",
    "project",
    "definitions",
  ],
  advisor: [
    "household",
    "summary",
    "wealth",
    "holdings",
    "regulated",
    "debts",
    "goals",
    "retirement",
    "unknown",
    "definitions",
  ],
  notary: ["household", "inventory", "debts", "holders", "years", "definitions"],
  ai: [
    "household",
    "summary",
    "fixed",
    "wealth",
    "holdings",
    "regulated",
    "debts",
    "ratio",
    "goals",
    "retirement",
    "inventory",
    "holders",
    "unknown",
    "definitions",
  ],
};

export function buildDocument(d: AuditOut): AuditDoc {
  const lang: Language = d.language;
  const m = MESSAGES[lang];
  const t = m.audit.doc;
  const eur = (a: string) =>
    d.privacy.exact_amounts ? formatEurIn(a, lang) : formatEurWholeIn(a, lang);
  const pct = (p: string) => formatTenthPercentIn(p, lang);
  const month = (mo: string) => monthLabelIn(mo, lang);
  const label = (l: AuditLabelOut) => labelText(l, t);
  const holder = (l: AuditLabelOut | null | undefined) => (l ? label(l) : t.joint);
  const table = (head: string[], rows: string[][], numeric: boolean[]): Block => ({
    kind: "table",
    head,
    rows,
    numeric,
  });
  const scopeNote: Block[] =
    d.scope === "household" ? [] : [{ kind: "note", text: t.householdFlows }];

  const debtRows = (debts: AuditDebtOut[]) =>
    debts.map((x) => [
      label(x.label),
      eur(x.owed),
      x.payment ? eur(x.payment) : t.none,
      eur(x.insurance),
      formatRatePercentIn(x.rate, lang),
      x.ends ? month(x.ends) : "—",
    ]);
  const debtHead = [t.line, t.owed, t.payment, t.insurance, t.rateCol, t.ends];
  const debtNumeric = [false, true, true, true, true, false];

  const spreadRows = (): string[][] => {
    const row = (name: string, s: AuditSpreadOut) => [
      name,
      eur(s.average),
      eur(s.total),
      `${eur(s.lowest)} (${month(s.lowest_month)})`,
      `${eur(s.highest)} (${month(s.highest_month)})`,
    ];
    return [
      row(t.incomeCol, d.money.income),
      row(t.spentCol, d.money.spent),
      row(t.savedCol, d.money.saved),
      row(t.restCol, d.money.rest),
    ];
  };
  const spreadTable = table([t.measure, t.average, t.total, t.lowest, t.highest], spreadRows(), [
    false,
    true,
    true,
    true,
    true,
  ]);
  const noIncome: Block[] = d.money.no_income.length
    ? [{ kind: "note", text: t.noIncome(d.money.no_income.map(month).join(", ")) }]
    : [];
  const rate: Block[] =
    d.money.savings_rate && d.money.saved_share
      ? [{ kind: "p", text: t.savingsRate(pct(d.money.savings_rate), pct(d.money.saved_share)) }]
      : [];

  const lines = d.wealth.lines;
  const goalsTier = (tier: string) => m.goals.tiers[tier as keyof typeof m.goals.tiers];

  const sections: Record<string, Block[]> = {
    household: [
      {
        kind: "list",
        items: d.household.members.map((x) =>
          [
            label(x.label),
            x.age !== null && x.age !== undefined ? t.age(x.age) : t.ageUnknown,
          ].join(", "),
        ),
      },
      { kind: "p", text: t.householdNote(formatDateTimeIn(d.generated_at, lang)) },
      ...scopeNote,
    ],
    income: [
      table(
        [t.month, t.incomeCol, t.spentCol, t.savedCol, t.restCol],
        d.money.months.map((x) => [
          month(x.month),
          eur(x.income),
          eur(x.spent),
          eur(x.saved),
          eur(x.rest),
        ]),
        [false, true, true, true, true],
      ),
      spreadTable,
      ...noIncome,
      { kind: "note", text: t.afterWithholding },
    ],
    summary: [
      spreadTable,
      ...rate,
      ...noIncome,
      { kind: "p", text: t.incomeByCategory },
      table(
        [t.category, t.amount],
        d.money.income_by_category.map((x) => [x.name, eur(x.amount)]),
        [false, true],
      ),
      { kind: "p", text: t.spendingByCategory },
      table(
        [t.category, t.amount],
        [
          ...d.money.spending_by_category.map((x) => [x.name, eur(x.amount)]),
          ...(Number(d.money.spending_rest) !== 0 ? [[t.others, eur(d.money.spending_rest)]] : []),
        ],
        [false, true],
      ),
      { kind: "note", text: t.afterWithholding },
      ...scopeNote,
    ],
    fixed: d.money.fixed.length
      ? [
          table(
            [t.category, t.frequency, t.perMonth],
            d.money.fixed.map((x) => [x.category, t.frequencies[x.frequency], eur(x.monthly)]),
            [false, false, true],
          ),
          { kind: "p", text: t.fixedTotal(eur(d.money.fixed_monthly)) },
        ]
      : [{ kind: "p", text: t.fixedNone }],
    loans: d.ratio.debts.length
      ? [table(debtHead, debtRows(d.ratio.debts), debtNumeric)]
      : [{ kind: "p", text: t.noLoans }],
    ratio: [
      { kind: "p", text: t.ratioIncome(eur(d.ratio.income)) },
      { kind: "p", text: t.counted(d.ratio.counted.join(", ") || t.none) },
      ...(d.ratio.left_out.length
        ? [{ kind: "p" as const, text: t.leftOut(d.ratio.left_out.join(", ")) }]
        : []),
      { kind: "p", text: t.payments(eur(d.ratio.payments)) },
      {
        kind: "p",
        text: d.ratio.ratio ? t.ratio(pct(d.ratio.ratio), d.ratio.above_ceiling) : t.ratioNone,
      },
      ...(d.ratio.before_tax_ratio && d.ratio.withholding
        ? [
            {
              kind: "p" as const,
              text: t.beforeTax(
                pct(d.ratio.before_tax_ratio),
                pct(d.ratio.withholding),
                d.ratio.before_tax_above,
              ),
            },
          ]
        : []),
      { kind: "p", text: t.remaining(eur(d.ratio.remaining)) },
      ...(d.ratio.left_out_debts.length
        ? [
            {
              kind: "p" as const,
              text: t.leftOutDebts(d.ratio.left_out_debts.map(label).join(", ")),
            },
          ]
        : []),
      { kind: "note", text: t.ratioNote },
      { kind: "note", text: t.afterWithholding },
    ],
    capacity: [
      {
        kind: "p",
        text: d.money.capacity_set
          ? t.capacitySet(eur(d.money.capacity))
          : t.capacity(
              eur(d.money.capacity),
              d.money.capacity_start ? month(d.money.capacity_start) : "—",
              d.money.capacity_end ? month(d.money.capacity_end) : "—",
            ),
      },
    ],
    liquidity: [
      { kind: "p", text: t.wealthAt(month(d.wealth.month)) },
      { kind: "p", text: t.liquid(eur(d.wealth.liquid)) },
      { kind: "p", text: t.illiquid(eur(d.wealth.illiquid)) },
      {
        kind: "p",
        text: t.precaution(
          eur(d.goals.precaution),
          d.goals.precaution_months ? formatTenthIn(d.goals.precaution_months, lang) : null,
        ),
      },
    ],
    project: d.project ? projectBlocks(d, t, eur, pct, lang) : [],
    wealth: [
      { kind: "p", text: t.wealthAt(month(d.wealth.month)) },
      table(
        [t.category, t.value, t.share, t.liquidCol],
        d.wealth.categories.map((c) => [
          c.name,
          eur(c.value),
          c.share ? pct(c.share) : "—",
          c.kind === "asset" ? (c.liquid ? t.yes : t.no) : "—",
        ]),
        [false, true, true, false],
      ),
      { kind: "p", text: t.gross(eur(d.wealth.gross)) },
      { kind: "p", text: t.debtsTotal(eur(d.wealth.debts)) },
      { kind: "p", text: t.net(eur(d.wealth.net)) },
      { kind: "p", text: t.liquid(eur(d.wealth.liquid)) },
      { kind: "p", text: t.change(month(d.wealth.start_month), eur(d.wealth.change)) },
      ...(d.assumptions.length
        ? [
            { kind: "p" as const, text: m.audit.doc.sections.assumptions },
            table(
              [t.category, t.expectedReturn, t.volatility],
              d.assumptions.map((a) => [a.category, pct(a.expected_return), pct(a.volatility)]),
              [false, true, true],
            ),
            { kind: "note" as const, text: t.assumptionsNote },
          ]
        : []),
    ],
    holdings: [
      table(
        [t.line, t.category, t.holder, t.envelope, t.opened, t.value],
        lines
          .filter((x) => x.kind === "asset")
          .map((x) => [
            label(x.label),
            x.category,
            holder(x.holder),
            x.envelope
              ? t.envelopes[x.envelope]
              : x.regulated
                ? m.wealth.regulatedTypes[x.regulated]
                : "—",
            x.opening_year && x.age !== null && x.age !== undefined
              ? t.openedValue(
                  x.opening_year,
                  x.age,
                  x.milestone && x.envelope ? milestoneText(x.milestone, x.envelope, t) : null,
                )
              : "—",
            `${eur(x.value)}${x.carried ? "*" : ""}`,
          ]),
        [false, false, false, false, false, true],
      ),
      ...(d.wealth.carried ? [{ kind: "note" as const, text: t.carried }] : []),
    ],
    regulated: lines.some((x) => x.regulated)
      ? [
          table(
            [t.line, t.envelope, t.value, t.ceiling],
            lines
              .filter((x) => x.regulated)
              .map((x) => [
                label(x.label),
                x.regulated ? m.wealth.regulatedTypes[x.regulated] : "",
                eur(x.value),
                x.ceiling ? eur(x.ceiling) : "—",
              ]),
            [false, false, true, true],
          ),
        ]
      : [{ kind: "p", text: t.noRegulated }],
    debts: d.wealth.debt_lines.length
      ? [table(debtHead, debtRows(d.wealth.debt_lines), debtNumeric)]
      : [{ kind: "p", text: t.noDebts }],
    goals: d.goals.goals.length
      ? [
          table(
            [t.line, t.goalTier, t.target, t.deadline, t.reached, t.status],
            d.goals.goals.map((g) => [
              g.pro_type
                ? `${label(g.label)} (${t.professional(
                    m.goals.proTypes[g.pro_type],
                    g.cost ? eur(g.cost) : "—",
                    g.aids
                      .map(
                        (a) =>
                          `${m.goals.aidSources[a.source]} ${eur(a.amount)}${a.source === "honour_loan" ? `, ${t.honourLoan}` : ""}`,
                      )
                      .join("; "),
                  )})`
                : label(g.label),
              goalsTier(g.tier),
              eur(g.target),
              g.deadline ? month(g.deadline) : "—",
              eur(g.value),
              m.goals.status[g.status],
            ]),
            [false, false, true, false, true, false],
          ),
          {
            kind: "p",
            text: t.precautionLine(
              eur(d.goals.precaution),
              d.goals.precaution_months ? formatTenthIn(d.goals.precaution_months, lang) : null,
            ),
          },
        ]
      : [{ kind: "p", text: t.noGoals }],
    retirement: d.retirement.length
      ? [
          table(
            [t.retirementMember, t.retires, t.pensionFrom, t.pension],
            d.retirement.map((x) => [
              label(x.member),
              month(x.retirement),
              month(x.pension_month),
              eur(x.pension),
            ]),
            [false, false, false, true],
          ),
        ]
      : [{ kind: "p", text: t.noRetirement }],
    unknown: [
      { kind: "list", items: t.unknown },
      { kind: "p", text: t.unknownEnd },
    ],
    inventory: [
      { kind: "p", text: t.wealthAt(month(d.wealth.month)) },
      table(
        [t.line, t.category, t.holder, t.value],
        lines.map((x) => [
          label(x.label),
          x.category,
          holder(x.holder),
          `${x.kind === "debt" ? "−" : ""}${eur(x.value)}${x.carried ? "*" : ""}`,
        ]),
        [false, false, false, true],
      ),
      { kind: "p", text: t.net(eur(d.wealth.net)) },
      ...(d.wealth.carried ? [{ kind: "note" as const, text: t.carried }] : []),
      { kind: "note", text: t.inventoryNote },
    ],
    holders: [
      table(
        [t.holder, t.value],
        d.wealth.holders.map((h) => [holder(h.holder), eur(h.net)]),
        [false, true],
      ),
      { kind: "p", text: t.net(eur(d.wealth.net)) },
    ],
    years: [
      table(
        [t.year, t.months, t.incomeCol, t.spentCol, t.savedCol, t.restCol],
        d.money.years.map((y) => [
          String(y.year),
          y.partial ? t.partial(y.months) : String(y.months),
          eur(y.income),
          eur(y.spent),
          eur(y.saved),
          eur(y.rest),
        ]),
        [false, false, true, true, true, true],
      ),
      { kind: "note", text: t.notTaxable },
    ],
    definitions: [{ kind: "list", items: t.definitions }],
  };

  const titles = t.sections as Record<string, string>;
  const meta: [string, string][] = [
    [t.period, t.periodText(month(d.period.start), month(d.period.end), d.period.months)],
    [t.generated, formatDateTimeIn(d.generated_at, lang)],
    [t.scope, t.scopes[d.scope]],
    [
      t.privacy,
      t.privacyText(d.privacy.named_members, d.privacy.named_lines, d.privacy.exact_amounts),
    ],
  ];
  return {
    title: t.titles[d.audience],
    household: d.household.name ?? t.theHousehold,
    meta: d.period.shortened ? [...meta, ["", t.shortened]] : meta,
    prompt: d.audience === "ai" ? t.prompt : null,
    sections: ORDER[d.audience]
      .map((id) => ({ id, title: titles[id] ?? id, blocks: sections[id] ?? [] }))
      .filter((s) => s.blocks.length > 0),
    closing: t.closing,
  };
}

/** A name, or its pseudonym in the document's language (F-AUD-4). */
export function labelText(l: AuditLabelOut, t: D): string {
  if (l.name !== null && l.name !== undefined) return l.name;
  const n = l.number ?? 1;
  switch (l.group) {
    case "member":
      return t.member(l.key ?? "?");
    case "envelope":
      return `${t.envelopes[l.key as keyof D["envelopes"]] ?? l.key} ${n}`;
    case "tier":
      return t.goalOf(t.tiers[l.key as keyof D["tiers"]] ?? l.key ?? "", n);
    default:
      return `${l.key ?? ""} ${n}`;
  }
}

const MILESTONE_YEARS: Record<string, number> = {
  life_insurance: 8,
  capitalisation: 8,
  pea: 5,
  pea_pme: 5,
};

function milestoneText(milestone: string, envelope: string, t: D): string | null {
  const years = MILESTONE_YEARS[envelope];
  if (years === undefined) return null;
  return t.milestones[milestone as keyof D["milestones"]](years);
}

function projectBlocks(
  d: AuditOut,
  t: D,
  eur: (a: string) => string,
  pct: (p: string) => string,
  lang: Language,
): Block[] {
  const p = d.project;
  if (!p) return [];
  const pt = t.project;
  const rows: string[][] = [
    [pt.price, eur(p.price)],
    [
      pt.notary,
      p.notary_estimated ? `${eur(p.notary_fees)} (${pt.notaryEstimated})` : eur(p.notary_fees),
    ],
    [pt.agency, eur(p.agency_fees)],
    [pt.guarantee, eur(p.guarantee_fees)],
    [pt.cost, eur(p.cost)],
    [pt.down, eur(p.down_payment)],
    [pt.downShare, pct(p.down_share)],
    [pt.loan, eur(p.loan)],
    [pt.duration, pt.durationValue(p.years, t.durations[p.duration])],
    [pt.rate, formatRatePercentIn(p.rate, lang)],
    [pt.payment, eur(p.payment)],
    [pt.insurance, eur(p.insurance)],
    [pt.ratioAfter, p.ratio_after ? pt.ratioAfterValue(pct(p.ratio_after), p.above_ceiling) : "—"],
    ...(p.before_tax_ratio_after
      ? [[pt.beforeTax, pt.ratioAfterValue(pct(p.before_tax_ratio_after), p.before_tax_above)]]
      : []),
    [pt.remaining, eur(p.remaining_after_housing)],
    [pt.rent, `${eur(p.rent)}, ${pt.rentStops(p.rent_stops)}`],
    [pt.change, eur(p.housing_change)],
    [pt.saved, eur(p.average_saved)],
    [pt.capacity, eur(p.capacity)],
    [pt.liquidLeft, eur(p.liquid_left)],
    [pt.precaution, eur(p.precaution)],
  ];
  return [
    { kind: "table", head: ["", ""], rows, numeric: [false, true] },
    { kind: "note", text: pt.note },
  ];
}

/** The document as structured Markdown for an AI chat: headings, tables, one figure a cell. */
export function toMarkdown(doc: AuditDoc, promptTitle: string, contents: string): string {
  const out: string[] = [];
  if (doc.prompt) {
    out.push(`# ${promptTitle}`, "", ...doc.prompt.map((line) => `- ${line}`), "", "---", "");
  }
  out.push(`# ${doc.title}`, "", `**${doc.household}**`, "");
  for (const [k, v] of doc.meta) out.push(k ? `- ${k}: ${v}` : `- ${v}`);
  out.push("", `## ${contents}`, "");
  doc.sections.forEach((s, i) => {
    out.push(`${i + 1}. ${s.title}`);
  });
  for (const s of doc.sections) {
    out.push("", `## ${s.title}`, "");
    for (const b of s.blocks) {
      if (b.kind === "p") out.push(b.text, "");
      else if (b.kind === "note") out.push(`> ${b.text}`, "");
      else if (b.kind === "list") out.push(...b.items.map((item) => `- ${item}`), "");
      else {
        const cell = (c: string) => c.replace(/\|/g, "\\|");
        out.push(`| ${b.head.map(cell).join(" | ")} |`);
        out.push(`| ${b.numeric.map((n) => (n ? "---:" : "---")).join(" | ")} |`);
        for (const row of b.rows) out.push(`| ${row.map(cell).join(" | ")} |`);
        out.push("");
      }
    }
  }
  out.push("---", "", `_${doc.closing}_`, "");
  return out.join("\n");
}
