import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useId, useState } from "react";
import {
  applyRules,
  type CategoryOut,
  createRule,
  previewRule,
  type TransactionOut,
} from "../api/generated";
import { apiErrorMessage, detailSentence } from "../auth/errors";
import { Button, ErrorAlert, TextField } from "../components/ui";
import { useI18n } from "../i18n";
import { suggestRuleText } from "../lib/ruleText";
import { CategoryOptions } from "./categories";

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}

/** "Create a rule from this transaction" (F-CAT-3): suggest, preview, create, apply. */
export function RuleForm({
  transaction,
  categories,
  onDone,
}: {
  transaction: TransactionOut;
  categories: CategoryOut[];
  onDone: (message: string) => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [text, setText] = useState(() => suggestRuleText(transaction.label));
  const [categoryId, setCategoryId] = useState(transaction.category_id ?? "");
  const categorySelect = useId();
  const conditions = useDebounced({ text: text.trim(), categoryId }, 300);

  const preview = useQuery({
    queryKey: ["rulePreview", conditions],
    enabled: Boolean(conditions.text && conditions.categoryId),
    queryFn: async () =>
      (
        await previewRule({
          body: { category_id: conditions.categoryId, label_contains: conditions.text },
          throwOnError: true,
        })
      ).data,
  });

  const save = useMutation({
    mutationFn: async () => {
      const created = await createRule({
        body: { category_id: categoryId, label_contains: text.trim() },
      });
      if (!created.data) {
        throw new Error(detailSentence(created.error) ?? apiErrorMessage(t, created.response));
      }
      const applied = await applyRules({ body: { only_uncategorised: true }, throwOnError: true });
      return applied.data.updated;
    },
    onSuccess: async (updated) => {
      await queryClient.invalidateQueries({ queryKey: ["transactions"] });
      await queryClient.invalidateQueries({ queryKey: ["toCategorise"] });
      onDone(t.transactions.ruleCreated(updated));
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };

  return (
    <form
      aria-label={t.transactions.newRule}
      onSubmit={submit}
      className="grid gap-4 rounded-lg border border-accent bg-surface p-4 sm:grid-cols-2"
    >
      <div className="sm:col-span-2">
        <h2 className="text-lg font-bold">{t.transactions.newRule}</h2>
        <p className="text-sm text-muted">{t.transactions.ruleSource(transaction.label)}</p>
      </div>
      <TextField
        label={t.transactions.labelContains}
        required
        maxLength={100}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="flex flex-col gap-1">
        <label htmlFor={categorySelect} className="text-sm font-medium">
          {t.transactions.category}
        </label>
        <select
          id={categorySelect}
          required
          className="rounded-md border border-border bg-surface px-3 py-2"
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
        >
          <option value="" disabled>
            {t.transactions.chooseCategory}
          </option>
          <CategoryOptions categories={categories} />
        </select>
      </div>
      <p className="text-sm sm:col-span-2" aria-live="polite">
        {preview.data &&
          t.transactions.ruleMatches(preview.data.matching, preview.data.uncategorised)}
      </p>
      <p className="text-xs text-muted sm:col-span-2">{t.transactions.ruleHelp}</p>
      <div className="sm:col-span-2">
        <ErrorAlert message={save.error?.message ?? null} />
      </div>
      <div className="flex gap-3 sm:col-span-2">
        <Button type="submit" disabled={save.isPending || !categoryId || !text.trim()}>
          {t.transactions.createRule}
        </Button>
        <Button variant="ghost" onClick={() => onDone("")}>
          {t.common.cancel}
        </Button>
      </div>
    </form>
  );
}
