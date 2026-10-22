import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import type { GoalDetailOut, GoalOut, GoalsOut } from "../api/generated";
import { translateApiMessage } from "../auth/errors";
import { setCurrentLanguage } from "../lib/locale";
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

const plain = (text: string | null | undefined) => text?.replace(/[\u00a0\u202f]/g, " ");

const goal = (fields: Partial<GoalOut>): GoalOut => ({
  id: "g-japan",
  name: "Voyage au Japon",
  tier: "medium",
  target: "6000.00",
  start: "2026-03",
  deadline: "2027-08",
  owner_id: owner.id,
  owner_name: "Wilson",
  visibility: "shared",
  closed_from: null,
  closed_as: null,
  fundings: [
    {
      line_id: "l-ldds",
      line_name: "LDDS",
      share: 75,
      opening: "0.00",
      held: "3100.00",
      adjustments: [],
    },
  ],
  value: "3100.00",
  progress: "0.5167",
  remaining: "2900.00",
  expected: "2941.18",
  months_left: 10,
  required: "290.00",
  actual: "333.33",
  estimated: "2027-07",
  never: false,
  months_early: 1,
  extra: null,
  status: "ahead",
  effort: "290.00",
  precaution: false,
  permanent: false,
  pleasure: false,
  ...fields,
});

const precaution = goal({
  id: "g-prec",
  name: "Épargne de précaution",
  tier: "precaution",
  precaution: true,
  permanent: true,
  target: "14700.00",
  start: "2026-01",
  deadline: null,
  fundings: [
    {
      line_id: "l-livret",
      line_name: "Livret A",
      share: 100,
      opening: "9800.00",
      held: "12400.00",
      adjustments: [],
    },
  ],
  value: "12400.00",
  progress: "0.8435",
  remaining: "2300.00",
  expected: null,
  months_left: null,
  required: null,
  actual: "200.00",
  estimated: "2027-10",
  months_early: null,
  status: "fill_first",
  effort: "945.00",
});

const summer = goal({
  id: "g-summer",
  name: "Vacances été 2027",
  target: "2500.00",
  start: "2026-05",
  deadline: "2027-06",
  value: "900.00",
  progress: "0.36",
  remaining: "1600.00",
  expected: "1146.15",
  months_left: 8,
  required: "200.00",
  actual: "120.00",
  estimated: "2027-12",
  months_early: -6,
  extra: "80.00",
  status: "behind",
  effort: "115.00",
  fundings: [
    {
      line_id: "l-ldds",
      line_name: "LDDS",
      share: 25,
      opening: "300.00",
      held: "900.00",
      adjustments: [{ month: "2026-09", amount: "800.00" }],
    },
  ],
});

const goals: GoalsOut = {
  month: "2026-10",
  pyramid: [
    { tier: "precaution", value: "12400.00", target: "14700.00", progress: "0.8435" },
    { tier: "short", value: "0.00", target: "0.00", progress: null },
    { tier: "medium", value: "4000.00", target: "8500.00", progress: "0.4706" },
    { tier: "long", value: "0.00", target: "0.00", progress: null },
    { tier: "pleasure", value: "0.00", target: "0.00", progress: null },
  ],
  capstone: {
    month: "2026-09",
    precaution: "0.8435",
    ahead: 1,
    counted: 1,
    needed: 1,
    unlocked: false,
  },
  plan: {
    capacity: "1350.00",
    capacity_set: false,
    precaution_share: "0.70",
    unallocated: "0.00",
    months_to_fill: 3,
    shortfall: "85.00",
  },
  goals: [precaution, goal({}), summer],
  closed: [
    goal({
      id: "g-car",
      name: "Voiture",
      closed_from: "2026-09",
      closed_as: "archived",
      value: "8000.00",
      effort: null,
    }),
  ],
};

const detail: GoalDetailOut = {
  goal: summer,
  months: [
    { month: "2026-05", value: "300.00", gained: null, expected: "300.00", gap: "0.00" },
    { month: "2026-09", value: "800.00", gained: "110.00", expected: "976.92", gap: "-176.92" },
    { month: "2026-10", value: "900.00", gained: "100.00", expected: "1146.15", gap: "-246.15" },
  ],
};

