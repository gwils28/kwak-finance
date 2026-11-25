import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { useI18n } from "../i18n";
import { Icon, type IconName } from "./icons";

/**
 * What a page shows while it has nothing yet: an icon, what is missing, what will appear here,
 * and a link to the guide's section about it.
 */
export function EmptyState({
  icon,
  message,
  hint,
  guide,
  children,
}: {
  icon: IconName;
  message: string;
  hint?: string;
  /** The guide section's id, opened at its anchor. */
  guide: string;
  children?: ReactNode;
}) {
  const { t } = useI18n();
  return (
    <div className="flex items-start gap-4 rounded-lg border border-dashed border-border bg-surface p-5 text-sm">
      <span className="grid size-10 shrink-0 place-items-center rounded-full bg-bg text-muted">
        <Icon name={icon} className="size-5" />
      </span>
      <div className="flex flex-col gap-1.5">
        <p className="font-medium">{message}</p>
        {hint && <p className="text-muted">{hint}</p>}
        {children}
        <Link to="/guide" hash={guide} className="w-fit text-accent hover:underline">
          {t.common.emptyGuide}
        </Link>
      </div>
    </div>
  );
}
