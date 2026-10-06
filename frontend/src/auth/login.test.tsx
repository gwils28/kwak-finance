import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner, unauthenticated } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => vi.unstubAllGlobals());

const RECOVERY_CODES = Array.from({ length: 10 }, (_, i) => `aaaa-bbbb-cccc-dd${i}${i}`);

async function submitPassword() {
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Email"), "owner@example.com");
  await user.type(screen.getByLabelText("Password"), "correct horse battery");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  return user;
}

test("an anonymous visitor is sent to the sign-in page", async () => {
  fakeApi({ "GET /api/auth/me": unauthenticated });
  render(<TestApp path="/" />);
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});

test("password then authenticator code leads to the home page", async () => {
  const calls = fakeApi({
    "GET /api/auth/me": unauthenticated,
    "POST /api/auth/login": () => Response.json({ user: owner, next_step: "totp_verify" }),
    "POST /api/auth/totp/verify": () => Response.json(owner),
  });
  render(<TestApp path="/login" />);

  const user = await submitPassword();
  await user.type(await screen.findByLabelText("Authenticator code"), "123456");
  await user.click(screen.getByRole("button", { name: "Verify" }));

  expect(await screen.findByText("Wilson")).toBeInTheDocument();
  expect(calls.find((c) => c.route === "POST /api/auth/totp/verify")?.body).toEqual({
    code: "123456",
  });
});

test("first sign-in sets up the authenticator and shows the recovery codes", async () => {
  fakeApi({
    "GET /api/auth/me": unauthenticated,
    "POST /api/auth/login": () => Response.json({ user: owner, next_step: "totp_setup" }),
    "POST /api/auth/totp/setup": () =>
      Response.json({
        secret: "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ",
        uri: "otpauth://totp/Kwak%20Finance:owner%40example.com?secret=GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ",
      }),
    "POST /api/auth/totp/confirm": () =>
      Response.json({ user: owner, recovery_codes: RECOVERY_CODES }),
  });
  render(<TestApp path="/login" />);

  const user = await submitPassword();
  expect(
    await screen.findByRole("img", { name: "QR code for your authenticator app" }),
  ).toBeVisible();
  expect(screen.getByText("GEZD GNBV GY3T QOJQ GEZD GNBV GY3T QOJQ")).toBeInTheDocument();

  await user.type(screen.getByLabelText("Authenticator code"), "123456");
  await user.click(screen.getByRole("button", { name: "Confirm" }));

  for (const code of RECOVERY_CODES) expect(await screen.findByText(code)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "I have saved my recovery codes" }));
  expect(await screen.findByText("Wilson")).toBeInTheDocument();
});

test("a recovery code can replace the authenticator code", async () => {
  const calls = fakeApi({
    "GET /api/auth/me": unauthenticated,
    "POST /api/auth/login": () => Response.json({ user: owner, next_step: "totp_verify" }),
    "POST /api/auth/recovery": () => Response.json(owner),
  });
  render(<TestApp path="/login" />);

  const user = await submitPassword();
  await user.click(await screen.findByRole("button", { name: "Use a recovery code" }));
  await user.type(screen.getByLabelText("Recovery code"), "aaaa-bbbb-cccc-dd00");
  await user.click(screen.getByRole("button", { name: "Verify" }));

  expect(await screen.findByText("Wilson")).toBeInTheDocument();
  expect(calls.find((c) => c.route === "POST /api/auth/recovery")?.body).toEqual({
    code: "aaaa-bbbb-cccc-dd00",
  });
});

test("wrong credentials show an error and keep the form", async () => {
  fakeApi({
    "GET /api/auth/me": unauthenticated,
    "POST /api/auth/login": () =>
      Response.json({ detail: "invalid email or password" }, { status: 401 }),
  });
  render(<TestApp path="/login" />);

  await submitPassword();

  expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password.");
  expect(screen.getByLabelText("Email")).toBeInTheDocument();
});

test("a wrong code shows an error", async () => {
  fakeApi({
    "GET /api/auth/me": unauthenticated,
    "POST /api/auth/login": () => Response.json({ user: owner, next_step: "totp_verify" }),
    "POST /api/auth/totp/verify": () => Response.json({ detail: "invalid code" }, { status: 400 }),
  });
  render(<TestApp path="/login" />);

  const user = await submitPassword();
  await user.type(await screen.findByLabelText("Authenticator code"), "000000");
  await user.click(screen.getByRole("button", { name: "Verify" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("This code is not valid.");
});

test("rate limiting tells the user how long to wait", async () => {
  fakeApi({
    "GET /api/auth/me": unauthenticated,
    "POST /api/auth/login": () =>
      Response.json(
        { detail: "too many failed attempts, try again later" },
        { status: 429, headers: { "Retry-After": "540" } },
      ),
  });
  render(<TestApp path="/login" />);

  await submitPassword();

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Too many failed attempts. Try again in 9 minutes.",
  );
});

test("signing out returns to the sign-in page", async () => {
  let signedIn = true;
  const calls = fakeApi({
    "GET /api/auth/me": () => (signedIn ? Response.json(owner) : unauthenticated()),
    "POST /api/auth/logout": () => {
      signedIn = false;
      return new Response(null, { status: 204 });
    },
  });
  render(<TestApp path="/" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Sign out" }));

  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  expect(calls.some((c) => c.route === "POST /api/auth/logout")).toBe(true);
});

test("a signed-in user visiting the sign-in page goes home", async () => {
  fakeApi({ "GET /api/auth/me": () => Response.json(owner) });
  render(<TestApp path="/login" />);
  expect(await screen.findByText("Wilson")).toBeInTheDocument();
});
