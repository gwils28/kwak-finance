/**
 * Loading states (UX audit #212): while a page computes, the shape of what is coming (tiles and
 * cards as grey blocks), a sentence saying what is computed and an indeterminate bar; while it
 * recomputes, the last result stays and a slim bar says it is being updated.
 */
import { useI18n } from "../i18n";

/** A grey block standing for content still to come. */
export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-md bg-border motion-reduce:animate-none ${className}`}
    />
  );
}

/** A bar with no end: something is computing, nobody knows for how long. */
function IndeterminateBar({ label }: { label: string }) {
  return (
    <div
      role="progressbar"
      aria-label={label}
      className="relative h-1 w-full overflow-hidden rounded-full bg-border"
    >
      <div className="loading-bar absolute inset-y-0 w-1/3 rounded-full bg-accent" />
    </div>
  );
}

/**
 * The first load of a page: what is computed, why it takes time, a bar, then `tiles` tile
 * shapes (laid out like `Tiles`) and `cards` card shapes.
 */
export function LoadingCards({
  sentence,
  why,
  tiles = 4,
  cards = 2,
}: {
  sentence: string;
  why?: string;
  tiles?: number;
  cards?: number;
}) {
  const { t } = useI18n();
  return (
    <div
      role="status"
      aria-label={t.common.loadingLabel}
      aria-busy="true"
      className="flex flex-col gap-4"
    >
      <div className="flex flex-col gap-2">
        <p className="text-muted">{sentence}</p>
        {why && <p className="text-sm text-muted">{why}</p>}
        <IndeterminateBar label={sentence} />
      </div>
      {tiles > 0 && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Array.from({ length: tiles }, (_, k) => (
            <div
              // biome-ignore lint/suspicious/noArrayIndexKey: identical placeholders, never reordered
              key={k}
              className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-4"
            >
              <Skeleton className="h-3 w-1/2" />
              <Skeleton className="h-7 w-3/4" />
              <Skeleton className="h-3 w-full" />
            </div>
          ))}
        </div>
      )}
      {Array.from({ length: cards }, (_, k) => (
        <div
          // biome-ignore lint/suspicious/noArrayIndexKey: identical placeholders, never reordered
          key={k}
          className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
        >
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-3 w-2/3" />
          <Skeleton className="h-48 w-full" />
        </div>
      ))}
    </div>
  );
}

/** A recomputation: the last result stays below, this slim line says it is being updated. */
export function Refreshing({ sentence }: { sentence: string }) {
  const { t } = useI18n();
  return (
    <div
      role="status"
      aria-label={t.common.updatingLabel}
      className="flex flex-col gap-1 text-sm text-muted"
    >
      <p>{sentence}</p>
      <IndeterminateBar label={sentence} />
    </div>
  );
}
