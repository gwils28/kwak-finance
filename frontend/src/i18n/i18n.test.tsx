import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { bakery, spendingHandlers } from "../spending/fixtures";
import { fakeApi, owner, unauthenticated } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";
import { initialLanguage } from ".";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

function api(language: string | null) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json({ ...owner, language }),
    "PATCH /api/auth/me": (body) => Response.json({ ...owner, ...(body as object) }),
    ...spendingHandlers([bakery]),
  });
}

const PATH = "/spending?month=2026-10";
const plain = (text: string | null) => text?.replace(/[  ]/g, " ");
const patches = (calls: { route: string; body: unknown }[]) =>
  calls.filter((c) => c.route === "PATCH /api/auth/me").map((c) => c.body);

test("an account set to French shows the app in French, with French amounts and dates", async () => {
  api("fr");
  render(<TestApp path={PATH} language="en" />);

  expect(await screen.findByRole("heading", { name: "Dépenses" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Lignes" })).toBeInTheDocument();
  expect(plain((await screen.findByText(/3\s000,00\s€/)).textContent)).toBe("3 000,00 €");
  expect(screen.getByRole("heading", { name: "oct. 2026" })).toBeInTheDocument();
  expect(document.documentElement.lang).toBe("fr");
});

test("switching the language translates the page and saves it with the account", async () => {
  const calls = api("en");
  const user = userEvent.setup();
  render(<TestApp path={PATH} />);

  await screen.findByRole("heading", { name: "Spending" });
  expect(await screen.findByText("€3,000.00")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Account menu: Wilson" }));
  await user.click(screen.getByRole("radio", { name: "Français" }));

  expect(await screen.findByRole("heading", { name: "Dépenses" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Menu du compte : Wilson" }));
  expect(screen.getByRole("radio", { name: "Français" })).toBeChecked();
  await waitFor(() => expect(patches(calls)).toEqual([{ language: "fr" }]));
  expect(localStorage.getItem("kwak-language")).toBe("fr");
});

test("a first sign-in keeps the language already shown and saves it", async () => {
  const calls = api(null);
  render(<TestApp path={PATH} language="fr" />);

  expect(await screen.findByRole("heading", { name: "Dépenses" })).toBeInTheDocument();
  await waitFor(() => expect(patches(calls)).toEqual([{ language: "fr" }]));
});

test("the sign-in page can switch language before signing in", async () => {
  const calls = fakeApi({ "GET /api/auth/me": unauthenticated });
  const user = userEvent.setup();
  render(<TestApp path="/login" />);

  await screen.findByRole("button", { name: "Sign in" });
  await user.selectOptions(screen.getByLabelText("Language"), "fr");

  expect(await screen.findByRole("button", { name: "Se connecter" })).toBeInTheDocument();
  expect(patches(calls)).toEqual([]);
});

test("the starting language is the last one used here, else the browser's", () => {
  vi.stubGlobal("navigator", { languages: ["fr-FR", "en"] });
  expect(initialLanguage()).toBe("fr");
  vi.stubGlobal("navigator", { languages: ["de-DE", "fr"] });
  expect(initialLanguage()).toBe("en");
  localStorage.setItem("kwak-language", "fr");
  expect(initialLanguage()).toBe("fr");
});
