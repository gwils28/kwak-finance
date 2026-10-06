import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => vi.unstubAllGlobals());

const member = {
  ...owner,
  id: "m1",
  email: "partner@example.com",
  display_name: "Partner",
  role: "member",
};
const pending = {
  id: "i1",
  email: "kid@example.com",
  state: "pending",
  created_at: "2026-01-01T12:00:00Z",
  expires_at: "2026-01-08T12:00:00Z",
};

test("the owner sees members and pending invitations", async () => {
  fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/household/members": () => Response.json([member, owner]),
    "GET /api/invites": () => Response.json([pending]),
  });
  render(<TestApp path="/members" />);

  const members = await screen.findByRole("list", { name: "Members" });
  expect(within(members).getByText("Partner")).toBeInTheDocument();
  expect(within(members).getByText("owner@example.com")).toBeInTheDocument();
  const invites = await screen.findByRole("list", { name: "Pending invitations" });
  expect(within(invites).getByText("kid@example.com")).toBeInTheDocument();
  expect(within(invites).getByText(/Expires 8 Jan 2026/)).toBeInTheDocument();
});

test("inviting shows a link to send to the invitee", async () => {
  let invites: unknown[] = [];
  const calls = fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/household/members": () => Response.json([owner]),
    "GET /api/invites": () => Response.json(invites),
    "POST /api/invites": () => {
      invites = [pending];
      return Response.json({ invite: pending, token: "tok-123" }, { status: 201 });
    },
  });
  render(<TestApp path="/members" />);

  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Email to invite"), "kid@example.com");
  await user.click(screen.getByRole("button", { name: "Create invitation" }));

  expect(
    await screen.findByDisplayValue(`${window.location.origin}/invite/tok-123`),
  ).toBeInTheDocument();
  expect(calls.find((c) => c.route === "POST /api/invites")?.body).toEqual({
    email: "kid@example.com",
  });
  const list = await screen.findByRole("list", { name: "Pending invitations" });
  expect(within(list).getByText("kid@example.com")).toBeInTheDocument();
});

test("inviting an existing account explains the problem", async () => {
  fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/household/members": () => Response.json([owner]),
    "GET /api/invites": () => Response.json([]),
    "POST /api/invites": () =>
      Response.json({ detail: "an account already uses this email" }, { status: 409 }),
  });
  render(<TestApp path="/members" />);

  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Email to invite"), "owner@example.com");
  await user.click(screen.getByRole("button", { name: "Create invitation" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("An account already uses this email.");
});

test("the owner can revoke a pending invitation", async () => {
  let invites = [pending];
  const calls = fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/household/members": () => Response.json([owner]),
    "GET /api/invites": () => Response.json(invites),
    "DELETE /api/invites/i1": () => {
      invites = [];
      return new Response(null, { status: 204 });
    },
  });
  render(<TestApp path="/members" />);

  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("button", { name: "Revoke invitation for kid@example.com" }),
  );

  expect(await screen.findByText("No pending invitations.")).toBeInTheDocument();
  expect(calls.some((c) => c.route === "DELETE /api/invites/i1")).toBe(true);
});

test("members see the household but cannot invite", async () => {
  const calls = fakeApi({
    "GET /api/auth/me": () => Response.json(member),
    "GET /api/household/members": () => Response.json([member, owner]),
  });
  render(<TestApp path="/members" />);

  expect(await screen.findByRole("list", { name: "Members" })).toBeInTheDocument();
  expect(screen.queryByLabelText("Email to invite")).not.toBeInTheDocument();
  expect(calls.some((c) => c.route === "GET /api/invites")).toBe(false);
});

test("the header links to the members page", async () => {
  fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/household/members": () => Response.json([owner]),
    "GET /api/invites": () => Response.json([]),
  });
  render(<TestApp path="/" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("link", { name: "Members" }));

  expect(await screen.findByRole("heading", { name: "Members" })).toBeInTheDocument();
});
