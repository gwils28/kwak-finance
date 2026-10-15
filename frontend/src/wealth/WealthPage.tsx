import { useMutation, useQuery, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { type FormEvent, type ReactNode, useId, useState } from "react";
import {
  createWealthLine,
  deleteWealthLine,
  listWealthCategories,
  listWealthLines,
  removeWealthValue,
  setWealthValue,
  updateWealthLine,
  updateWealthMonth,
  type Visibility,
  type WealthCellOut,
  type WealthLineOut,
  type WealthMatrixLineOut,
  type WealthMatrixOut,
  wealthLinesToUpdate,
} from "../api/generated";
import { detailSentence } from "../auth/errors";
import { meQuery } from "../auth/session";
import { InView } from "../components/InView";
import { SCROLL_FRAME, STICKY_CORNER, STICKY_LEFT, STICKY_TOP } from "../components/stickyTable";
import { Button, ErrorAlert, TextField } from "../components/ui";
import { useI18n } from "../i18n";
import { amountInputShort, formatEurWhole, formatPercent, parseEurInput } from "../lib/money";
import { isMonth, monthLabel, thisMonth } from "../lib/months";
import { wealthColour } from "./colours";
import { ManageCategories } from "./ManageCategories";
import { changeText, Summary, useWealthView, ViewControls } from "./WealthView";

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";
const labelClass = "flex flex-col gap-1 text-sm font-medium";
const VISIBILITIES: Visibility[] = ["shared", "private", "joint"];
const KEY = ["wealth"];

type Panel =
  | { kind: "add" }
  | { kind: "update" }
  | { kind: "categories" }
  | { kind: "edit"; lineId: string }
  | {
      kind: "value";
      line: WealthMatrixLineOut;
      month: string;
      cell: WealthCellOut | null;
      debt: boolean;
    };

export function WealthPage() {
  const { t } = useI18n();
  const [panel, setPanel] = useState<Panel | null>(null);
  const view = useWealthView();
  const close = () => setPanel(null);
  const { matrix } = view;
  const data = matrix.data;
  const empty = data?.categories.every((c) => c.lines.length === 0);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight">{t.wealth.title}</h1>
          <p className="max-w-2xl text-sm text-muted">{t.wealth.intro}</p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <ViewControls view={view} />
          <Button variant="ghost" onClick={() => setPanel({ kind: "categories" })}>
            {t.wealth.manageCategories}
          </Button>
          <Button variant="ghost" onClick={() => setPanel({ kind: "add" })}>
            {t.wealth.addLine}
          </Button>
          <Button onClick={() => setPanel({ kind: "update" })}>{t.wealth.updateMonth}</Button>
        </div>
      </div>
      {panel && (
        <div key={JSON.stringify(panel)}>
          {panel.kind === "add" && <AddLine onDone={close} />}
          {panel.kind === "update" && <UpdateMonth onDone={close} />}
          {panel.kind === "categories" && <ManageCategories onDone={close} />}
          {panel.kind === "edit" && <EditLine lineId={panel.lineId} onDone={close} />}
          {panel.kind === "value" && <EditValue {...panel} onDone={close} />}
        </div>
      )}
      {matrix.isError && <ErrorAlert message={t.wealth.loadFailed} />}
      {matrix.isPending && <p className="text-sm text-muted">{t.common.loading}</p>}
      {data && !empty && <Summary matrix={data} />}
      {data && empty && <p className="text-sm">{t.wealth.empty}</p>}
      {data && !empty && <Matrix matrix={data} onOpen={setPanel} />}
    </div>
  );
}