function api(me: object = owner) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(me),
    "GET /api/goals": () => Response.json(goals),
    "GET /api/goals/g-summer": () => Response.json(detail),
    "GET /api/goals/lines": () =>
      Response.json([
        {
          line_id: "l-livret",
          line_name: "Livret A",
          worth: "5000.00",
          set_aside: "0.00",
          free: "5000.00",
        },
      ]),
    "DELETE /api/goals/g-summer": () => new Response(null, { status: 204 }),
    "PUT /api/goals/g-summer/envelopes/l-ldds/2026-10": () => Response.json(detail),
    "DELETE /api/goals/g-summer/envelopes/l-ldds/2026-09": () =>
      new Response(null, { status: 204 }),
    "PATCH /api/goals/g-japan": () => Response.json(goal({})),
    "POST /api/goals": () => Response.json(goal({ id: "g-new" }), { status: 201 }),
    "GET /api/goals/precaution-proposal": (_, url) =>
      Response.json({
        months: Number(url.searchParams.get("months")),
        monthly_fixed: "950.00",
        amount: String(950 * Number(url.searchParams.get("months"))),
        items: [
          { label: "Assurance", frequency: "yearly", amount: "600.00", monthly: "50.00" },
          { label: "Loyer", frequency: "monthly", amount: "900.00", monthly: "900.00" },
        ],
      }),
    "GET /api/wealth/lines": () =>
      Response.json(
        [
          { id: "l-livret", category_id: "c-sav", name: "Livret A", owner_id: owner.id },
          { id: "l-loan", category_id: "c-debt", name: "Prêt", owner_id: owner.id },
        ].map((l) => ({ owner_name: "Wilson", visibility: "shared", closed_from: null, ...l })),
      ),
    "GET /api/wealth/categories": () =>
      Response.json([
        { id: "c-sav", name: "Savings", kind: "asset", colour: "savings", position: 0 },
        { id: "c-debt", name: "Debts", kind: "debt", colour: "debts", position: 1 },
      ]),
    "GET /api/household/settings": () =>
      Response.json({
        warn_at: "0.80",
        analysis_start: null,
        wealth_start: null,
        precaution_share: "0.70",
        goal_capacity: null,
      }),
    "PATCH /api/household/settings": (body) => Response.json(body),
  });
}

test("the goals page shows the pyramid, the month's effort and each goal by tier", async () => {
  api();
  render(<TestApp path="/goals" />);

  expect(await screen.findByRole("heading", { level: 1, name: "Goals" })).toBeInTheDocument();
  expect(plain((await screen.findByRole("status")).textContent)).toContain(
    "Your emergency fund is short of €2,300.",
  );
  expect(
    screen.getByRole("img", {
      name: "Emergency fund: 84%, Short term: No goal, Medium term: 47%, Long term: No goal",
    }),
  ).toBeInTheDocument();
  // the long term is the pyramid's base and the short term its top, as the legend reads
  const pyramid = screen.getByRole("region", { name: "The pyramid" });
  expect(
    within(pyramid)
      .getAllByRole("listitem")
      .map((li) => plain(li.textContent)?.split(" · ")[0]),
  ).toEqual(["Short term", "Medium term", "Long term", "Emergency fund"]);

  const effort = screen.getByRole("table", { name: "Effort by goal" });
  const rows = within(effort)
    .getAllByRole("row")
    .slice(1)
    .map((r) => plain(r.textContent));
  expect(rows[0]).toBe("Épargne de précaution · filled in 3 months€2,300 missing€945");
  expect(rows[1]).toBe("Voyage au Japon€290 required€290");
  expect(plain(screen.getByRole("region", { name: "This month's effort" }).textContent)).toContain(
    "The other goals get €405 of the €490 they need: they fall €85 behind each month",
  );

  const japan = screen.getByRole("article", { name: "Voyage au Japon" });
  expect(within(japan).getByText("Ahead")).toBeInTheDocument();
  expect(plain(japan.textContent)).toContain("€3,100 of €6,000 (52%)");
  expect(plain(japan.textContent)).toContain("LDDS (€3,100)");
  expect(japan).toHaveTextContent("At this pace, reached 1 month before its deadline.");
  const late = screen.getByRole("article", { name: "Vacances été 2027" });
  expect(plain(late.textContent)).toContain(
    "At this pace, 6 months after its deadline: €80 more a month keeps the date.",
  );
  const fund = screen.getByRole("article", { name: "Épargne de précaution" });
  expect(within(fund).getByText("Fill first")).toBeInTheDocument();
  expect(fund).toHaveTextContent("Filled byJan 2027");

  // archived and cancelled goals stay hidden until asked for
  expect(screen.queryByRole("link", { name: "Voiture" })).toBeNull();
  await userEvent
    .setup()
    .click(screen.getByRole("button", { name: "Show archived and cancelled goals (1)" }));
  const closed = screen.getByRole("region", { name: "Archived and cancelled goals" });
  expect(within(closed).getByRole("link", { name: "Voiture" })).toBeInTheDocument();
  expect(closed).toHaveTextContent("Archived · tracked until Aug 2026");
});

