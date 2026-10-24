import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import type { GoalAnalysisOut, PointOut } from "../api/generated";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 9, 20));
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const plain = (text: string | null | undefined) => text?.replace(/[  ]/g, " ");

const point = (fields: Partial<PointOut>): PointOut => ({
  rule: "unfunded",
  severity: "warning",
  goal_id: null,
  goal_name: null,
  line_id: null,
  line_name: null,
  lines: [],
  amount: null,
  deadline: null,
  figures: {},
  postponements: [],
  subject_id: null,
  subject_name: null,
  hideable: true,
  ...fields,
});

const months = Array.from({ length: 24 }, (_, k) => {
  const index = 2026 * 12 + 9 + k;
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`;
});

const analysis: GoalAnalysisOut = {
  month: "2026-10",
  sankey: {
    month: "2026-09",
    all_assets: false,
    categories: [],
    lines: [],
    flows: [],
    elsewhere: [],
  },
  reference: "2026-09",
  capacity: "250.00",
  capacity_set: false,
  capacity_months: 6,
  inflation: "0.0200",
  risk: [],
  forward: {
    reference: "2026-09",
    months,
    bands: [
      {
        goal_id: "g-summer",
        name: "Été",
        tier: "short",
        deadline: "2027-09",
        amount: "100.00",
        months: 12,
      },
      {
        goal_id: "g-car",
        name: "Voiture",
        tier: "medium",
        deadline: "2029-03",
        amount: "200.00",
        months: 30,
      },
    ],
    totals: months.map((_, k) => (k < 12 ? "300.00" : "200.00")),
    over: 12,
    peak: "50.00",
  },
  timeline: [
    {
      goal_id: "g-summer",
      name: "Été",
      tier: "short",
      start: "2026-07",
      deadline: "2027-09",
      estimated: "2027-12",
      never: false,
      enough_history: true,
      at_plan: "2027-09",
    },
    {
      goal_id: "g-car",
      name: "Voiture",
      tier: "medium",
      start: "2026-09",
      deadline: "2029-03",
      estimated: null,
      never: false,
      enough_history: false,
      at_plan: null,
    },
  ],
  statuses: [
    {
      goal_id: "g-summer",
      name: "Été",
      tier: "short",
      months: [
        { month: "2026-07", status: "on" },
        { month: "2026-08", status: "behind" },
        { month: "2026-09", status: "behind" },
      ],
    },
  ],
  points: {
    shown: [
      point({ rule: "precaution_none", hideable: false }),
      point({
        rule: "overcommitted",
        amount: "50.00",
        postponements: [
          {
            goal_id: "g-car",
            name: "Voiture",
            months: 10,
            deadline: "2030-01",
            tier: "long",
            lower_by: "1500.00",
          },
          {
            goal_id: "g-summer",
            name: "Été",
            months: 12,
            deadline: "2028-09",
            tier: "medium",
            lower_by: "600.00",
          },
        ],
      }),
      point({
        rule: "behind",
        goal_id: "g-summer",
        goal_name: "Été",
        amount: "300.00",
        figures: {
          extra: "40.00",
          estimated: "2027-12",
          never: false,
          reachable: "1000.00",
          market: false,
        },
      }),
    ],
    more: [
      point({
        rule: "data",
        severity: "warning",
        lines: [{ line_id: "l-ldds", name: "LDDS" }],
        hideable: false,
      }),
    ],
  },
};

function api(me: object = owner, data: GoalAnalysisOut = analysis) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(me),
    "GET /api/goals/analysis": () => Response.json(data),
    "POST /api/goals/analysis/hidden": () => new Response(null, { status: 204 }),
    "DELETE /api/goals/analysis/hidden": () => new Response(null, { status: 204 }),
  });
}

test("the analysis tab shows the points, the effort against capacity, the timeline and the statuses", async () => {
  api();
  render(<TestApp path="/goals/analysis" />);

  expect(
    await screen.findByRole("heading", { level: 1, name: "Goals analysis" }),
  ).toBeInTheDocument();
  const tabs = screen.getByRole("navigation", { name: "Main" });
  expect(within(tabs).getByRole("link", { name: "Analysis" })).toHaveClass("border-accent");
  expect(within(tabs).getByRole("link", { name: "Pyramid" })).not.toHaveClass("border-accent");
  expect(within(tabs).getByRole("link", { name: "Pyramid" })).not.toHaveAttribute("aria-current");
  expect(within(tabs).getByRole("link", { name: "Analysis" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(await screen.findByText(/Judged at Sept 2026/)).toBeInTheDocument();

  const points = await screen.findByRole("region", { name: "Points to look at" });
  const cards = within(points)
    .getAllByRole("listitem")
    .filter((li) => li.parentElement?.parentElement === points);
  expect(cards).toHaveLength(3);
  expect(plain(points.textContent)).toContain("You have no emergency fund yet.");
  expect(plain(points.textContent)).toContain(
    "Your goals need €50 a month more than your capacity (€250 a month).",
  );
  expect(plain(points.textContent)).toContain(
    "Consider postponing Voiture by 10 months, to Jan 2030 (it would move to the long term), or lowering its target by €1,500.",
  );
  expect(plain(points.textContent)).toContain("Other options: Été: 12 months later");
  expect(plain(points.textContent)).toContain("+€40 a month keeps the date");
  expect(points).toHaveTextContent("Not personalised investment advice");
  // the emergency fund's point cannot be hidden
  expect(within(cards[0] as HTMLElement).queryByRole("button", { name: /Hide/ })).toBeNull();

  await userEvent.setup().click(screen.getByRole("button", { name: "1 more point" }));
  expect(plain(points.textContent)).toContain("No value entered for Sept 2026 on: LDDS.");

  const forward = screen.getByRole("region", { name: "Required effort against capacity" });
  expect(plain(forward.textContent)).toContain(
    "Over-committed for 12 months, by up to €50 a month.",
  );
  expect(plain(forward.textContent)).toContain("Capacity: €250 a month (measured over 6 months).");
  const table = within(forward).getByRole("table", { name: "Required effort by month" });
  expect(plain(within(table).getAllByRole("row")[1]?.textContent)).toBe("Oct 2026€100€200€300€250");

  const timeline = screen.getByRole("table", { name: "Goals' dates" });
  expect(plain(within(timeline).getAllByRole("row")[2]?.textContent)).toBe(
    "VoitureSept 2026Mar 2029— (not enough history)—",
  );
  const statuses = screen.getByRole("table", { name: "Goals' status by month" });
  expect(within(statuses).getAllByText("Behind")).toHaveLength(2);
});

test("a point is snoozed, and hidden points shown again", async () => {
  const calls = api();
  render(<TestApp path="/goals/analysis" />);
  const user = userEvent.setup();
  const points = await screen.findByRole("region", { name: "Points to look at" });
  const [snooze] = within(points).getAllByRole("button", { name: "Remind me next month" });
  await user.click(snooze as HTMLElement);
  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "POST /api/goals/analysis/hidden")?.body).toEqual({
      rule: "overcommitted",
      goal_id: null,
      line_id: null,
      action: "snooze",
    }),
  );
  await user.click(screen.getByRole("button", { name: "Show hidden points again" }));
  await vi.waitFor(() =>
    expect(calls.some((c) => c.route === "DELETE /api/goals/analysis/hidden")).toBe(true),
  );
});

test("the analysis reads in French", async () => {
  api({ ...owner, language: "fr" });
  render(<TestApp path="/goals/analysis" language="fr" />);
  expect(
    await screen.findByRole("heading", { level: 1, name: "Analyse des objectifs" }),
  ).toBeInTheDocument();
  const points = await screen.findByRole("region", { name: "Points d'attention" });
  expect(plain(points.textContent)).toContain(
    "Vos objectifs demandent 50 € par mois de plus que votre capacité (250 € par mois).",
  );
  expect(plain(points.textContent)).toContain(
    "Envisager de repousser Voiture de 10 mois, à janv. 2030 (il passerait au long terme), ou de baisser sa cible de 1 500 €.",
  );
  expect(points).toHaveTextContent("Ni un conseil en investissement personnalisé");
  const forward = screen.getByRole("region", { name: "Effort requis face à la capacité" });
  expect(plain(forward.textContent)).toContain("Surengagé pendant 12 mois, jusqu'à 50 € par mois.");
});

test("the pyramid's tab stays marked on a goal's page", async () => {
  fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
  });
  render(<TestApp path="/goals/g-summer" />);
  const tabs = await screen.findByRole("navigation", { name: "Main" });
  expect(within(tabs).getByRole("link", { name: "Pyramid" })).toHaveClass("border-accent");
});

test("a goal due in the reference month takes that month, as the total counts it", async () => {
  const due = {
    ...analysis,
    forward: {
      ...analysis.forward,
      bands: [
        { ...analysis.forward.bands[0], months: 0 } as GoalAnalysisOut["forward"]["bands"][0],
      ],
      totals: months.map((_, k) => (k === 0 ? "100.00" : "0.00")),
    },
  };
  api(owner, due);
  render(<TestApp path="/goals/analysis" />);
  const forward = await screen.findByRole("region", { name: "Required effort against capacity" });
  const table = within(forward).getByRole("table", { name: "Required effort by month" });
  const rows = within(table).getAllByRole("row");
  expect(plain(rows[1]?.textContent)).toBe("Oct 2026€100€100€250");
  expect(plain(rows[2]?.textContent)).toBe("Nov 2026€0€0€250");
});

test("a capacity measured over too few months is not judged", async () => {
  api(owner, { ...analysis, capacity_months: 2 });
  render(<TestApp path="/goals/analysis" />);
  const forward = await screen.findByRole("region", { name: "Required effort against capacity" });
  expect(plain(forward.textContent)).toContain(
    "Capacity measured over 2 months: too short to judge.",
  );
  expect(forward).not.toHaveTextContent("Over-committed");
});

test("the timeline marks each goal's dates, and an arrow for those beyond it", async () => {
  const far = {
    ...analysis,
    timeline: [
      { ...analysis.timeline[0], estimated: "2045-01" } as GoalAnalysisOut["timeline"][0],
      analysis.timeline[1] as GoalAnalysisOut["timeline"][0],
    ],
  };
  api(owner, far);
  render(<TestApp path="/goals/analysis" />);
  const svg = await screen.findByRole("img", { name: "Timeline of the goals" });
  expect(svg.querySelectorAll("circle")).toHaveLength(0); // one beyond, one with no estimate
  expect(svg.querySelectorAll("path")).toHaveLength(1); // Été's date at the plan
  expect(within(svg).getByText("Beyond the chart: see the table")).toBeInTheDocument();
});

const second: GoalAnalysisOut = {
  ...analysis,
  risk: [
    {
      goal_id: "g-summer",
      name: "Été",
      tier: "short",
      months_left: 12,
      volatility: "0.1600",
      real_return: "0.0500",
      risky_share: "1.0000",
      allowed_share: null,
      zone: "red_short",
      loss: "-0.1253",
      losing: false,
    },
    {
      goal_id: "g-car",
      name: "Voiture",
      tier: "long",
      months_left: 120,
      volatility: "0.0000",
      real_return: "-0.0030",
      risky_share: "0.0000",
      allowed_share: null,
      zone: "red_eroding",
      loss: "0.1830",
      losing: false,
    },
    {
      goal_id: "g-home",
      name: "Apport",
      tier: "medium",
      months_left: 40,
      volatility: "0.0800",
      real_return: "0.0300",
      risky_share: "0.5000",
      allowed_share: "0.4444",
      zone: "amber_glide",
      loss: "-0.0900",
      losing: false,
    },
    {
      goal_id: "g-rum",
      name: "Rhum",
      tier: "pleasure",
      months_left: null,
      volatility: "0.0000",
      real_return: "-0.0030",
      risky_share: "0.0000",
      allowed_share: null,
      zone: null,
      loss: null,
      losing: false,
    },
  ],
  points: {
    shown: [
      point({
        rule: "short_risk",
        goal_id: "g-summer",
        goal_name: "Été",
        amount: "3000.00",
        figures: { loss: "376.00", months: 12 },
      }),
      point({
        rule: "idle",
        severity: "warning",
        amount: "2000.00",
        subject_id: "g-summer",
        subject_name: "Été",
        figures: { set_aside: "400.00" },
      }),
      point({
        rule: "capstone",
        severity: "good",
        amount: "11.00",
        subject_id: "g-car",
        subject_name: "Voiture",
        figures: { monthly: "109.00", months: 3 },
      }),
    ],
    more: [
      point({
        rule: "not_indexed",
        severity: "info",
        goal_id: "g-car",
        goal_name: "Voiture",
        amount: "30000.00",
        figures: { indexed: "36569.83", months: 120 },
      }),
      point({
        rule: "eroding",
        severity: "info",
        goal_id: "g-car",
        goal_name: "Voiture",
        amount: "290.26",
        figures: { months: 120 },
      }),
      point({ rule: "left_over", severity: "good", amount: "80.00" }),
    ],
  },
};

test("the second batch of points reads its figures, and the risk chart its zones", async () => {
  api(owner, second);
  render(<TestApp path="/goals/analysis" />);
  const points = await screen.findByRole("region", { name: "Points to look at" });
  const text = () => plain(points.textContent);
  expect(text()).toContain(
    "€3,000 of Été sits on volatile or illiquid lines, 12 months from its deadline. One time in ten, about €376 less at the deadline.",
  );
  expect(text()).toContain(
    "Consider setting €400 aside for Été (an adjustment of its envelope, which moves no money)",
  );
  expect(text()).toContain(
    "€11 more on Voiture would make it ahead and unlock your pleasure goals.",
  );
  expect(text()).toContain("Or €109 a month for 3 months.");
  await userEvent.setup().click(screen.getByRole("button", { name: "3 more points" }));
  expect(text()).toContain(
    "Voiture's target, €30,000, is in today's euros: in 10 years, at 2% inflation a year, it is about €36,570.",
  );
  expect(text()).toContain("Over 10 years, inflation would take about €290 from Voiture");
  expect(text()).toContain("Your plan leaves €80 a month unallocated, and no goal is behind.");

  const risk = screen.getByRole("region", { name: "Horizon and risk" });
  expect(within(risk).getByRole("img", { name: "Goals by horizon and risk" })).toBeInTheDocument();
  expect(plain(risk.textContent)).toContain("Without a deadline: Rhum");
  const rows = within(within(risk).getByRole("table", { name: "Goals' horizon and risk" }))
    .getAllByRole("row")
    .map((r) => plain(r.textContent));
  expect(rows[0]).toContain("Allowed on volatile lines");
  expect(rows[1]).toBe("Été1216%+5.0%100%—-12.5%Near and volatile");
  expect(rows[2]).toBe("Voiture1200%-0.3%0%—+18.3%Eroding");
  expect(rows[3]).toBe("Apport408%+3.0%50%44%-9.0%Above the glide path");

  // The legend says what each area and each ring means.
  expect(within(risk).getByText("How to read the chart")).toBeVisible();
  // Each zone says what it is, on the chart itself.
  const chart = within(risk).getByRole("img", { name: "Goals by horizon and risk" });
  for (const name of ["Near and volatile", "Glide path", "Far and eroding"]) {
    expect(within(chart).getByText(name)).toBeInTheDocument();
  }
  const legend = within(risk).getByRole("list", { name: "How to read the chart" });
  const items = within(legend)
    .getAllByRole("listitem")
    .map((li) => plain(li.textContent));
  expect(items).toEqual([
    "Up to 2 years, volatility above 5%: near and volatile, a fall would have no time to recover.",
    "2 to 5 years: the share on volatile or illiquid lines should shrink step by step, from all of it 5 years out to none 2 years out (the table gives each goal's share allowed).",
    "Beyond 8 years: the lines should earn more than inflation (2% a year).",
    "Solid ring: near and volatile, or eroding. Dashed ring: above the glide path. Dotted ring: partly in a category that loses value.",
    "The areas are guides by horizon: only a ring says a goal needs a look.",
  ]);
});

test("the second batch reads in French", async () => {
  api({ ...owner, language: "fr" }, second);
  render(<TestApp path="/goals/analysis" language="fr" />);
  const points = await screen.findByRole("region", { name: "Points d'attention" });
  expect(plain(points.textContent)).toContain(
    "3 000 € d'Été sont sur des lignes volatiles ou peu liquides, à 12 mois de son échéance. Une fois sur dix, environ 376 € de moins à l'échéance.",
  );
  expect(plain(points.textContent)).toContain(
    "11 € de plus sur Voiture le mettraient en avance et débloqueraient vos objectifs plaisir.",
  );
  const risk = screen.getByRole("region", { name: "Horizon et risque" });
  expect(risk).toHaveTextContent("Proche et volatil");
  const chartFr = within(risk).getByRole("img", { name: "Objectifs par horizon et risque" });
  for (const name of ["Proche et volatil", "Trajectoire de sortie", "Lointain et grignoté"]) {
    expect(within(chartFr).getByText(name)).toBeInTheDocument();
  }
  const legend = within(risk).getByRole("list", { name: "Comment lire le graphique" });
  expect(plain(legend.textContent)).toContain(
    "Les aires sont des repères d'horizon : seul un anneau signale un objectif à regarder.",
  );
  expect(plain(within(risk).getAllByRole("row")[3]?.textContent ?? "")).toBe(
    "Apport408 %+3,0 %50 %44 %-9,0 %Au-dessus de la trajectoire",
  );
});

const third: GoalAnalysisOut = {
  ...analysis,
  points: {
    shown: [
      point({
        rule: "ceiling",
        severity: "info",
        line_id: "l-livret",
        line_name: "Mon livret",
        amount: "22600.00",
        figures: { ceiling: "22950.00", room: "350.00", regulated: "livret_a" },
        subject_id: "g-summer",
        subject_name: "Été",
      }),
    ],
    more: [],
  },
  sankey: {
    month: "2026-09",
    all_assets: false,
    categories: [
      {
        category_id: "c-savings",
        name: "Savings accounts",
        colour: "savings",
        amount: "5000.00",
      },
      { category_id: "c-stocks", name: "Stocks", colour: "stocks", amount: "3000.00" },
    ],
    lines: [
      {
        line_id: "l-livret",
        name: "Mon livret",
        category_id: "c-savings",
        amount: "5000.00",
        free: "3000.00",
      },
      {
        line_id: "l-pea",
        name: "PEA",
        category_id: "c-stocks",
        amount: "3000.00",
        free: "2000.00",
      },
    ],
    flows: [
      { goal_id: "g-summer", name: "Été", tier: "short", line_id: "l-livret", amount: "2000.00" },
      { goal_id: "g-car", name: "Voiture", tier: "medium", line_id: "l-pea", amount: "1000.00" },
    ],
    elsewhere: [{ goal_id: "g-car", name: "Voiture", tier: "medium", amount: "4000.00" }],
  },
};

test("a regulated line near its ceiling, and where the goals' money sits", async () => {
  const asked: URL[] = [];
  fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/goals/analysis": (_, url) => {
      asked.push(url);
      return Response.json(third);
    },
  });
  render(<TestApp path="/goals/analysis" />);
  const points = await screen.findByRole("region", { name: "Points to look at" });
  expect(plain(points.textContent)).toContain(
    "Mon livret (Livret A) is €350 below its €22,950 ceiling. Été still counts on its rises.",
  );
  expect(plain(points.textContent)).toContain(
    "Deposits above the ceiling are refused; interest can still take it over.",
  );

  const sankey = screen.getByRole("region", { name: "Where the goals' money sits" });
  expect(within(sankey).getByRole("img", { name: /Categories, lines/ })).toBeInTheDocument();
  expect(plain(sankey.textContent)).toContain("On lines not shown: Voiture €4,000.");
  const rows = within(
    within(sankey).getByRole("table", { name: "The goals' envelopes, line by line" }),
  )
    .getAllByRole("row")
    .map((r) => plain(r.textContent));
  expect(rows.slice(1)).toEqual([
    "Savings accountsMon livretÉté€2,000",
    "Savings accountsMon livretFree€3,000",
    "StocksPEAVoiture€1,000",
    "StocksPEAFree€2,000",
  ]);
  expect(asked.at(-1)?.searchParams.get("all_assets")).toBe("false");
  const box = within(sankey).getByRole("checkbox", { name: "Show real estate and equipment" });
  await userEvent.setup().click(box);
  // Ticked at once, before the answer comes back.
  expect(box).toBeChecked();
  await vi.waitFor(() => expect(asked.at(-1)?.searchParams.get("all_assets")).toBe("true"));
});

test("a full regulated line, and a Sankey with nothing to show", async () => {
  const [ceiling] = third.points.shown;
  api(owner, {
    ...third,
    points: {
      shown: [
        {
          ...(ceiling as PointOut),
          figures: { ceiling: "1600.00", room: "0.00", regulated: "livret_jeune" },
          line_name: "Livret jeune",
        },
      ],
      more: [],
    },
    sankey: { ...third.sankey, categories: [], lines: [], flows: [], elsewhere: [] },
  });
  render(<TestApp path="/goals/analysis" />);
  const points = await screen.findByRole("region", { name: "Points to look at" });
  expect(plain(points.textContent)).toContain("Livret jeune has reached its €1,600 ceiling.");
  const sankey = screen.getByRole("region", { name: "Where the goals' money sits" });
  expect(sankey).toHaveTextContent("No wealth line has a value at this month.");
  expect(within(sankey).queryByRole("img")).not.toBeInTheDocument();
});

test("the ceiling and the Sankey read in French", async () => {
  api({ ...owner, language: "fr" }, third);
  render(<TestApp path="/goals/analysis" language="fr" />);
  const points = await screen.findByRole("region", { name: "Points d'attention" });
  expect(plain(points.textContent)).toContain(
    "Mon livret (Livret A) est à 350 € de son plafond de 22 950 €. Été compte encore sur ses hausses.",
  );
  const sankey = screen.getByRole("region", { name: "Où est l'argent des objectifs" });
  expect(plain(sankey.textContent)).toContain("Les lignes de chaque catégorie en sept. 2026");
  expect(plain(sankey.textContent)).toContain("Sur des lignes non montrées : Voiture 4 000 €.");
  expect(plain(sankey.textContent)).toContain(
    "« Libre » peut contenir des enveloppes d'objectifs que vous ne voyez pas.",
  );
});
