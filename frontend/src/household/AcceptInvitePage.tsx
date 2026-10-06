import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getRouteApi, useNavigate } from "@tanstack/react-router";
import { type FormEvent, useState } from "react";
import { acceptInvite, logout, previewInvite } from "../api/generated";
import { apiErrorMessage, detailSentence } from "../auth/errors";
import { Button, Card, ErrorAlert, TextField } from "../components/ui";

const route = getRouteApi("/invite/$token");

export function AcceptInvitePage() {
  const { token } = route.useParams();
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
            ? (detailSentence(error) ?? "Check the form.")
            : apiErrorMessage(response, {
                404: "This invitation is invalid or has expired.",
                409: "An account already uses this email.",
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
    <main className="flex min-h-screen items-center justify-center px-4">
      {invite.isPending && <p className="text-muted">Checking the invitation…</p>}
      {invite.isError && (
        <Card title="Invitation">
          <p className="text-sm">
            This invitation is invalid or has expired. Ask the household owner for a new link.
          </p>
        </Card>
      )}
      {invite.data && accept.isSuccess && (
        <Card title="Your account is ready">
          <div className="flex flex-col gap-4">
            <p className="text-sm text-muted">
              Sign in with {invite.data.email} and your new password. You will then set up two-step
              verification with an authenticator app.
            </p>
            <Button onClick={goToSignIn}>Sign in</Button>
          </div>
        </Card>
      )}
      {invite.data && !accept.isSuccess && (
        <Card title="Join the household">
          <form onSubmit={submit} className="flex flex-col gap-4">
            <p className="text-sm text-muted">
              You are invited to join {invite.data.household_name} on Kwak Finance. Your account
              will use <span className="text-fg">{invite.data.email}</span>.
            </p>
            <TextField
              label="Your name"
              autoComplete="name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <TextField
              label="Password"
              type="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <TextField
              label="Repeat password"
              type="password"
              autoComplete="new-password"
              required
              value={repeat}
              onChange={(e) => setRepeat(e.target.value)}
            />
            <p className="text-xs text-muted">At least 12 characters. A passphrase is easiest.</p>
            <ErrorAlert
              message={mismatch ? "The passwords do not match." : (accept.error?.message ?? null)}
            />
            <Button type="submit" disabled={accept.isPending}>
              Create my account
            </Button>
          </form>
        </Card>
      )}
    </main>
  );
}
