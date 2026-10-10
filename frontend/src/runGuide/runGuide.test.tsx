import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner, unauthenticated } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

test("the footer of a signed-in page links to the guide on running the app", async () => {
  fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/accounts": () => Response.json([]),
  });
  const user = userEvent.setup();
  render(<TestApp path="/accounts" />);

  await screen.findByRole("heading", { name: "Accounts" });
  await user.click(screen.getByRole("link", { name: "How to run the app" }));

  expect(await screen.findByRole("heading", { name: "Running Kwak Finance" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Start and stop" })).toBeInTheDocument();
  expect(screen.getAllByText("make up").length).toBeGreaterThan(0);
});

test("the guide opens without signing in, from the sign-in page, in French too", async () => {
  fakeApi({ "GET /api/auth/me": unauthenticated });
  const user = userEvent.setup();
  render(<TestApp path="/login" language="fr" />);

  await user.click(await screen.findByRole("link", { name: "Lancer et arrêter l'application" }));

  expect(
    await screen.findByRole("heading", { name: "Faire tourner Kwak Finance" }),
  ).toBeInTheDocument();
  const danger = screen.getByText("docker compose down -v");
  expect(danger.parentElement).not.toHaveTextContent("Copier");
});

test("a command can be copied with one click", async () => {
  fakeApi({ "GET /api/auth/me": unauthenticated });
  const user = userEvent.setup();
  render(<TestApp path="/run" />);

  await screen.findByRole("heading", { name: "Running Kwak Finance" });
  const [first] = screen.getAllByRole("button", { name: "Copy" });
  if (!first) throw new Error("no copy button");
  await user.click(first);

  expect(await navigator.clipboard.readText()).toBe("docker compose version");
  expect(await screen.findByRole("button", { name: "Copied" })).toBeInTheDocument();
});
