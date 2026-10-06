import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { type FormEvent, useState } from "react";
import QRCode from "react-qr-code";
import {
  login,
  recovery,
  totpConfirm,
  totpSetup,
  totpVerify,
  type UserOut,
} from "../api/generated";
import { Button, Card, ErrorAlert, TextField } from "../components/ui";
import { apiErrorMessage } from "./errors";
import { meQuery } from "./session";

type Step =
  | { kind: "password" }
  | { kind: "totp" }
  | { kind: "recovery" }
  | { kind: "setup" }
  | { kind: "codes"; user: UserOut; codes: string[] };

/** Runs a form submission, keeping track of the pending state and the error message. */
function useSubmit() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = (action: () => Promise<string | null>) => async (event: FormEvent) => {
    event.preventDefault();
    setPending(true);
    setError(await action());
    setPending(false);
  };
  return { pending, error, run };
}

const CODE_ERRORS = { 400: "This code is not valid." };

export function LoginPage() {
  const [step, setStep] = useState<Step>({ kind: "password" });
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const finish = async (user: UserOut) => {
    queryClient.setQueryData(meQuery.queryKey, user);
    await navigate({ to: "/" });
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      {step.kind === "password" && (
        <PasswordStep
          onDone={(next) => setStep({ kind: next === "totp_setup" ? "setup" : "totp" })}
        />
      )}
      {step.kind === "totp" && (
        <CodeStep mode="totp" onDone={finish} onSwitch={() => setStep({ kind: "recovery" })} />
      )}
      {step.kind === "recovery" && (
        <CodeStep mode="recovery" onDone={finish} onSwitch={() => setStep({ kind: "totp" })} />
      )}
      {step.kind === "setup" && (
        <SetupStep onDone={(user, codes) => setStep({ kind: "codes", user, codes })} />
      )}
      {step.kind === "codes" && (
        <RecoveryCodes codes={step.codes} onDone={() => finish(step.user)} />
      )}
    </main>
  );
}

function PasswordStep({ onDone }: { onDone: (next: "totp_setup" | "totp_verify") => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { pending, error, run } = useSubmit();

  const submit = run(async () => {
    const { data, response } = await login({ body: { email, password } });
    if (!data) return apiErrorMessage(response, { 401: "Invalid email or password." });
    onDone(data.next_step);
    return null;
  });

  return (
    <Card title="Sign in">
      <form onSubmit={submit} className="flex flex-col gap-4">
        <TextField
          label="Email"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <ErrorAlert message={error} />
        <Button type="submit" disabled={pending}>
          Sign in
        </Button>
      </form>
    </Card>
  );
}

function CodeStep({
  mode,
  onDone,
  onSwitch,
}: {
  mode: "totp" | "recovery";
  onDone: (user: UserOut) => void;
  onSwitch: () => void;
}) {
  const [code, setCode] = useState("");
  const { pending, error, run } = useSubmit();

  const submit = run(async () => {
    const call = mode === "totp" ? totpVerify : recovery;
    const { data, response } = await call({ body: { code: code.trim() } });
    if (!data) return apiErrorMessage(response, CODE_ERRORS);
    onDone(data);
    return null;
  });

  return (
    <Card title="Two-step verification">
      <form onSubmit={submit} className="flex flex-col gap-4">
        <p className="text-sm text-muted">
          {mode === "totp"
            ? "Enter the 6-digit code from your authenticator app."
            : "Enter one of the recovery codes you saved. Each code works once."}
        </p>
        {mode === "totp" ? (
          <TextField
            key="totp"
            label="Authenticator code"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{6}"
            maxLength={6}
            required
            className="tabular tracking-widest"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        ) : (
          <TextField
            key="recovery"
            label="Recovery code"
            autoComplete="off"
            spellCheck={false}
            required
            className="tabular"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        )}
        <ErrorAlert message={error} />
        <Button type="submit" disabled={pending}>
          Verify
        </Button>
        <Button variant="ghost" onClick={onSwitch}>
          {mode === "totp" ? "Use a recovery code" : "Use the authenticator app"}
        </Button>
      </form>
    </Card>
  );
}

function SetupStep({ onDone }: { onDone: (user: UserOut, codes: string[]) => void }) {
  // A query, not an effect: React StrictMode would call an effect twice and issue two secrets.
  const seed = useQuery({
    queryKey: ["totpSetup"],
    queryFn: async () => {
      const { data } = await totpSetup();
      if (!data) throw new Error("setup failed");
      return data;
    },
    retry: false,
    staleTime: Number.POSITIVE_INFINITY,
    gcTime: 0,
  });
  const [code, setCode] = useState("");
  const { pending, error, run } = useSubmit();

  const submit = run(async () => {
    const { data, response } = await totpConfirm({ body: { code: code.trim() } });
    if (!data) return apiErrorMessage(response, CODE_ERRORS);
    onDone(data.user, data.recovery_codes);
    return null;
  });

  return (
    <Card title="Set up two-step verification">
      {seed.isPending && <p className="text-sm text-muted">Preparing…</p>}
      {seed.isError && <ErrorAlert message="Could not start the setup. Sign in again." />}
      {seed.data && (
        <form onSubmit={submit} className="flex flex-col gap-4">
          <p className="text-sm text-muted">
            Scan this code with an authenticator app (Aegis, 2FAS, Google Authenticator…), then
            enter the 6-digit code it shows.
          </p>
          {/* Always dark on light, whatever the theme: some scanners cannot read inverted codes. */}
          <div
            role="img"
            aria-label="QR code for your authenticator app"
            className="self-center rounded-md bg-neutral-50 p-3"
          >
            <QRCode
              value={seed.data.uri}
              size={176}
              fgColor="var(--color-neutral-900)"
              bgColor="var(--color-neutral-50)"
              aria-hidden
            />
          </div>
          <details className="text-sm">
            <summary className="cursor-pointer text-muted">Can't scan? Enter this key</summary>
            <p className="tabular mt-2 break-all">{seed.data.secret.match(/.{1,4}/g)?.join(" ")}</p>
          </details>
          <TextField
            label="Authenticator code"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{6}"
            maxLength={6}
            required
            className="tabular tracking-widest"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
          <ErrorAlert message={error} />
          <Button type="submit" disabled={pending}>
            Confirm
          </Button>
        </form>
      )}
    </Card>
  );
}

function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(codes.join("\n"));
    setCopied(true);
  };
  return (
    <Card title="Save your recovery codes" wide>
      <div className="flex flex-col gap-4">
        <p className="text-sm text-muted">
          If you lose your phone, each of these codes lets you sign in once. They are shown only
          now: store them in your password manager or print them.
        </p>
        <ul className="tabular grid grid-cols-1 gap-x-6 gap-y-1 rounded-md border border-border p-3 text-sm whitespace-nowrap sm:grid-cols-2">
          {codes.map((code) => (
            <li key={code}>{code}</li>
          ))}
        </ul>
        <Button variant="ghost" onClick={copy}>
          {copied ? "Copied" : "Copy the codes"}
        </Button>
        <Button onClick={onDone}>I have saved my recovery codes</Button>
      </div>
    </Card>
  );
}
