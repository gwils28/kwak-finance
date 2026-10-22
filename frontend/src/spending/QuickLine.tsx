import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { type KeyboardEvent, useId, useState } from "react";
import { type QuickOut, type SpendingCategoryOut, understandQuickLine } from "../api/generated";
import { detailSentence } from "../auth/errors";
import { useI18n } from "../i18n";
import { formatDate } from "../lib/dates";
import { amountInputShort, formatEur } from "../lib/money";
import { type Cell, type Draft, firstMissing, negate } from "./draft";
import { useDebounced } from "./LineRow";
import { labelsQuery, SPENDING } from "./queries";

const understand = (text: string) => ({
  queryKey: [SPENDING, "quick", text],
  queryFn: async () => (await understandQuickLine({ body: { text }, throwOnError: true })).data,
});

/**
 * The quick line (F-ENT-2): a line typed in any order, shown as understood while it is typed.
 * Enter saves it when complete, otherwise hands it to the grid's empty row.
 */
export function QuickLine({
  categories,
  defaultDay,
  onCreate,
  onIncomplete,
}: {
  categories: SpendingCategoryOut[];
  defaultDay: string;
  onCreate: (draft: Draft) => Promise<void>;
  onIncomplete: (draft: Draft, missing: Cell) => void;
}) {
  const { t } = useI18n();
  const q = t.spending.quick;
  const queryClient = useQueryClient();
  const id = useId();
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const typed = useDebounced(text.trim(), 200);
  const understood = useQuery({
    ...understand(typed),
    enabled: typed !== "",
    placeholderData: keepPreviousData,
  });
  const labels = useQuery(labelsQuery(typed));

  const draftOf = (line: QuickOut): Draft => ({
    day: line.day ?? defaultDay,
    label: line.label,
    amount: line.amount ? amountInputShort(negate(line.amount)) : "",
    category: line.category_id ?? "",
    split: null,
  });

  const onKeyDown = async (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      setText("");
      setError(null);
      return;
    }
    if (event.key !== "Enter" || !text.trim() || busy) return;
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const draft = draftOf(await queryClient.fetchQuery(understand(text.trim())));
      const missing = firstMissing(draft);
      if (missing) onIncomplete(draft, missing);
      else await onCreate(draft);
      setText("");
    } catch (exc) {
      setError(detailSentence(exc) ?? t.errors.generic);
    } finally {
      setBusy(false);
    }
  };

  const line = typed && understood.data ? understood.data : null;
  const category = categories.find((c) => c.id === line?.category_id);

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium">
        {q.label}
      </label>
      <input
        id={id}
        value={text}
        maxLength={200}
        list={`${id}-labels`}
        autoComplete="off"
        placeholder={q.placeholder}
        aria-describedby={`${id}-understood ${id}-hint`}
        onChange={(e) => {
          setText(e.target.value);
          setError(null);
        }}
        onKeyDown={(e) => void onKeyDown(e)}
        className="rounded-md border border-border bg-surface px-3 py-2 focus-visible:outline-2 focus-visible:outline-accent"
      />
      <datalist id={`${id}-labels`}>
        {labels.data?.map((s) => (
          <option key={s.label} value={s.label} />
        ))}
      </datalist>
      <p id={`${id}-understood`} aria-live="polite" className="min-h-5 text-sm text-muted">
        {line && (
          <>
            {q.understood}{" "}
            <span className="text-fg">
              {line.day ? formatDate(line.day) : q.defaultDate} · {line.label || "…"} ·{" "}
              {line.amount ? formatEur(negate(line.amount)) : "…"} ·{" "}
              {category?.name ??
                (line.category_word ? q.unknownCategory(line.category_word) : q.noCategory)}
            </span>
          </>
        )}
      </p>
      <p id={`${id}-hint`} className="text-xs text-muted">
        {q.hint}
      </p>
      {error && (
        <p role="alert" className="text-sm text-negative">
          {error}
        </p>
      )}
    </div>
  );
}
