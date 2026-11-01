/**
 * The analysis pages' pieces (spec §7): the answer first in tiles, a status as a chip with its
 * icon and word (never its colour alone), links to the sections, and closed folds for what is
 * there to check rather than to read every day.
 */
import type { ReactNode } from "react";

export type Status = "ok" | "watch" | "over";

export const STATUS_ICON: Record<Status, string> = { ok: "✓", watch: "△", over: "▲" };
export const STATUS_COLOUR: Record<Status, string> = {
  ok: "var(--color-progress-ok)",
  watch: "var(--color-progress-watch)",
  over: "var(--color-progress-over)",
};
const CHIP: Record<Status, string> = {
  ok: "border-progress-ok text-fg",
  watch: "border-progress-watch text-fg",
  over: "border-progress-over text-fg",
};

export function Chip({ status, children }: { status: Status; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border-2 px-2 py-0.5 text-xs font-medium ${CHIP[status]}`}
    >
      <span aria-hidden="true" style={{ color: STATUS_COLOUR[status] }}>
        {STATUS_ICON[status]}
      </span>
      {children}
    </span>
  );
}

export function Tiles({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{children}</div>;
}

/** A figure with its label above and the sentence that reads it under. */
export function Tile({
  label,
  value,
  note,
  chips,
  wide = false,
  id,
  children,
}: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  chips?: ReactNode;
  wide?: boolean;
  id?: string;
  children?: ReactNode;
}) {
  return (
    <section
      id={id}
      aria-label={label}
      className={`flex scroll-mt-4 flex-col gap-1.5 rounded-lg border border-border bg-surface p-3 ${
        wide ? "col-span-2" : ""
      }`}
    >
      <p className="text-xs font-medium text-muted">{label}</p>
      <p className="tabular text-2xl font-bold">{value}</p>
      {chips && <div className="flex flex-wrap gap-1">{chips}</div>}
      {children}
      {note && <p className="text-sm text-muted">{note}</p>}
    </section>
  );
}

/** Links to the page's sections, by their ids. */
export function Jump({ label, links }: { label: string; links: [string, string][] }) {
  return (
    <nav aria-label={label} className="flex flex-wrap gap-2 text-sm">
      {links.map(([id, text]) => (
        <a
          key={id}
          href={`#${id}`}
          className="rounded-full border border-border bg-surface px-3 py-1 text-muted hover:text-fg"
        >
          {text}
        </a>
      ))}
    </nav>
  );
}

/** Closed until opened: the method, the back-test, the limits. */
export function Fold({
  title,
  hint,
  id,
  children,
}: {
  title: string;
  hint?: string;
  id?: string;
  children: ReactNode;
}) {
  return (
    <details id={id} className="group scroll-mt-4 rounded-lg border border-border bg-surface">
      <summary className="cursor-pointer list-none px-4 py-3">
        <span aria-hidden="true" className="mr-2 inline-block text-muted group-open:rotate-90">
          ▸
        </span>
        <span className="font-semibold">{title}</span>
        {hint && <span className="text-sm text-muted"> · {hint}</span>}
      </summary>
      <div className="flex flex-col gap-4 border-t border-border p-4">{children}</div>
    </details>
  );
}

/** A warning above the tiles; `info` for a reminder rather than a warning. */
export function Callout({ children, info = false }: { children: ReactNode; info?: boolean }) {
  return (
    <p
      role={info ? "note" : "alert"}
      className={`rounded-lg border-l-4 bg-surface p-3 text-sm ${
        info ? "border-border text-muted" : "border-progress-watch"
      }`}
    >
      {!info && (
        <span aria-hidden="true" className="mr-1 text-warning">
          △
        </span>
      )}
      {children}
    </p>
  );
}

/** A table in words and figures: the first `text` columns words, left-aligned and wrapping;
 * the others figures, right-aligned on one line, except the `worded` ones (a chance, a status,
 * a bias), which wrap so the table fits its card (issue #164). */
export function WordTable({
  label,
  head,
  rows,
  text = 1,
  worded = [],
}: {
  label: string;
  head: string[];
  rows: string[][];
  text?: number;
  worded?: number[];
}) {
  const cell = (i: number) =>
    i < text
      ? "min-w-32 text-left"
      : worded.includes(i)
        ? "min-w-24 pl-3 text-right"
        : "pl-3 text-right whitespace-nowrap tabular";
  return (
    <div className="overflow-x-auto">
      <table aria-label={label} className="w-full text-sm">
        <thead className="text-muted">
          <tr>
            {head.map((h, i) => (
              <th key={h} className={`py-1 align-bottom font-medium ${cell(i)} whitespace-normal`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: a static table, not reordered
            <tr key={r} className="border-t border-border">
              {row.map((v, i) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: columns are positional
                <td key={i} className={`py-1 ${cell(i)}`}>
                  {v}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
