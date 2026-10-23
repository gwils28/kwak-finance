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