test("a card is edited, archived or cancelled in place", async () => {
  const calls = api();
  render(<TestApp path="/goals" />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Archive Voyage au Japon" }));
  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "PATCH /api/goals/g-japan")?.body).toEqual({
      closed_from: "2026-11",
      closed_as: "archived",
    }),
  );
  expect(screen.getByRole("button", { name: "Cancel the goal Voyage au Japon" })).toBeEnabled();
  // a permanent goal stays in view: it is never archived
  const fund = screen.getByRole("article", { name: "Épargne de précaution" });
  expect(fund).toHaveTextContent("Permanent");
  expect(within(fund).queryByRole("button", { name: /^Archive/ })).toBeNull();

  await user.click(screen.getByRole("button", { name: "Edit Voyage au Japon" }));
  const form = screen.getByRole("form", { name: "Edit the goal" });
  expect(within(form).getByLabelText("Name")).toHaveValue("Voyage au Japon");
  expect(form).toHaveTextContent("Short term, given by the deadline");
});

test("the goals page reads in French", async () => {
  api({ ...owner, language: "fr" });
  render(<TestApp path="/goals" language="fr" />);

  expect(await screen.findByRole("heading", { level: 1, name: "Objectifs" })).toBeInTheDocument();
  expect(plain((await screen.findByRole("status")).textContent)).toContain(
    "Il manque 2 300 € à votre épargne de précaution.",
  );
  const late = screen.getByRole("article", { name: "Vacances été 2027" });
  expect(within(late).getByText("En retard")).toBeInTheDocument();
  expect(plain(late.textContent)).toContain(
    "À ce rythme, 6 mois après l'échéance : 80 € de plus par mois tiennent la date.",
  );
  expect(plain(late.textContent)).toContain("déc. 2027");
});

test("a goal's page gives its estimates and its months, latest first, and deletes it", async () => {
  const calls = api();
  render(<TestApp path="/goals/g-summer" />);

  expect(
    await screen.findByRole("heading", { level: 1, name: "Vacances été 2027" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Behind")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "Trajectory of Vacances été 2027" })).toBeInTheDocument();
  const months = screen.getByRole("table", { name: "Month by month" });
  const rows = within(months)
    .getAllByRole("row")
    .slice(1)
    .map((r) => plain(r.textContent));
  expect(rows[0]).toBe("Oct 2026€900+€100€1,146-€246");
  expect(rows.at(-1)).toBe("May 2026€300—€300€0");

  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Delete" }));
  await user.click(screen.getByRole("button", { name: "Yes, delete" }));
  expect(await screen.findByRole("heading", { level: 1, name: "Goals" })).toBeInTheDocument();
  expect(calls.some((c) => c.route === "DELETE /api/goals/g-summer")).toBe(true);
});

test("a new emergency fund takes the proposal and its wealth lines, never a debt", async () => {
  const calls = api();
  render(<TestApp path="/goals" />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "New goal" }));

  const form = screen.getByRole("form", { name: "New goal" });
  // the tier follows the deadline; the proposal and the optional deadline belong to the emergency fund
  expect(within(form).queryByLabelText("Months of fixed expenses")).toBeNull();
  expect(within(form).getByLabelText("Deadline")).toBeRequired();
  fireEvent.change(within(form).getByLabelText("Deadline"), { target: { value: "2032-01" } });
  expect(form).toHaveTextContent("Long term, given by the deadline");
  fireEvent.change(within(form).getByLabelText("Deadline"), { target: { value: "" } });
  await user.click(within(form).getByRole("checkbox", { name: "Permanent" }));
  expect(within(form).getByLabelText("Deadline")).not.toBeRequired();
  await user.click(within(form).getByRole("checkbox", { name: "Permanent" }));
  await user.click(within(form).getByRole("checkbox", { name: "This is the emergency fund" }));
  // the emergency fund is always permanent
  expect(within(form).getByRole("checkbox", { name: "Permanent" })).toBeChecked();
  expect(within(form).getByRole("checkbox", { name: "Permanent" })).toBeDisabled();
  expect(within(form).getByLabelText("Deadline")).not.toBeRequired();
  await user.type(within(form).getByLabelText("Name"), "Précaution");
  await user.selectOptions(within(form).getByLabelText("Months of fixed expenses"), "4");
  await user.click(within(form).getByRole("button", { name: "Propose from my fixed expenses" }));
  expect(plain((await within(form).findByText(/of fixed expenses a month/)).textContent)).toBe(
    "4 × €950 of fixed expenses a month = €3,800",
  );
  await user.click(within(form).getByRole("button", { name: "Use this amount" }));
  expect(within(form).getByLabelText("Target")).toHaveValue("3800");
  expect(within(form).queryByText("Prêt")).toBeNull();
  await user.click(within(form).getByRole("checkbox", { name: /Livret A/ }));
  expect(plain(form.textContent)).toContain("€5,000 free");
  await user.type(within(form).getByLabelText("Opening amount on Livret A"), "1 000");
  await user.clear(within(form).getByLabelText("Share of the rises of Livret A (%)"));
  await user.type(within(form).getByLabelText("Share of the rises of Livret A (%)"), "80");
  await user.click(within(form).getByRole("button", { name: "Create the goal" }));

  await vi.waitFor(() => expect(calls.some((c) => c.route === "POST /api/goals")).toBe(true));
  expect(calls.find((c) => c.route === "POST /api/goals")?.body).toEqual({
    name: "Précaution",
    precaution: true,
    permanent: true,
    target: "3800.00",
    deadline: null,
    start: "2026-10",
    visibility: "shared",
    fundings: [{ line_id: "l-livret", share: 80, opening: "1000.00" }],
  });
});

test("the owner sets the effort by hand", async () => {
  const calls = api();
  const { unmount } = render(<TestApp path="/goals" />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Effort settings" }));
  await user.selectOptions(
    await screen.findByLabelText("Share of the effort kept for the emergency fund"),
    "0.50",
  );
  await user.click(screen.getByRole("radio", { name: "An amount I set" }));
  await user.type(screen.getByLabelText("Amount per month"), "1 200");
  await user.click(screen.getByRole("button", { name: "Save" }));
  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "PATCH /api/household/settings")?.body).toEqual({
      precaution_share: "0.50",
      goal_capacity: "1200.00",
    }),
  );
  unmount();
});

