import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner, unauthenticated } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";
import { initialLanguage } from ".";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

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
  balance: "1234.56",
};

function api(language: string | null) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json({ ...owner, language }),
    "PATCH /api/auth/me": (body) => Response.json({ ...owner, ...(body as object) }),
    "GET /api/accounts": () => Response.json([checking]),
  });
}

const plain = (text: string | null) => text?.replace(/[  ]/g, " ");
const patches = (calls: { route: string; body: unknown }[]) =>
  calls.filter((c) => c.route === "PATCH /api/auth/me").map((c) => c.body);

test("an account set to French shows the app in French, with French amounts and dates", async () => {
  api("fr");
  render(<TestApp path="/accounts" language="en" />);

  expect(await screen.findByRole("heading", { name: "Comptes" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Opérations" })).toBeInTheDocument();
  const row = await screen.findByRole("listitem");
  expect(plain(row.textContent)).toContain("1 234,56 €");
  expect(row).toHaveTextContent("1 janv. 2026");
  expect(document.documentElement.lang).toBe("fr");
});

test("switching the language translates the page and saves it with the account", async () => {
  const calls = api("en");
  const user = userEvent.setup();
  render(<TestApp path="/accounts" />);

  await screen.findByRole("heading", { name: "Accounts" });
  expect(await screen.findByRole("listitem")).toHaveTextContent("€1,234.56");
  await user.selectOptions(screen.getByLabelText("Language"), "fr");

  expect(await screen.findByRole("heading", { name: "Comptes" })).toBeInTheDocument();
  expect(screen.getByLabelText("Langue")).toHaveValue("fr");
  await waitFor(() => expect(patches(calls)).toEqual([{ language: "fr" }]));
  expect(localStorage.getItem("kwak-language")).toBe("fr");
});

test("a first sign-in keeps the language already shown and saves it", async () => {
  const calls = api(null);
  render(<TestApp path="/accounts" language="fr" />);

  expect(await screen.findByRole("heading", { name: "Comptes" })).toBeInTheDocument();
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
