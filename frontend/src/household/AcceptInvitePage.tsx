import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getRouteApi, useNavigate } from "@tanstack/react-router";
import { type FormEvent, useState } from "react";
import { acceptInvite, logout, previewInvite } from "../api/generated";
import { apiErrorMessage, detailSentence } from "../auth/errors";
import { LanguageSelect } from "../components/LanguageSelect";
import { Button, Card, ErrorAlert, TextField } from "../components/ui";
import { useI18n } from "../i18n";

const route = getRouteApi("/invite/$token");

export function AcceptInvitePage() {
  const { token } = route.useParams();
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const invite = useQuery({
    queryKey: ["invite", token],
    queryFn: async () => (await previewInvite({ path: { token }, throwOnError: true })).data,
    retry: false,
  });
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [mismatch, setMismatch] = useState(false);

  const accept = useMutation({
    mutationFn: async () => {
      const { data, error, response } = await acceptInvite({
        path: { token },
        body: { display_name: name, password },
      });
      if (!data) {
        throw new Error(
          response?.status === 422
            ? (detailSentence(error) ?? t.errors.checkForm)
            : apiErrorMessage(t, response, {
                404: t.household.invalidInvite,
                409: t.household.emailTaken,
              }),
        );
      }
      return data;
    },
  });

  // Someone else may be signed in on this browser (e.g. the owner testing the link).
  const goToSignIn = async () => {
    await logout();
    queryClient.clear();
    await navigate({ to: "/login" });
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setMismatch(password !== repeat);
    if (password === repeat) accept.mutate();
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-4">
      <LanguageSelect />
      {invite.isPending && <p className="text-muted">{t.household.checking}</p>}
      {invite.isError && (
        <Card title={t.household.invitation}>
          <p className="text-sm">{t.household.askNewLink}</p>
        </Card>
      )}
      {invite.data && accept.isSuccess && (
        <Card title={t.household.ready}>
          <div className="flex flex-col gap-4">
            <p className="text-sm text-muted">{t.household.readyHelp(invite.data.email)}</p>
            <Button onClick={goToSignIn}>{t.household.signIn}</Button>
          </div>
        </Card>
      )}
      {invite.data && !accept.isSuccess && (
        <Card title={t.household.join}>
          <form onSubmit={submit} className="flex flex-col gap-4">
            <p className="text-sm text-muted">
              {t.household.invitedTo(invite.data.household_name)}
              <span className="text-fg">{invite.data.email}</span>.
            </p>
            <TextField
              label={t.household.yourName}
              autoComplete="name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <TextField
              label={t.household.password}
              type="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <TextField
              label={t.household.repeatPassword}
              type="password"
              autoComplete="new-password"
              required
              value={repeat}
              onChange={(e) => setRepeat(e.target.value)}
            />
            <p className="text-xs text-muted">{t.household.passwordHelp}</p>
            <ErrorAlert
              message={mismatch ? t.household.mismatch : (accept.error?.message ?? null)}
            />
            <Button type="submit" disabled={accept.isPending}>
              {t.household.createAccount}
            </Button>
          </form>
        </Card>
      )}
    </main>
  );
}
