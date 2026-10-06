import { useMutation, useQuery, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type FormEvent, useId, useState } from "react";
import {
  type AccountOut,
  type AccountType,
  createAccount,
  listAccounts,
  listInstitutions,
  updateAccount,
  type Visibility,
} from "../api/generated";
import { apiErrorMessage, detailSentence } from "../auth/errors";
import { meQuery } from "../auth/session";
import { Button, ErrorAlert, TextField } from "../components/ui";
import { formatDate, todayIso } from "../lib/dates";
import { formatEur, parseEurInput } from "../lib/money";

export const TYPE_LABELS: Record<AccountType, string> = {
  checking: "Checking",
  savings: "Savings",
  brokerage: "Brokerage (PEA, CTO)",
  life_insurance: "Life insurance",
  employee_savings: "Employee savings, retirement",
  crypto: "Crypto",
  loan: "Loan",
  real_estate: "Real estate",
  use_asset: "Vehicle, equipment",
  other: "Other",
};

/** Accounts whose balance comes from imported or entered transactions. */
const CASH_TYPES = new Set<AccountType>(["checking", "savings"]);

const accountsKey = (includeClosed: boolean) => ["accounts", { includeClosed }];

export function AccountsPage() {
  const [showClosed, setShowClosed] = useState(false);
  const [editing, setEditing] = useState<AccountOut | "new" | null>(null);
  const accounts = useQuery({
    queryKey: accountsKey(showClosed),
    queryFn: async () =>
      (await listAccounts({ query: { include_closed: showClosed }, throwOnError: true })).data,
  });

  const groups = new Map<string, AccountOut[]>();
  for (const account of accounts.data ?? []) {
    groups.set(account.institution, [...(groups.get(account.institution) ?? []), account]);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-black tracking-tight">Accounts</h1>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={showClosed}
              onChange={(e) => setShowClosed(e.target.checked)}
            />
            Show closed accounts
          </label>
          <Button onClick={() => setEditing("new")}>Add an account</Button>
        </div>
      </div>
      {editing && (
        <AccountForm account={editing === "new" ? null : editing} onDone={() => setEditing(null)} />
      )}
      {accounts.isPending && <p className="text-sm text-muted">Loading…</p>}
      {accounts.isError && <ErrorAlert message="Could not load the accounts." />}
      {accounts.data?.length === 0 && (
        <p className="text-muted">
          No accounts yet. Add your bank accounts, then import their statements.
        </p>
      )}
      {[...groups].map(([institution, list]) => (
        <section key={institution}>
          <h2 className="mb-2 text-lg font-bold">{institution}</h2>
          <ul
            aria-label={institution}
            className="divide-y divide-border rounded-lg border border-border bg-surface"
          >
            {list.map((account) => (
              <AccountRow key={account.id} account={account} onEdit={() => setEditing(account)} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function AccountRow({ account, onEdit }: { account: AccountOut; onEdit: () => void }) {
  const { data: user } = useSuspenseQuery(meQuery);
  const queryClient = useQueryClient();
  const setClosed = useMutation({
    mutationFn: async (closedOn: string | null) =>
      updateAccount({
        path: { account_id: account.id },
        body: { closed_on: closedOn },
        throwOnError: true,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["accounts"] }),
  });

  return (
    <li className="flex flex-wrap items-center justify-between gap-4 px-4 py-3">
      <div>
        <p className="font-medium">
          <Link
            to="/transactions"
            search={{ account: account.id }}
            className="hover:text-accent hover:underline"
          >
            {account.name}
          </Link>
          {account.closed_on && (
            <span className="ml-2 text-sm text-muted">Closed {formatDate(account.closed_on)}</span>
          )}
        </p>
        <p className="text-sm text-muted">
          {TYPE_LABELS[account.type]} · {account.visibility === "shared" ? "Shared" : "Private"}
          {account.owner_id !== user.id && ` · ${account.owner_name}`}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <div className="text-right">
          <p className="tabular font-medium">{formatEur(account.balance)}</p>
          <p className="text-xs text-muted">
            opening {formatEur(account.opening_balance)} on {formatDate(account.opening_date)}
          </p>
        </div>
        {CASH_TYPES.has(account.type) && !account.closed_on && (
          <Link
            to="/accounts/$accountId/import"
            params={{ accountId: account.id }}
            aria-label={`Import into ${account.name}`}
            className="rounded-md border border-border bg-surface px-3 py-2 text-sm hover:border-accent"
          >
            Import
          </Link>
        )}
        <Button variant="ghost" aria-label={`Edit ${account.name}`} onClick={onEdit}>
          Edit
        </Button>
        <Button
          variant="ghost"
          aria-label={`${account.closed_on ? "Reopen" : "Close"} ${account.name}`}
          disabled={setClosed.isPending}
          onClick={() => setClosed.mutate(account.closed_on ? null : todayIso())}
        >
          {account.closed_on ? "Reopen" : "Close"}
        </Button>
      </div>
    </li>
  );
}

function AccountForm({ account, onDone }: { account: AccountOut | null; onDone: () => void }) {
  const { data: user } = useSuspenseQuery(meQuery);
  const queryClient = useQueryClient();
  const institutions = useQuery({
    queryKey: ["institutions"],
    queryFn: async () => (await listInstitutions({ throwOnError: true })).data,
  });
  const [name, setName] = useState(account?.name ?? "");
  const [institution, setInstitution] = useState(account?.institution ?? "");
  const [type, setType] = useState<AccountType>(account?.type ?? "checking");
  const [visibility, setVisibility] = useState<Visibility>(account?.visibility ?? "private");
  const [balance, setBalance] = useState(account ? account.opening_balance.replace(".", ",") : "0");
  const [openedOn, setOpenedOn] = useState(account?.opening_date ?? todayIso());
  const [invalidAmount, setInvalidAmount] = useState(false);
  const institutionsId = useId();
  const visibilityId = useId();
  const typeId = useId();
  const ownedByMe = !account || account.owner_id === user.id;

  const save = useMutation({
    mutationFn: async (opening_balance: string) => {
      const fields = {
        name,
        institution_name: institution,
        type,
        opening_balance,
        opening_date: openedOn,
      };
      const { data, error, response } = account
        ? await updateAccount({
            path: { account_id: account.id },
            body: ownedByMe ? { ...fields, visibility } : fields,
          })
        : await createAccount({ body: { ...fields, visibility } });
      if (!data) {
        throw new Error(
          response?.status === 409 || response?.status === 422
            ? (detailSentence(error) ?? "Check the form.")
            : apiErrorMessage(response),
        );
      }
      return data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["accounts"] });
      await queryClient.invalidateQueries({ queryKey: ["institutions"] });
      onDone();
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const amount = parseEurInput(balance);
    setInvalidAmount(amount === null);
    if (amount !== null) save.mutate(amount);
  };

  const selectClass = "rounded-md border border-border bg-surface px-3 py-2 disabled:opacity-60";

  return (
    <form
      onSubmit={submit}
      className="grid gap-4 rounded-lg border border-accent bg-surface p-4 sm:grid-cols-2"
    >
      <h2 className="text-lg font-bold sm:col-span-2">
        {account ? `Edit ${account.name}` : "New account"}
      </h2>
      <TextField
        label="Account name"
        required
        maxLength={100}
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <TextField
        label="Institution"
        required
        maxLength={100}
        list={institutionsId}
        value={institution}
        onChange={(e) => setInstitution(e.target.value)}
      />
      <datalist id={institutionsId}>
        {institutions.data?.map((n) => (
          <option key={n} value={n} />
        ))}
      </datalist>
      <div className="flex flex-col gap-1">
        <label htmlFor={typeId} className="text-sm font-medium">
          Type
        </label>
        <select
          id={typeId}
          className={selectClass}
          value={type}
          onChange={(e) => setType(e.target.value as AccountType)}
        >
          {Object.entries(TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={visibilityId} className="text-sm font-medium">
          Visible to
        </label>
        <select
          id={visibilityId}
          className={selectClass}
          value={visibility}
          disabled={!ownedByMe}
          onChange={(e) => setVisibility(e.target.value as Visibility)}
        >
          <option value="private">Only me</option>
          <option value="shared">Every household member</option>
        </select>
        {!ownedByMe && account && (
          <p className="text-xs text-muted">Only {account.owner_name} can change this.</p>
        )}
      </div>
      <TextField
        label="Opening balance (€)"
        inputMode="decimal"
        required
        className="tabular"
        value={balance}
        onChange={(e) => setBalance(e.target.value)}
      />
      <TextField
        label="Opening date"
        type="date"
        required
        value={openedOn}
        onChange={(e) => setOpenedOn(e.target.value)}
      />
      <p className="text-xs text-muted sm:col-span-2">
        The opening balance is the account balance on the opening date, before the first transaction
        you will import or enter.
      </p>
      <div className="sm:col-span-2">
        <ErrorAlert
          message={
            invalidAmount
              ? "Enter an amount in euros with at most 2 decimals, e.g. 1234,56."
              : (save.error?.message ?? null)
          }
        />
      </div>
      <div className="flex gap-3 sm:col-span-2">
        <Button type="submit" disabled={save.isPending}>
          Save
        </Button>
        <Button variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
