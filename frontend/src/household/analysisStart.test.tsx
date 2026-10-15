import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => vi.unstubAllGlobals());

function api(me: object = owner, start: string | null = null, wealth: string | null = null) {
  const settings = { warn_at: "0.80", analysis_start: start, wealth_start: wealth };
  return fakeApi({
    "GET /api/auth/me": () => Response.json(me),
    "GET /api/household/members": () => Response.json([owner]),
    "GET /api/invites": () => Response.json([]),
    "GET /api/household/settings": () => Response.json(settings),
    "PATCH /api/household/settings": (body) => Response.json({ ...settings, ...(body as object) }),
  });
}

test("the owner sets the month analyses start from", async () => {
  const calls = api();
  render(<TestApp path="/members" />);
  const section = await screen.findByRole("region", { name: "Analyses start" });
  expect(await within(section).findByText("Every month counts.")).toBeInTheDocument();

  // jsdom cannot type into <input type="month">: set the value as the picker would.
  fireEvent.change(within(section).getByLabelText("First month analysed"), {
    target: { value: "2026-10" },
  });
  await userEvent.setup().click(within(section).getByRole("button", { name: "Save" }));

  expect(calls.find((c) => c.route === "PATCH /api/household/settings")?.body).toEqual({
    analysis_start: "2026-10",
  });
});

test("the owner can count every month again", async () => {
  const calls = api(owner, "2026-10");
  render(<TestApp path="/members" />);
  const section = await screen.findByRole("region", { name: "Analyses start" });
  expect(await within(section).findByText("Analyses start in Oct 2026.")).toBeInTheDocument();

  await userEvent.setup().click(within(section).getByRole("button", { name: "Count every month" }));
  expect(calls.find((c) => c.route === "PATCH /api/household/settings")?.body).toEqual({
    analysis_start: null,
  });
});

test("a member sees the start without changing it", async () => {
  api({ ...owner, role: "member" }, "2026-10");
  render(<TestApp path="/members" />);
  const section = await screen.findByRole("region", { name: "Analyses start" });
  expect(await within(section).findByText("Analyses start in Oct 2026.")).toBeInTheDocument();
  expect(within(section).queryByRole("button")).not.toBeInTheDocument();
});

test("in French, the setting speaks French", async () => {
  api({ ...owner, language: "fr" }, "2026-10");
  render(<TestApp path="/members" language="fr" />);
  const section = await screen.findByRole("region", { name: "Début des analyses" });
  expect(
    await within(section).findByText("Les analyses commencent en oct. 2026."),
  ).toBeInTheDocument();
});

test("the owner sets the wealth start apart from the analyses", async () => {
  const calls = api(owner, "2026-10");
  render(<TestApp path="/members" />);
  const section = await screen.findByRole("region", { name: "Wealth start" });
  expect(
    await within(section).findByText("The wealth follows the analyses start (Oct 2026)."),
  ).toBeInTheDocument();

  fireEvent.change(within(section).getByLabelText("First month of the wealth"), {
    target: { value: "2026-01" },
  });
  await userEvent.setup().click(within(section).getByRole("button", { name: "Save" }));
  expect(calls.find((c) => c.route === "PATCH /api/household/settings")?.body).toEqual({
    wealth_start: "2026-01",
  });
});

test("the wealth start can follow the analyses again", async () => {
  const calls = api({ ...owner, language: "fr" }, "2026-10", "2026-01");
  render(<TestApp path="/members" language="fr" />);
  const section = await screen.findByRole("region", { name: "Début du patrimoine" });
  expect(
    await within(section).findByText("Le patrimoine commence en janv. 2026."),
  ).toBeInTheDocument();

  await userEvent
    .setup()
    .click(within(section).getByRole("button", { name: "Suivre le début des analyses" }));
  expect(calls.find((c) => c.route === "PATCH /api/household/settings")?.body).toEqual({
    wealth_start: null,
  });
});
