import { useLayoutEffect, useRef } from "react";

/**
 * A wide month table opens on the current month: its frame scrolls sideways so that the column
 * marked `aria-current="date"` ends at the frame's right edge (the latest months in view, the
 * sticky first column kept). It scrolls once per `key` (null while the data loads), so a refetch
 * does not move the reader back.
 */
export function useScrollToCurrent<T extends HTMLElement>(key: string | null) {
  const ref = useRef<T>(null);
  useLayoutEffect(() => {
    const frame = ref.current;
    if (key === null || !frame) return;
    const cell = frame.querySelector<HTMLElement>('thead [aria-current="date"]');
    if (!cell) return;
    const gap = cell.getBoundingClientRect().right - frame.getBoundingClientRect().right;
    if (gap > 0) frame.scrollLeft += gap;
  }, [key]);
  return ref;
}
