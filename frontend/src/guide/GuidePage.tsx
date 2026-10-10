import { Link } from "@tanstack/react-router";
import { useI18n } from "../i18n";

/** "Using Kwak Finance": a section per feature, each with a link to its page. */
export function GuidePage() {
  const { t } = useI18n();
  const g = t.guide;
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-3xl font-black tracking-tight">{g.title}</h1>
      <p className="mt-3 text-muted">{g.intro}</p>
      <nav aria-label={g.contents} className="mt-6 rounded-lg border border-border bg-surface p-4">
        <p className="mb-2 text-sm font-semibold">{g.contents}</p>
        <ol className="list-inside list-decimal space-y-1 text-sm">
          {g.sections.map((section) => (
            <li key={section.id}>
              <a href={`#${section.id}`} className="hover:text-accent">
                {section.title}
              </a>
            </li>
          ))}
        </ol>
      </nav>
      {g.sections.map((section) => (
        <section
          key={section.id}
          id={section.id}
          aria-labelledby={`${section.id}-title`}
          className="mt-10 scroll-mt-4"
        >
          <h2 id={`${section.id}-title`} className="text-xl font-bold tracking-tight">
            {section.title}
          </h2>
          {section.paragraphs.map((text) => (
            <p key={text} className="mt-3">
              {text}
            </p>
          ))}
          {section.link && (
            <Link
              to={section.link.to}
              className="mt-3 inline-block text-sm font-medium text-accent hover:underline"
            >
              {section.link.label} <span aria-hidden="true">→</span>
            </Link>
          )}
        </section>
      ))}
    </div>
  );
}