function Matrix({ matrix, onOpen }: { matrix: WealthMatrixOut; onOpen: (panel: Panel) => void }) {
  const { t } = useI18n();
  const { data: user } = useSuspenseQuery(meQuery);
  const num = "whitespace-nowrap px-3 py-2 text-right tabular";
  const months = matrix.months;
  const totals = (label: string, values: (string | null)[], strong = false) => (
    <tr className={strong ? "border-t-2 border-border font-bold" : ""}>
      <th
        scope="row"
        className={`${STICKY_LEFT} whitespace-nowrap px-3 py-2 text-left font-semibold`}
      >
        {label}
      </th>
      {values.map((v, i) => (
        <td key={months[i]} className={num}>
          {v ?? ""}
        </td>
      ))}
      <td className={num} />
    </tr>
  );
  return (
    <div className={SCROLL_FRAME}>
      <table aria-label={t.wealth.matrix} className="w-full text-sm">
        <thead className="text-left text-muted">
          <tr>
            <th scope="col" className={`${STICKY_CORNER} px-3 py-2 font-medium`}>
              {t.wealth.line}
            </th>
            {months.map((m) => (
              <th
                key={m}
                scope="col"
                className={`${STICKY_TOP} whitespace-nowrap px-3 py-2 text-right font-medium`}
              >
                {monthLabel(m)}
              </th>
            ))}
            <th scope="col" className={`${STICKY_TOP} px-3 py-2 text-right font-medium`}>
              {t.wealth.share}
            </th>
          </tr>
        </thead>
        {matrix.categories
          .filter((c) => c.lines.length > 0)
          .map((c) => (
            <tbody key={c.id} className="divide-y divide-border border-t-4 border-border">
              <tr>
                <th
                  scope="row"
                  className={`${STICKY_LEFT} whitespace-nowrap px-3 py-2 text-left font-bold`}
                >
                  <span
                    aria-hidden="true"
                    className="mr-2 inline-block size-3 rounded-sm align-middle"
                    style={{ background: wealthColour(c.colour) }}
                  />
                  {c.name}
                </th>
                {c.subtotals.map((v, i) => (
                  <td key={months[i]} className={`${num} font-semibold`}>
                    {formatEurWhole(v)}
                  </td>
                ))}
                <td className={num}>{c.share === null ? "" : formatPercent(c.share)}</td>
              </tr>
              {c.lines.map((line) => (
                <tr key={line.id}>
                  <th
                    scope="row"
                    className={`${STICKY_LEFT} whitespace-nowrap py-2 pr-3 pl-8 text-left font-normal`}
                    style={{ borderLeft: `4px solid ${wealthColour(c.colour)}` }}
                  >
                    <button
                      type="button"
                      aria-label={t.wealth.editLine(line.name)}
                      className="text-left hover:text-accent hover:underline"
                      onClick={() => onOpen({ kind: "edit", lineId: line.id })}
                    >
                      {line.name}
                    </button>
                    {line.owner_id !== user.id && (
                      <span className="text-xs text-muted">
                        {" "}
                        · {t.wealth.owner(line.owner_name)}
                      </span>
                    )}
                    {line.visibility === "private" && (
                      <span className="text-xs text-muted"> · {t.wealth.onlyYou}</span>
                    )}
                  </th>
                  {line.cells.map((cell, i) => {
                    const month = months[i] as string;
                    const text = cell ? formatEurWhole(cell.amount) : "";
                    const shown = (
                      <span className={cell?.carried ? "text-muted italic" : ""}>
                        {text}
                        {cell?.carried && <span className="sr-only"> ({t.wealth.carried})</span>}
                      </span>
                    );
                    const closed = line.closed_from !== null && month >= line.closed_from;
                    const value = cell
                      ? `${text}${cell.carried ? ` (${t.wealth.carried})` : ""}`
                      : t.wealth.noValue;
                    return (
                      <td key={month} className={num}>
                        {closed ? (
                          shown
                        ) : (
                          <button
                            type="button"
                            aria-label={t.wealth.valueOf(line.name, monthLabel(month), value)}
                            className="min-w-12 rounded px-1 hover:bg-bg focus-visible:outline-2 focus-visible:outline-accent"
                            onClick={() =>
                              onOpen({ kind: "value", line, month, cell, debt: c.kind === "debt" })
                            }
                          >
                            {cell ? shown : "·"}
                          </button>
                        )}
                      </td>
                    );
                  })}
                  <td className={`${num} text-muted`}>
                    {line.share === null ? "" : formatPercent(line.share)}
                  </td>
                </tr>
              ))}
            </tbody>
          ))}
        <tbody className="border-t-4 border-border">
          {totals(t.wealth.gross, matrix.gross.map(formatEurWhole))}
          {totals(t.wealth.debts, matrix.debts.map(formatEurWhole))}
          {totals(t.wealth.netWorth, matrix.net.map(formatEurWhole), true)}
          {totals(
            t.wealth.change,
            matrix.change.map((v, i) =>
              v === null ? null : changeText(v, matrix.change_ratio[i] ?? null),
            ),
          )}
        </tbody>
      </table>
    </div>
  );
}