test("a member only reads the effort settings", async () => {
  api({ ...owner, role: "member" });
  render(<TestApp path="/goals" />);
  await userEvent.setup().click(await screen.findByRole("button", { name: "Effort settings" }));
  expect(
    await screen.findByText("Only the household owner changes these settings."),
  ).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
});

test("the overview shows the three tiers and the emergency fund's warning", async () => {
  api();
  render(<TestApp path="/" />);

  const tile = await screen.findByRole("region", { name: "Goals" });
  expect(plain(tile.textContent)).toContain("Emergency fund84%");
  expect(plain(tile.textContent)).toContain("Your emergency fund is short of €2,300.");
  expect(within(tile).getByRole("link", { name: "Open your goals" })).toHaveAttribute(
    "href",
    "/goals",
  );
});

test("a line shared out beyond 100% says, in French too, how much is left", () => {
  setCurrentLanguage("fr");
  expect(
    translateApiMessage("LDDS would fund open goals beyond 100 %: 25 % of its rises left"),
  ).toBe(
    "LDDS financerait des objectifs ouverts au-delà de 100 % : il ne reste que 25 % de ses hausses à répartir",
  );
  setCurrentLanguage("en");
});

test("an envelope is adjusted by hand on the goal's page, and its adjustment removed", async () => {
  const calls = api();
  render(<TestApp path="/goals/g-summer" />);
  const envelopes = await screen.findByRole("table", { name: "Envelopes" });
  const row = within(envelopes).getByRole("row", { name: /LDDS/ });
  expect(plain(row.textContent)).toContain("€300");
  expect(plain(row.textContent)).toContain("25 %");
  expect(plain(row.textContent)).toContain("Set to €800 from Sept 2026");

  const user = userEvent.setup();
  await user.click(within(row).getByRole("button", { name: "Remove the adjustment of Sept 2026" }));
  await vi.waitFor(() =>
    expect(calls.map((c) => c.route)).toContain(
      "DELETE /api/goals/g-summer/envelopes/l-ldds/2026-09",
    ),
  );

  await user.click(screen.getByRole("button", { name: "Adjust the envelope on LDDS" }));
  const form = screen.getByRole("form", { name: "Adjust the envelope on LDDS" });
  expect(within(form).getByLabelText("Amount it holds")).toHaveValue("900");
  await user.clear(within(form).getByLabelText("Amount it holds"));
  await user.type(within(form).getByLabelText("Amount it holds"), "500");
  await user.click(within(form).getByRole("button", { name: "Save" }));
  await vi.waitFor(() =>
    expect(
      calls.find((c) => c.route === "PUT /api/goals/g-summer/envelopes/l-ldds/2026-10")?.body,
    ).toEqual({ amount: "500.00" }),
  );
});
