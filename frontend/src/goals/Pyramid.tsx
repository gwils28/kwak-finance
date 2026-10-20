import type { GoalsOut } from "../api/generated";
import { useI18n } from "../i18n";
import { formatEurWhole, formatPercent } from "../lib/money";
import { TIERS, tierColour } from "./shared";

const WIDTH = 360;
const HEIGHT = 286;
const APEX = { x: 120, y: 6 };
const BASE_Y = 234;
const HALF_BASE = 114;
/** The foundation: a slab under the pyramid, a little wider than its base. */
const FOUNDATION = { x: 0, y: 244, width: 240, height: 36 };
const TIERS_ABOVE = TIERS.filter((tier) => tier !== "precaution");

/** The pyramid on its foundation, the emergency fund, each filled to its progress (F-GOAL-7). */
export function Pyramid({ data }: { data: GoalsOut }) {
  const { t } = useI18n();
  const g = t.goals;
  const byTier = new Map(data.pyramid.map((p) => [p.tier, p]));
  const counts = new Map(TIERS.map((tier) => [tier, 0]));
  for (const goal of data.goals) counts.set(goal.tier, (counts.get(goal.tier) ?? 0) + 1);
  const halfAt = (y: number) => (HALF_BASE * (y - APEX.y)) / (BASE_Y - APEX.y);
  const step = (BASE_Y - APEX.y) / TIERS_ABOVE.length;
  const tiers = TIERS_ABOVE.map((tier, i) => {
    const bottom = BASE_Y - i * step;
    const top = bottom - step;
    const progress = Number(byTier.get(tier)?.progress ?? 0);
    return { tier, bottom, top, progress };
  });
  const label = (tier: (typeof TIERS)[number]) => {
    const p = byTier.get(tier);
    return p?.progress == null ? g.noGoalInTier : formatPercent(p.progress);
  };
  return (
    <section
      aria-labelledby="goals-pyramid"
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
    >
      <div>
        <h2 id="goals-pyramid" className="text-lg font-bold">
          {g.pyramid}
        </h2>
        <p className="text-sm text-muted">{g.pyramidCaption}</p>
      </div>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="mx-auto w-full max-w-sm"
        role="img"
        aria-label={TIERS.map((tier) => `${g.tiers[tier]}: ${label(tier)}`).join(", ")}
      >
        {tiers.map(({ tier, bottom, top, progress }) => {
          const points = [
            `${APEX.x - halfAt(bottom)},${bottom}`,
            `${APEX.x + halfAt(bottom)},${bottom}`,
            `${APEX.x + halfAt(top)},${top}`,
            `${APEX.x - halfAt(top)},${top}`,
          ].join(" ");
          const filled = (bottom - top) * Math.min(1, progress);
          return (
            <g key={tier}>
              <clipPath id={`goal-tier-${tier}`}>
                <polygon points={points} />
              </clipPath>
              <polygon points={points} fill="var(--color-budget-on-bg)" />
              <rect
                x={0}
                y={bottom - filled}
                width={APEX.x * 2}
                height={filled}
                fill={tierColour(tier)}
                clipPath={`url(#goal-tier-${tier})`}
              />
              {/* A 2px surface gap between the tiers. */}
              <polygon points={points} fill="none" stroke="var(--color-surface)" strokeWidth={3} />
              <text
                x={APEX.x * 2 + 14}
                y={(bottom + top) / 2 - 4}
                className="fill-fg text-[13px] font-semibold"
              >
                {g.tierShort[tier]}
              </text>
              <text
                x={APEX.x * 2 + 14}
                y={(bottom + top) / 2 + 13}
                className="tabular fill-muted text-[13px]"
              >
                {label(tier)}
              </text>
            </g>
          );
        })}
        <Foundation
          progress={Number(byTier.get("precaution")?.progress ?? 0)}
          name={g.tierShort.precaution}
          label={label("precaution")}
        />
      </svg>
      <ul className="flex flex-col gap-1 text-sm">
        {[...TIERS].reverse().map((tier) => {
          const p = byTier.get(tier);
          return (
            <li key={tier} className="flex flex-wrap justify-between gap-2">
              <span className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="h-3 w-3 rounded-sm"
                  style={{ background: tierColour(tier) }}
                />
                {g.tiers[tier]} · {g.tierGoals(counts.get(tier) ?? 0)}
              </span>
              <span className="tabular">
                {g.ofTarget(formatEurWhole(p?.value ?? "0"), formatEurWhole(p?.target ?? "0"))}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** The emergency fund under the pyramid, filled from the left (F-GOAL-7). */
function Foundation({ progress, name, label }: { progress: number; name: string; label: string }) {
  const { x, y, width, height } = FOUNDATION;
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} rx={4} fill="var(--color-budget-on-bg)" />
      <rect
        x={x}
        y={y}
        width={width * Math.min(1, Math.max(0, progress))}
        height={height}
        rx={4}
        fill={tierColour("precaution")}
      />
      <text
        x={APEX.x * 2 + 14}
        y={y + height / 2 - 4}
        className="fill-fg text-[13px] font-semibold"
      >
        {name}
      </text>
      <text x={APEX.x * 2 + 14} y={y + height / 2 + 13} className="tabular fill-muted text-[13px]">
        {label}
      </text>
    </g>
  );
}