function useSave<A>(
  call: (arg: A) => Promise<{ error?: unknown; response?: Response }>,
  onDone: () => void,
) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (arg: A) => {
      const { error, response } = await call(arg);
      if (response?.ok) return;
      // The server says why it refused (a closed month, someone else's line…).
      const told = response && [403, 409, 422].includes(response.status);
      throw new Error((told && detailSentence(error)) || t.wealth.saveFailed);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: KEY }),
    onSuccess: onDone,
  });
}

function Frame({
  title,
  onSubmit,
  error,
  pending,
  onCancel,
  children,
  extra,
}: {
  title: string;
  onSubmit: (event: FormEvent) => void;
  error: string | null;
  pending: boolean;
  onCancel: () => void;
  children: ReactNode;
  extra?: ReactNode;
}) {
  const { t } = useI18n();
  return (
    <InView>
      <form
        aria-label={title}
        onSubmit={onSubmit}
        className="flex flex-col gap-4 rounded-lg border border-accent bg-surface p-4"
      >
        <h2 className="text-lg font-bold">{title}</h2>
        {children}
        <ErrorAlert message={error} />
        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={pending}>
            {t.common.save}
          </Button>
          {extra}
          <Button variant="ghost" onClick={onCancel}>
            {t.common.cancel}
          </Button>
        </div>
      </form>
    </InView>
  );
}

function useCategories() {
  return useQuery({
    queryKey: [...KEY, "categories"],
    queryFn: async () => (await listWealthCategories({ throwOnError: true })).data,
  });
}

