import { Link } from "@tanstack/react-router";
import { useI18n } from "../i18n";

/** Footer of the signed-in pages and the sign-in page. */
export function Footer() {
  const { t } = useI18n();
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-4 text-sm text-muted">
        <span>{t.common.appName}</span>
        <Link to="/run" className="hover:text-accent">
          {t.runGuide.footerLink}
        </Link>
      </div>
    </footer>
  );
}
