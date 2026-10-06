import { useMutation, useQuery, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import {
  createInvite,
  type InviteOut,
  listInvites,
  listMembers,
  revokeInvite,
} from "../api/generated";
import { apiErrorMessage } from "../auth/errors";
import { meQuery } from "../auth/session";
import { Button, ErrorAlert, TextField } from "../components/ui";

const DATE = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" });

const membersQuery = {
  queryKey: ["members"],
  queryFn: async () => (await listMembers({ throwOnError: true })).data,
};

const invitesQuery = {
  queryKey: ["invites"],
  queryFn: async () => (await listInvites({ throwOnError: true })).data,
};

export function MembersPage() {
  const { data: user } = useSuspenseQuery(meQuery);
  const members = useQuery(membersQuery);
  const isOwner = user.role === "owner";

  return (
    <div className="flex flex-col gap-10">
      <section>
        <h1 className="text-3xl font-black tracking-tight">Members</h1>
        {members.isPending && <p className="mt-4 text-sm text-muted">Loading…</p>}
        {members.isError && <ErrorAlert message="Could not load the members." />}
        {members.data && (
          <ul
            aria-label="Members"
            className="mt-4 divide-y divide-border rounded-lg border border-border bg-surface"
          >
            {members.data.map((m) => (
              <li key={m.id} className="flex items-center justify-between gap-4 px-4 py-3">
                <div>
                  <p className="font-medium">{m.display_name}</p>
                  <p className="text-sm text-muted">{m.email}</p>
                </div>
                <span className="text-sm text-muted">
                  {m.role === "owner" ? "Owner" : "Member"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
      {isOwner && <Invitations />}
    </div>
  );
}

function Invitations() {
  const queryClient = useQueryClient();
  const invites = useQuery(invitesQuery);
  const [email, setEmail] = useState("");
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const create = useMutation({
    mutationFn: async (address: string) => {
      const { data, response } = await createInvite({ body: { email: address } });
      if (!data)
        throw new Error(
          apiErrorMessage(response, {
            409: "An account already uses this email.",
            422: "This email address is not valid.",
          }),
        );
      return data;
    },
    onSuccess: (created) => {
      setLink(`${window.location.origin}/invite/${created.token}`);
      setCopied(false);
      setEmail("");
      void queryClient.invalidateQueries({ queryKey: invitesQuery.queryKey });
    },
  });

  const revoke = useMutation({
    mutationFn: async (invite: InviteOut) => {
      await revokeInvite({ path: { invite_id: invite.id }, throwOnError: true });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: invitesQuery.queryKey }),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(email);
  };

  const copy = async () => {
    if (!link) return;
    await navigator.clipboard.writeText(link);
    setCopied(true);
  };

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-2xl font-black tracking-tight">Invite someone</h2>
      <p className="text-sm text-muted">
        Kwak Finance sends no email: create a link, then send it yourself (message, SMS…). It works
        once and expires after 7 days. The new member sets up two-step verification at first
        sign-in.
      </p>
      <form onSubmit={submit} className="flex max-w-md flex-col gap-3">
        <TextField
          label="Email to invite"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <ErrorAlert message={create.error?.message ?? null} />
        <Button type="submit" disabled={create.isPending} className="self-start">
          Create invitation
        </Button>
      </form>
      {link && (
        <div className="flex max-w-xl flex-col gap-2 rounded-lg border border-accent p-4">
          <TextField
            label="Invitation link"
            readOnly
            value={link}
            onFocus={(e) => e.target.select()}
            className="tabular text-sm"
          />
          <Button variant="ghost" onClick={copy} className="self-start">
            {copied ? "Copied" : "Copy the link"}
          </Button>
          <p className="text-sm text-muted">This link is shown only once.</p>
        </div>
      )}
      <h3 className="mt-4 text-lg font-bold">Pending invitations</h3>
      {invites.data?.length === 0 && <p className="text-sm text-muted">No pending invitations.</p>}
      {invites.data && invites.data.length > 0 && (
        <ul
          aria-label="Pending invitations"
          className="divide-y divide-border rounded-lg border border-border bg-surface"
        >
          {invites.data.map((invite) => (
            <li key={invite.id} className="flex items-center justify-between gap-4 px-4 py-3">
              <div>
                <p className="font-medium">{invite.email}</p>
                <p className="text-sm text-muted">
                  Expires {DATE.format(new Date(invite.expires_at))}
                </p>
              </div>
              <Button
                variant="ghost"
                aria-label={`Revoke invitation for ${invite.email}`}
                disabled={revoke.isPending}
                onClick={() => revoke.mutate(invite)}
              >
                Revoke
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
