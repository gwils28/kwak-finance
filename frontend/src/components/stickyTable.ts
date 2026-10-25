/**
 * Classes for a large table that keeps its header row and its first column in view: the
 * table scrolls inside its own frame both ways, since a page-level sticky header cannot also
 * scroll sideways. Sticky cells need a background, or the rows would show through. The frame is
 * positioned so that absolute descendants (the `sr-only` texts) are clipped by it: otherwise they
 * stay at their place in the wide table and widen the whole page.
 */
export const SCROLL_FRAME =
  "relative max-h-[75vh] overflow-auto rounded-lg border border-border bg-surface";

/** A column header: stays at the top, under the corner. */
export const STICKY_TOP =
  "sticky top-0 z-20 bg-surface shadow-[inset_0_-1px_0_var(--color-border)]";

/** The top-left header: stays at the top and on the left, above everything. */
export const STICKY_CORNER = `${STICKY_TOP} left-0 z-30`;

/** A row header: stays on the left, under the column headers. */
export const STICKY_LEFT = "sticky left-0 z-10 bg-surface";
