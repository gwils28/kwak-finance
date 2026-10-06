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
import { LanguageSelect } from "../components/LanguageSelect";
import { Button, Card, ErrorAlert, TextField } from "../components/ui";
import { useI18n } from "../i18n";
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

export function LoginPage() {
  const [step, setStep] = useState<Step>({ kind: "password" });
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const finish = async (user: UserOut) => {
    queryClient.setQueryData(meQuery.queryKey, user);
    await navigate({ to: "/" });
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-4">
      <LanguageSelect />
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
  const { t } = useI18n();

  const submit = run(async () => {
    const { data, response } = await login({ body: { email, password } });
    if (!data) return apiErrorMessage(t, response, { 401: t.auth.invalidCredentials });
    onDone(data.next_step);
    return null;
  });

  return (
    <Card title={t.auth.signIn}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <TextField
          label={t.auth.email}
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <TextField
          label={t.auth.password}
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <ErrorAlert message={error} />
        <Button type="submit" disabled={pending}>
          {t.auth.signIn}
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
  const { t } = useI18n();

  const submit = run(async () => {
    const call = mode === "totp" ? totpVerify : recovery;
    const { data, response } = await call({ body: { code: code.trim() } });
    if (!data) return apiErrorMessage(t, response, { 400: t.auth.invalidCode });
    onDone(data);
    return null;
  });

  return (
    <Card title={t.auth.twoStep}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <p className="text-sm text-muted">
          {mode === "totp" ? t.auth.enterTotp : t.auth.enterRecovery}
        </p>
        {mode === "totp" ? (
          <TextField
            key="totp"
            label={t.auth.authenticatorCode}
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
            label={t.auth.recoveryCode}
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
          {t.auth.verify}
        </Button>
        <Button variant="ghost" onClick={onSwitch}>
          {mode === "totp" ? t.auth.useRecovery : t.auth.useAuthenticator}
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
  const { t } = useI18n();

  const submit = run(async () => {
    const { data, response } = await totpConfirm({ body: { code: code.trim() } });
    if (!data) return apiErrorMessage(t, response, { 400: t.auth.invalidCode });
    onDone(data.user, data.recovery_codes);
    return null;
  });

  return (
    <Card title={t.auth.setupTitle}>
      {seed.isPending && <p className="text-sm text-muted">{t.auth.preparing}</p>}
      {seed.isError && <ErrorAlert message={t.auth.setupFailed} />}
      {seed.data && (
        <form onSubmit={submit} className="flex flex-col gap-4">
          <p className="text-sm text-muted">{t.auth.scanInstructions}</p>
          {/* Always dark on light, whatever the theme: some scanners cannot read inverted codes. */}
          <div
            role="img"
            aria-label={t.auth.qrLabel}
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
            <summary className="cursor-pointer text-muted">{t.auth.cantScan}</summary>
            <p className="tabular mt-2 break-all">{seed.data.secret.match(/.{1,4}/g)?.join(" ")}</p>
          </details>
          <TextField
            label={t.auth.authenticatorCode}
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
            {t.auth.confirm}
          </Button>
        </form>
      )}
    </Card>
  );
}

function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const [copied, setCopied] = useState(false);
  const { t } = useI18n();
  const copy = async () => {
    await navigator.clipboard.writeText(codes.join("\n"));
    setCopied(true);
  };
  return (
    <Card title={t.auth.saveCodesTitle} wide>
      <div className="flex flex-col gap-4">
        <p className="text-sm text-muted">{t.auth.saveCodesText}</p>
        <ul className="tabular grid grid-cols-1 gap-x-6 gap-y-1 rounded-md border border-border p-3 text-sm whitespace-nowrap sm:grid-cols-2">
          {codes.map((code) => (
            <li key={code}>{code}</li>
          ))}
        </ul>
        <Button variant="ghost" onClick={copy}>
          {copied ? t.common.copied : t.auth.copyCodes}
        </Button>
        <Button onClick={onDone}>{t.auth.savedCodes}</Button>
      </div>
    </Card>
  );
}
