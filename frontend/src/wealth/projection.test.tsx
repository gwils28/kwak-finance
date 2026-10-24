import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => {
  delete document.documentElement.dataset.theme;
});

test("the projection embeds the Dash page in the app's language and theme", async () => {
  document.documentElement.dataset.theme = "dark";
  fakeApi({ "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }) });
  render(<TestApp path="/wealth/projection" />);

  expect(await screen.findByRole("heading", { name: "Projection du patrimoine" })).toBeVisible();
  const frame = screen.getByTitle("Les graphiques de la projection");
  expect(frame).toHaveAttribute("src", "/dash/projection?lang=fr&theme=dark");

  // Switching the theme reloads the page in the new one.
  document.documentElement.dataset.theme = "light";
  await waitFor(() => expect(frame).toHaveAttribute("src", "/dash/projection?lang=fr&theme=light"));
});
