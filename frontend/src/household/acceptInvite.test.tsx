import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner, unauthenticated } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => vi.unstubAllGlobals());

const preview = () =>
  Response.json({
    email: "partner@example.com",
    household_name: "Home",
    expires_at: "2026-01-08T12:00:00Z",
  });

async function fillForm(password = "another long passphrase", confirm = password) {
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Your name"), "Partner");
  await user.type(screen.getByLabelText("Password"), password);
  await user.type(screen.getByLabelText("Repeat password"), confirm);
  await user.click(screen.getByRole("button", { name: "Create my account" }));
  return user;
}

test("the invitee creates an account then goes to sign in", async () => {
  const calls = fakeApi({
    "GET /api/auth/me": unauthenticated,
    "POST /api/auth/logout": unauthenticated,
    "GET /api/invites/accept/tok-123": preview,
    "POST /api/invites/accept/tok-123": () =>
      Response.json(
        { id: "m1", display_name: "Partner", email: "partner@example.com", role: "member" },
        { status: 201 },
      ),
  });
  render(<TestApp path="/invite/tok-123" />);

  expect(await screen.findByText(/You are invited to join Home/)).toBeInTheDocument();
  expect(screen.getByText("partner@example.com")).toBeInTheDocument();

  const user = await fillForm();
  expect(calls.find((c) => c.route === "POST /api/invites/accept/tok-123")?.body).toEqual({
    display_name: "Partner",
    password: "another long passphrase",
  });

  await user.click(await screen.findByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});

test("the two passwords must match before anything is sent", async () => {
  const calls = fakeApi({ "GET /api/invites/accept/tok-123": preview });
  render(<TestApp path="/invite/tok-123" />);

  await fillForm("another long passphrase", "another long passphrasE");

  expect(await screen.findByRole("alert")).toHaveTextContent("The passwords do not match.");
  expect(calls.some((c) => c.route.startsWith("POST"))).toBe(false);
});

test("a password the API rejects shows its reason", async () => {
  fakeApi({
    "GET /api/invites/accept/tok-123": preview,
    "POST /api/invites/accept/tok-123": () =>
      Response.json({ detail: "password must be at least 12 characters" }, { status: 422 }),
  });
  render(<TestApp path="/invite/tok-123" />);

  await fillForm("short", "short");

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Password must be at least 12 characters.",
  );
});

test("an invalid link says so", async () => {
  fakeApi({
    "GET /api/invites/accept/old": () =>
      Response.json({ detail: "this invitation is invalid or has expired" }, { status: 404 }),
  });
  render(<TestApp path="/invite/old" />);

  expect(await screen.findByText(/This invitation is invalid or has expired/)).toBeInTheDocument();
  expect(screen.queryByLabelText("Your name")).not.toBeInTheDocument();
});

test("someone else signed in on this browser is signed out first", async () => {
  let signedIn = true;
  fakeApi({
    "GET /api/auth/me": () => (signedIn ? Response.json(owner) : unauthenticated()),
    "POST /api/auth/logout": () => {
      signedIn = false;
      return new Response(null, { status: 204 });
    },
    "GET /api/invites/accept/tok-123": preview,
    "POST /api/invites/accept/tok-123": () =>
      Response.json(
        { id: "m1", display_name: "Partner", email: "partner@example.com", role: "member" },
        { status: 201 },
      ),
  });
  render(<TestApp path="/invite/tok-123" />);

  const user = await fillForm();
  await user.click(await screen.findByRole("button", { name: "Sign in" }));

  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});