function CategorySelect({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const { t } = useI18n();
  const id = useId();
  const categories = useCategories();
  return (
    <label htmlFor={id} className={labelClass}>
      {t.wealth.category}
      <select
        id={id}
        className={fieldClass}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="" disabled>
          {t.wealth.category}
        </option>
        {categories.data?.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function VisibilitySelect({
  value,
  onChange,
}: {
  value: Visibility;
  onChange: (v: Visibility) => void;
}) {
  const { t } = useI18n();
  const id = useId();
  return (
    <label htmlFor={id} className={labelClass}>
      {t.wealth.visibility}
      <select
        id={id}
        className={fieldClass}
        value={value}
        onChange={(e) => onChange(e.target.value as Visibility)}
      >
        {VISIBILITIES.map((v) => (
          <option key={v} value={v}>
            {t.wealth.visibilities[v]}
          </option>
        ))}
      </select>
    </label>
  );
}

function AddLine({ onDone }: { onDone: () => void }) {
  const { t } = useI18n();
  const [category, setCategory] = useState("");
  const [name, setName] = useState("");
  const [visibility, setVisibility] = useState<Visibility>("shared");
  const save = useSave(
    () => createWealthLine({ body: { category_id: category, name: name.trim(), visibility } }),
    onDone,
  );
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (category && name.trim()) save.mutate(undefined);
  };
  return (
    <Frame
      title={t.wealth.newLine}
      onSubmit={submit}
      error={save.error?.message ?? null}
      pending={save.isPending}
      onCancel={onDone}
    >
      <div className="flex flex-wrap items-end gap-3">
        <CategorySelect value={category} onChange={setCategory} />
        <TextField
          label={t.wealth.name}
          placeholder={t.wealth.namePlaceholder}
          required
          maxLength={100}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <VisibilitySelect value={visibility} onChange={setVisibility} />
      </div>
    </Frame>
  );
}

function EditLine({ lineId, onDone }: { lineId: string; onDone: () => void }) {
  const lines = useQuery({
    queryKey: [...KEY, "lines"],
    queryFn: async () => (await listWealthLines({ throwOnError: true })).data,
  });
  const { t } = useI18n();
  const line = lines.data?.find((l) => l.id === lineId);
  if (lines.isError) return <ErrorAlert message={t.wealth.loadFailed} />;
  if (!line) return <p className="text-sm text-muted">{t.common.loading}</p>;
  return <EditLineForm line={line} onDone={onDone} />;
}

function EditLineForm({ line, onDone }: { line: WealthLineOut; onDone: () => void }) {
  const { t } = useI18n();
  const { data: user } = useSuspenseQuery(meQuery);
  const closedId = useId();
  const [name, setName] = useState(line.name);
  const [category, setCategory] = useState(line.category_id);
  const [visibility, setVisibility] = useState<Visibility>(line.visibility);
  const [closedFrom, setClosedFrom] = useState(line.closed_from ?? "");
  const isOwner = line.owner_id === user.id;
  const [confirming, setConfirming] = useState(false);
  const save = useSave(
    () =>
      updateWealthLine({
        path: { line_id: line.id },
        body: {
          name: name.trim(),
          category_id: category,
          ...(isOwner ? { visibility } : {}),
          closed_from: isMonth(closedFrom) ? closedFrom : null,
        },
      }),
    onDone,
  );
  const remove = useSave(() => deleteWealthLine({ path: { line_id: line.id } }), onDone);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (name.trim()) save.mutate(undefined);
  };
  return (
    <Frame
      title={t.wealth.editLine(line.name)}
      onSubmit={submit}
      error={save.error?.message ?? remove.error?.message ?? null}
      pending={save.isPending || remove.isPending}
      onCancel={onDone}
      extra={
        isOwner &&
        (confirming ? (
          <Button
            variant="ghost"
            className="border-negative text-negative"
            onClick={() => remove.mutate(undefined)}
          >
            {t.wealth.confirmDelete}
          </Button>
        ) : (
          // Every value goes with the line: a second click confirms.
          <Button variant="ghost" onClick={() => setConfirming(true)}>
            {t.wealth.deleteLine}
          </Button>
        ))
      }
    >
      <div className="flex flex-wrap items-end gap-3">
        <TextField
          label={t.wealth.name}
          required
          maxLength={100}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <CategorySelect value={category} onChange={setCategory} />
        {isOwner && <VisibilitySelect value={visibility} onChange={setVisibility} />}
        <label htmlFor={closedId} className={labelClass}>
          {t.wealth.closedFrom}
          <input
            id={closedId}
            type="month"
            className={fieldClass}
            value={closedFrom}
            max={thisMonth()}
            onChange={(e) => setClosedFrom(e.target.value)}
          />
        </label>
        {closedFrom && (
          <Button variant="ghost" onClick={() => setClosedFrom("")}>
            {t.wealth.reopen}
          </Button>
        )}
      </div>
      <p className="text-xs text-muted">{t.wealth.closedHelp}</p>
      {isOwner && <p className="text-xs text-muted">{t.wealth.deleteHelp}</p>}
    </Frame>
  );
}

function EditValue({
  line,
  month,
  cell,
  debt,
  onDone,
}: {
  line: WealthMatrixLineOut;
  month: string;
  cell: WealthCellOut | null;
  debt: boolean;
  onDone: () => void;
}) {
  const { t } = useI18n();
  const [amount, setAmount] = useState(cell ? amountInputShort(cell.amount) : "");
  const [invalid, setInvalid] = useState(false);
  const path = { line_id: line.id, month };
  const save = useSave(
    (value: string) => setWealthValue({ path, body: { amount: value } }),
    onDone,
  );
  const remove = useSave(() => removeWealthValue({ path }), onDone);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = parseEurInput(amount);
    const bad = value === null || value.startsWith("-");
    setInvalid(bad);
    if (!bad) save.mutate(value);
  };
  return (
    <Frame
      title={t.wealth.valueTitle(line.name, monthLabel(month))}
      onSubmit={submit}
      error={invalid ? t.wealth.saveFailed : (save.error?.message ?? remove.error?.message ?? null)}
      pending={save.isPending || remove.isPending}
      onCancel={onDone}
      extra={
        cell &&
        !cell.carried && (
          <Button variant="ghost" onClick={() => remove.mutate(undefined)}>
            {t.wealth.removeValue}
          </Button>
        )
      }
    >
      <TextField
        label={t.wealth.amount}
        inputMode="decimal"
        className="tabular w-40"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
      />
      {debt && <p className="text-xs text-muted">{t.wealth.amountHelpDebt}</p>}
      {cell && !cell.carried && <p className="text-xs text-muted">{t.wealth.removeHelp}</p>}
    </Frame>
  );
}

function UpdateMonth({ onDone }: { onDone: () => void }) {
  const month = thisMonth();
  const lines = useQuery({
    queryKey: [...KEY, "update", month],
    queryFn: async () => (await wealthLinesToUpdate({ query: { month }, throwOnError: true })).data,
  });
  const { t } = useI18n();
  if (lines.isError) return <ErrorAlert message={t.wealth.loadFailed} />;
  if (!lines.data) return <p className="text-sm text-muted">{t.common.loading}</p>;
  return <UpdateForm month={month} lines={lines.data} onDone={onDone} />;
}

function UpdateForm({
  month,
  lines,
  onDone,
}: {
  month: string;
  lines: { line_id: string; name: string; category_name: string; last_value: string | null }[];
  onDone: () => void;
}) {
  const { t } = useI18n();
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      lines.map((l) => [l.line_id, l.last_value ? amountInputShort(l.last_value) : ""]),
    ),
  );
  const [invalid, setInvalid] = useState(false);
  const save = useSave(
    (body: { month: string; values: { line_id: string; amount: string }[] }) =>
      updateWealthMonth({ body }),
    onDone,
  );
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const filled = lines.filter((l) => (values[l.line_id] ?? "").trim() !== "");
    const parsed = filled.map((l) => ({
      line_id: l.line_id,
      amount: parseEurInput(values[l.line_id] ?? ""),
    }));
    const bad = parsed.some((p) => p.amount === null || p.amount.startsWith("-"));
    setInvalid(bad);
    if (!bad) save.mutate({ month, values: parsed as { line_id: string; amount: string }[] });
  };
  return (
    <Frame
      title={t.wealth.updateTitle(monthLabel(month))}
      onSubmit={submit}
      error={invalid ? t.wealth.saveFailed : (save.error?.message ?? null)}
      pending={save.isPending}
      onCancel={onDone}
    >
      <p className="text-xs text-muted">{t.wealth.updateHelp}</p>
      {lines.length === 0 ? (
        <p className="text-sm">{t.wealth.nothingToUpdate}</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {lines.map((l) => (
            <TextField
              key={l.line_id}
              label={`${l.name} (${l.category_name})`}
              inputMode="decimal"
              className="tabular"
              value={values[l.line_id] ?? ""}
              onChange={(e) => setValues({ ...values, [l.line_id]: e.target.value })}
            />
          ))}
        </div>
      )}
    </Frame>
  );
}
