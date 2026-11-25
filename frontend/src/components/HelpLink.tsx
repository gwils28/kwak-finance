import { Link } from "@tanstack/react-router";
import { useI18n } from "../i18n";
import type { GuideSectionId } from "../i18n/guide";
import { Icon } from "./icons";

/** The "?" next to a page's title: opens the guide at the section about that page. */
export function HelpLink({ section }: { section: GuideSectionId }) {
  const { t } = useI18n();
  const title = t.guide.sections.find((s) => s.id === section)?.title ?? t.guide.title;
  const label = t.guide.help(title);
  return (
    <Link
      to="/guide"
      hash={section}
      aria-label={label}
      title={label}
      className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-muted hover:bg-surface hover:text-accent focus-visible:text-accent"
    >
      <Icon name="help" className="h-5 w-5" />
    </Link>
  );
}
