import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import {
  createWealthCategory,
  deleteWealthCategory,
  listWealthCategories,
  updateWealthCategory,
  type WealthCategoryOut,
  type WealthKind,
} from "../api/generated";
import { detailSentence } from "../auth/errors";
import { Button, ErrorAlert, TextField } from "../components/ui";
import { useI18n } from "../i18n";
import { WEALTH_COLOURS, wealthColour } from "./colours";

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";
const labelClass = "flex flex-col gap-1 text-sm font-medium";

/** Rename, recolour, reorder, add and delete the wealth categories (F-WLT-1). */
export function ManageCategories({ onDone }: { onDone: () => void }) {
  const { t } = useI18n();
  const ids = { title: useId() };
  const queryClient = useQueryClient();
  const categories = useQuery({
    queryKey: ["wealth", "categories"],
    queryFn: async () => (await listWealthCategories({ throwOnError: true })).data,
  });
  const change = useMutation({
    mutationFn: async (call: () => Promise<{ error?: unknown; response?: Response }>) => {
      const { error, response } = await call();
      if (response?.ok) return;
      // The server says why it refused: a name taken, a category still holding lines.
      const told = response && [409, 422].includes(response.status);
      throw new Error((told && detailSentence(error)) || t.wealth.saveFailed);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["wealth"] }),
  });
  const rows = categories.data ?? [];

  return (
    <section
      aria-labelledby={ids.title}
      className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id={ids.title} className="text-lg font-bold">
            {t.wealth.categoriesTitle}
          </h2>
          <p className="max-w-2xl text-sm text-muted">{t.wealth.categoriesHelp}</p>
        </div>
        <Button variant="ghost" onClick={onDone}>
          {t.wealth.done}
        </Button>
      </div>
      <ErrorAlert message={change.error?.message ?? null} />
      <ul className="flex flex-col divide-y divide-border">
        {rows.map((category, index) => (
          <CategoryRow
            // Remounted when the server's values change, so the fields show them again.
            key={`${category.id}-${category.name}-${category.colour}`}
            category={category}
            first={index === 0}
            last={index === rows.length - 1}
            pending={change.isPending}
            onChange={(body) =>
              change.mutate(() =>
                updateWealthCategory({ path: { category_id: category.id }, body }),
              )
            }
            onDelete={() =>
              change.mutate(() => deleteWealthCategory({ path: { category_id: category.id } }))
            }
            onMove={(by) =>
              change.mutate(() =>
                updateWealthCategory({
                  path: { category_id: category.id },
                  body: { position: index + by },
                }),
              )
            }
          />
        ))}
      </ul>
      <NewCategory
        pending={change.isPending}
        onAdd={(body) => change.mutate(() => createWealthCategory({ body }))}
      />
    </section>
  );
}

/** `name`: the accessible name when it says more than the visible "Colour". */
function ColourSelect({
  name,
  value,
  onChange,
}: {
  name?: string;
  value: string;
  onChange: (colour: string) => void;
}) {
  const { t } = useI18n();
  const id = useId();
  return (
    <label htmlFor={id} className={labelClass}>
      {t.wealth.colour}
      <span className="flex items-center gap-2">
        <span
          aria-hidden
          className="inline-block size-4 shrink-0 rounded-sm"
          style={{ background: wealthColour(value) }}
        />
        <select
          id={id}
          aria-label={name}
          className={fieldClass}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        >
          {WEALTH_COLOURS.map((key) => (
            <option key={key} value={key}>
              {t.wealth.colours[key] ?? key}
            </option>
          ))}
        </select>
      </span>
    </label>
  );
}

function CategoryRow({
  category,
  first,
  last,
  pending,
  onChange,
  onDelete,
  onMove,
}: {
  category: WealthCategoryOut;
  first: boolean;
  last: boolean;
  pending: boolean;
  onChange: (body: { name?: string; colour?: string }) => void;
  onDelete: () => void;
  onMove: (by: -1 | 1) => void;
}) {
  const { t } = useI18n();
  const [name, setName] = useState(category.name);
  const [colour, setColour] = useState(category.colour);
  const body = {
    ...(name.trim() !== category.name && { name: name.trim() }),
    ...(colour !== category.colour && { colour }),
  };
  const changed = Object.keys(body).length > 0 && name.trim() !== "";
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (changed) onChange(body);
  };
  return (
    <li className="py-3">
      <form onSubmit={submit} aria-label={category.name} className="flex flex-wrap items-end gap-3">
        <TextField
          label={t.wealth.name}
          aria-label={t.wealth.nameOf(category.name)}
          required
          maxLength={60}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <ColourSelect name={t.wealth.colourOf(category.name)} value={colour} onChange={setColour} />
        <span className="pb-2 text-sm text-muted">{t.wealth.kinds[category.kind]}</span>
        <div className="flex flex-wrap gap-2">
          <Button
            type="submit"
            disabled={pending || !changed}
            aria-label={t.wealth.saveCategory(category.name)}
          >
            {t.common.save}
          </Button>
          <Button
            variant="ghost"
            disabled={pending || first}
            aria-label={t.wealth.moveUp(category.name)}
            onClick={() => onMove(-1)}
          >
            ↑
          </Button>
          <Button
            variant="ghost"
            disabled={pending || last}
            aria-label={t.wealth.moveDown(category.name)}
            onClick={() => onMove(1)}
          >
            ↓
          </Button>
          <Button
            variant="ghost"
            disabled={pending}
            aria-label={t.wealth.deleteCategory(category.name)}
            onClick={onDelete}
          >
            {t.common.delete}
          </Button>
        </div>
      </form>
    </li>
  );
}

function NewCategory({
  pending,
  onAdd,
}: {
  pending: boolean;
  onAdd: (body: { name: string; kind: WealthKind; colour: string }) => void;
}) {
  const { t } = useI18n();
  const ids = { title: useId(), kind: useId() };
  const [name, setName] = useState("");
  const [kind, setKind] = useState<WealthKind>("asset");
  const [colour, setColour] = useState<string>("exotic");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    onAdd({ name: name.trim(), kind, colour });
    setName("");
  };
  return (
    <form
      onSubmit={submit}
      aria-labelledby={ids.title}
      className="flex flex-col gap-3 border-t border-border pt-4"
    >
      <h3 id={ids.title} className="font-bold">
        {t.wealth.newCategory}
      </h3>
      <div className="flex flex-wrap items-end gap-3">
        <TextField
          label={t.wealth.name}
          required
          maxLength={60}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <label htmlFor={ids.kind} className={labelClass}>
          {t.wealth.kind}
          <select
            id={ids.kind}
            className={fieldClass}
            value={kind}
            onChange={(e) => setKind(e.target.value as WealthKind)}
          >
            <option value="asset">{t.wealth.kinds.asset}</option>
            <option value="debt">{t.wealth.kinds.debt}</option>
          </select>
        </label>
        <ColourSelect value={colour} onChange={setColour} />
        <Button type="submit" disabled={pending || !name.trim()}>
          {t.wealth.add}
        </Button>
      </div>
    </form>
  );
}
