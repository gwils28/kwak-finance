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
import { useI18n } from "../i18n";
import { formatDate, todayIso } from "../lib/dates";
import { amountInput, formatEur, parseEurInput } from "../lib/money";

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

  const { t } = useI18n();
  const groups = new Map<string, AccountOut[]>();
  for (const account of accounts.data ?? []) {
    groups.set(account.institution, [...(groups.get(account.institution) ?? []), account]);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-black tracking-tight">{t.accounts.title}</h1>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={showClosed}
              onChange={(e) => setShowClosed(e.target.checked)}
            />
            {t.accounts.showClosed}
          </label>
          <Button onClick={() => setEditing("new")}>{t.accounts.add}</Button>
        </div>
      </div>
      {editing && (
        <AccountForm account={editing === "new" ? null : editing} onDone={() => setEditing(null)} />
      )}
      {accounts.isPending && <p className="text-sm text-muted">{t.common.loading}</p>}
      {accounts.isError && <ErrorAlert message={t.accounts.loadFailed} />}
      {accounts.data?.length === 0 && <p className="text-muted">{t.accounts.empty}</p>}
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
  const { t } = useI18n();
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
            <span className="ml-2 text-sm text-muted">
              {t.accounts.closedOn(formatDate(account.closed_on))}
            </span>
          )}
        </p>
        <p className="text-sm text-muted">
          {t.accounts.types[account.type]} ·{" "}
          {account.visibility === "shared" ? t.accounts.shared : t.accounts.private}
          {account.owner_id !== user.id && ` · ${account.owner_name}`}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <div className="text-right">
          <p className="tabular font-medium">{formatEur(account.balance)}</p>
          <p className="text-xs text-muted">
            {t.accounts.opening(
              formatEur(account.opening_balance),
              formatDate(account.opening_date),
            )}
          </p>
        </div>
        {CASH_TYPES.has(account.type) && !account.closed_on && (
          <Link
            to="/accounts/$accountId/import"
            params={{ accountId: account.id }}
            aria-label={t.accounts.importInto(account.name)}
            className="rounded-md border border-border bg-surface px-3 py-2 text-sm hover:border-accent"
          >
            {t.accounts.import}
          </Link>
        )}
        <Button variant="ghost" aria-label={t.accounts.editNamed(account.name)} onClick={onEdit}>
          {t.common.edit}
        </Button>
        <Button
          variant="ghost"
          aria-label={
            account.closed_on
              ? t.accounts.reopenNamed(account.name)
              : t.accounts.closeNamed(account.name)
          }
          disabled={setClosed.isPending}
          onClick={() => setClosed.mutate(account.closed_on ? null : todayIso())}
        >
          {account.closed_on ? t.accounts.reopen : t.accounts.close}
        </Button>
      </div>
    </li>
  );
}

function AccountForm({ account, onDone }: { account: AccountOut | null; onDone: () => void }) {
  const { data: user } = useSuspenseQuery(meQuery);
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const institutions = useQuery({
    queryKey: ["institutions"],
    queryFn: async () => (await listInstitutions({ throwOnError: true })).data,
  });
  const [name, setName] = useState(account?.name ?? "");
  const [institution, setInstitution] = useState(account?.institution ?? "");
  const [type, setType] = useState<AccountType>(account?.type ?? "checking");
  const [visibility, setVisibility] = useState<Visibility>(account?.visibility ?? "private");
  const [balance, setBalance] = useState(account ? amountInput(account.opening_balance) : "0");
  // No default: "today" would put every operation of the first import before the opening.
  const [openedOn, setOpenedOn] = useState(account?.opening_date ?? "");
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
            ? (detailSentence(error) ?? t.errors.checkForm)
            : apiErrorMessage(t, response),
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
        {account ? t.accounts.editNamed(account.name) : t.accounts.newAccount}
      </h2>
      <TextField
        label={t.accounts.name}
        required
        maxLength={100}
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <TextField
        label={t.accounts.institution}
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
          {t.accounts.type}
        </label>
        <select
          id={typeId}
          className={selectClass}
          value={type}
          onChange={(e) => setType(e.target.value as AccountType)}
        >
          {Object.entries(t.accounts.types).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={visibilityId} className="text-sm font-medium">
          {t.accounts.visibleTo}
        </label>
        <select
          id={visibilityId}
          className={selectClass}
          value={visibility}
          disabled={!ownedByMe}
          onChange={(e) => setVisibility(e.target.value as Visibility)}
        >
          <option value="private">{t.accounts.onlyMe}</option>
          <option value="shared">{t.accounts.everyone}</option>
        </select>
        {!ownedByMe && account && (
          <p className="text-xs text-muted">{t.accounts.onlyOwnerChanges(account.owner_name)}</p>
        )}
      </div>
      <TextField
        label={t.accounts.openingBalance}
        inputMode="decimal"
        required
        className="tabular"
        value={balance}
        onChange={(e) => setBalance(e.target.value)}
      />
      <TextField
        label={t.accounts.openingDate}
        type="date"
        required
        value={openedOn}
        onChange={(e) => setOpenedOn(e.target.value)}
      />
      <p className="text-xs text-muted sm:col-span-2">{t.accounts.openingHelp}</p>
      <div className="sm:col-span-2">
        <ErrorAlert
          message={invalidAmount ? t.accounts.invalidAmount : (save.error?.message ?? null)}
        />
      </div>
      <div className="flex gap-3 sm:col-span-2">
        <Button type="submit" disabled={save.isPending}>
          {t.common.save}
        </Button>
        <Button variant="ghost" onClick={onDone}>
          {t.common.cancel}
        </Button>
      </div>
    </form>
  );
}
