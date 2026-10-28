import { render, screen, within } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => {
  delete document.documentElement.dataset.theme;
});

test("the forecast is a tab of the spending, its charts a Dash page", async () => {
  document.documentElement.dataset.theme = "dark";
  fakeApi({ "GET /api/auth/me": () => Response.json(owner) });
  render(<TestApp path="/forecast" />);

  expect(await screen.findByRole("heading", { name: "Forecast" })).toBeVisible();
  expect(screen.getByTitle("The forecast's charts")).toHaveAttribute(
    "src",
    "/dash/forecast?lang=en&theme=dark",
  );
  const tab = screen.getByRole("link", { name: "Forecast" });
  expect(tab).toHaveAttribute("href", "/forecast");
  expect(tab).toHaveAttribute("aria-current", "page");
  expect(within(screen.getByRole("banner")).getByRole("link", { name: "Lines" })).toBeVisible();
});

test("the forecast follows the language", async () => {
  fakeApi({ "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }) });
  render(<TestApp path="/forecast" />);

  expect(await screen.findByRole("heading", { name: "Prévision" })).toBeVisible();
  expect(screen.getByTitle("Les graphiques de la prévision")).toHaveAttribute(
    "src",
    "/dash/forecast?lang=fr&theme=light",
  );
});
