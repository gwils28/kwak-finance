import type { Language } from "../api/generated";
import { MESSAGES } from "../i18n";
import type { AuditDoc, Block } from "./document";

/** The document as it prints (F-AUD-7): title, frame, contents, sections, closing statement. */
export function AuditDocumentView({ doc, language }: { doc: AuditDoc; language: Language }) {
  const t = MESSAGES[language].audit.doc;
  return (
    <article
      lang={language}
      className="rounded-lg border border-border bg-surface p-6 text-sm leading-relaxed print:border-0 print:p-0"
    >
      {doc.prompt && (
        <section className="print-whole mb-6 rounded-md border border-border p-4">
          <h2 className="mb-2 text-base font-bold">{t.promptTitle}</h2>
          <ul className="list-disc space-y-1 pl-5">
            {doc.prompt.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>
      )}
      <header className="mb-6 border-b border-border pb-4">
        <h1 className="text-2xl font-black tracking-tight">{doc.title}</h1>
        <p className="mt-1 text-lg font-semibold">{doc.household}</p>
        <dl className="mt-3 grid gap-x-4 gap-y-1 sm:grid-cols-[auto_1fr]">
          {doc.meta.map(([k, v]) => (
            <div key={`${k}${v}`} className="contents">
              <dt className="text-muted">{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      </header>
      <nav aria-label={t.contents} className="print-whole mb-6">
        <h2 className="mb-2 text-base font-bold">{t.contents}</h2>
        <ol className="list-decimal space-y-0.5 pl-5">
          {doc.sections.map((s) => (
            <li key={s.id}>
              <a href={`#audit-${s.id}`} className="hover:text-accent">
                {s.title}
              </a>
            </li>
          ))}
        </ol>
      </nav>
      {doc.sections.map((s, i) => (
        <section key={s.id} id={`audit-${s.id}`} className="print-whole mb-6">
          <h2 className="mb-2 text-lg font-bold">
            {i + 1}. {s.title}
          </h2>
          <div className="flex flex-col gap-2">
            {s.blocks.map((b, j) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: a static document, never reordered
              <BlockView key={`${s.id}-${j}`} block={b} />
            ))}
          </div>
        </section>
      ))}
      <p className="mt-8 border-t border-border pt-4 text-xs text-muted italic">{doc.closing}</p>
    </article>
  );
}

function BlockView({ block }: { block: Block }) {
  if (block.kind === "p") return <p>{block.text}</p>;
  if (block.kind === "note") return <p className="text-xs text-muted">{block.text}</p>;
  if (block.kind === "list") {
    return (
      <ul className="list-disc space-y-0.5 pl-5">
        {block.items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    );
  }
  const hasHead = block.head.some((h) => h);
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        {hasHead && (
          <thead>
            <tr className="border-b border-border">
              {block.head.map((h, k) => (
                <th
                  // biome-ignore lint/suspicious/noArrayIndexKey: a static document, never reordered
                  key={`${h}-${k}`}
                  scope="col"
                  className={`px-2 py-1 font-semibold ${block.numeric[k] ? "text-right" : "text-left"}`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {block.rows.map((row, r) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: a static document, never reordered
            <tr key={`${row[0]}-${r}`} className="border-b border-border last:border-0">
              {row.map((cell, k) => (
                <td
                  // biome-ignore lint/suspicious/noArrayIndexKey: a static document, never reordered
                  key={`${r}-${k}`}
                  className={`px-2 py-1 ${block.numeric[k] ? "tabular text-right whitespace-nowrap" : ""}`}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
