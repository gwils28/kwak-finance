import { type ReactNode, useEffect, useRef } from "react";

/**
 * Brings a form opened from further down the page into view and focuses its first field.
 * Remount it (with a `key`) to do so again for another row.
 */
export function InView({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // Not returned: scrollIntoView may return a promise, which React would call as a cleanup.
    ref.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    ref.current
      ?.querySelector<HTMLElement>("input:not([type=hidden]), select, textarea")
      ?.focus({ preventScroll: true });
  }, []);
  return (
    <div ref={ref} className="scroll-mt-20">
      {children}
    </div>
  );
}
