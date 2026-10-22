import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => vi.unstubAllGlobals());

const plain = (text: string | null) => text?.replace(/[  ]/g, " ");

const entry = (action: string, kind: string, details: object, extra: object = {}) => ({
  id: `e-${action}`,
  at: "2026-10-14T20:15:00Z",
  action,
  kind,
  user_id: owner.id,
  user_name: "Wilson",
  ip: null,
  details,
  ...extra,
});
const entries = [
  entry("signed_in", "sign_in", { method: "totp" }, { ip: "192.168.1.20" }),
  entry("sign_in_failed", "sign_in", { step: "password" }, { user_name: "Léa", user_id: "m1" }),
  entry("settings_changed", "household", { warn_at: "0.90" }),
  entry("settings_changed", "household", { analysis_start: "2026-10" }, { id: "e-start" }),
  entry("settings_changed", "household", { analysis_start: "" }, { id: "e-every" }),
  entry(
    "invite_revoked",
    "household",
    { email: "a@example.com" },
    { user_id: null, user_name: null },
  ),
  entry("goal_deleted", "deletion", { name: "Voyage", tier: "medium" }, { id: "e-goal" }),
  entry("settings_changed", "household", { precaution_share: "0.70" }, { id: "e-share" }),
  entry("settings_changed", "household", { goal_capacity: "1350.00" }, { id: "e-cap" }),
  entry(
    "spending_line_deleted",
    "deletion",
    { label: "Cinéma", amount: "-12.00", date: "2026-10-14" },
    { id: "e-line" },
  ),
  entry(
    "spending_category_deleted",
    "deletion",
    { name: "Loisirs", moved_to: "Divers" },
    { id: "e-cat" },
  ),
];
const members = [
  { id: owner.id, display_name: "Wilson", email: owner.email, role: "owner" },
  { id: "m1", display_name: "Léa", email: "lea@example.com", role: "member" },
];

function api(me: object = owner, page = { items: entries, total: entries.length }) {
  const asked: URL[] = [];
  fakeApi({
    "GET /api/auth/me": () => Response.json(me),
    "GET /api/household/members": () => Response.json(members),
    "GET /api/audit": (_, url) => {
      asked.push(url);
      return Response.json(page);
    },
  });
  return asked;
}

test("the account menu leads to the activity log, each entry in words", async () => {
  api();
  render(<TestApp path="/" />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Account menu: Wilson" }));
  await user.click(screen.getByRole("link", { name: "Activity log" }));

  const table = await screen.findByRole("table", { name: "Activity log" });
  const rows = within(table)
    .getAllByRole("row")
    .slice(1)
    .map((r) => plain(r.textContent));
  expect(rows[0]).toMatch(/WilsonSigned in192\.168\.1\.20$/);
  expect(rows[1]).toContain("LéaFailed sign-in: wrong password");
  expect(rows[2]).toContain("Set the budget warning threshold to 90%");
  // Entries from before v1.0 still read: the analyses start is gone, its history stays.
  expect(rows[3]).toContain("Set the analyses to start in Oct 2026");
  expect(rows[4]).toContain("Set the analyses to count every month");
  expect(rows[5]).toContain("A former memberRevoked the invitation of a@example.com");
  expect(rows[6]).toContain("Deleted the goal Voyage");
  expect(rows[7]).toContain("Set the precaution share of the goals' effort to 70%");
  expect(rows[8]).toContain("Set the goals' monthly capacity to €1,350.00");
  expect(rows[9]).toContain("Deleted the line “Cinéma” (-€12.00, 14 Oct 2026)");
  expect(rows[10]).toContain("Deleted the category Loisirs, its lines moved to Divers");
});

test("the owner filters by kind and by member", async () => {
  const asked = api();
  render(<TestApp path="/activity" />);
  const user = userEvent.setup();
  await screen.findByRole("table", { name: "Activity log" });

  await user.selectOptions(screen.getByLabelText("Kind"), "deletion");
  await vi.waitFor(() => expect(asked.at(-1)?.searchParams.get("kind")).toBe("deletion"));
  await user.selectOptions(await screen.findByLabelText("Member"), "m1");
  await vi.waitFor(() => expect(asked.at(-1)?.searchParams.get("user_id")).toBe("m1"));
});

test("a member sees their own entries, without the member filter", async () => {
  api({ ...owner, role: "member" });
  render(<TestApp path="/activity" />);
  expect(await screen.findByText(/Your sensitive actions/)).toBeInTheDocument();
  expect(screen.queryByLabelText("Member")).not.toBeInTheDocument();
});

test("a long log is read page by page", async () => {
  const asked = api(owner, { items: entries, total: 120 });
  render(<TestApp path="/activity" />);
  const user = userEvent.setup();
  expect(await screen.findByText("1–50 of 120")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Newer" })).toBeDisabled();

  await user.click(screen.getByRole("button", { name: "Older" }));
  await vi.waitFor(() => expect(asked.at(-1)?.searchParams.get("offset")).toBe("50"));
  expect(await screen.findByText("51–100 of 120")).toBeInTheDocument();
});

test("an empty log says so", async () => {
  api(owner, { items: [], total: 0 });
  render(<TestApp path="/activity" />);
  expect(await screen.findByText("Nothing logged yet.")).toBeInTheDocument();
});

test("in French, the log speaks French", async () => {
  api({ ...owner, language: "fr" });
  render(<TestApp path="/activity" language="fr" />);
  const table = await screen.findByRole("table", { name: "Journal d'activité" });
  expect(plain(table.textContent)).toContain("Ligne « Cinéma » supprimée (-12,00 €, 14 oct. 2026)");
});
