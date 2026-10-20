import type { GoalDetailOut } from "../api/generated";
import { GRID, niceTicks } from "../dashboard/charts";
import { useI18n } from "../i18n";
import { formatEurWhole } from "../lib/money";
import { monthLabel, shiftMonth } from "../lib/months";

const W = 960;
const H = 300;
const PAD = { left: 64, right: 16, top: 16, bottom: 32 };
const ACCENT = "var(--color-chart-accent)";
const CONTEXT = "var(--color-chart-context)";

const index = (month: string) => {
  const [y, m] = month.split("-").map(Number) as [number, number];
  return y * 12 + m - 1;
};

/**
 * A goal's values month by month, the straight line it should follow to its target, and where
 * its actual pace leads (F-GOAL-7). The month-by-month table below reads every value.
 */
export function Trajectory({ detail }: { detail: GoalDetailOut }) {
  const { t } = useI18n();
  const g = t.goals;
  const { goal, months } = detail;
  const first = months[0];
  const last = months.at(-1);
  if (!first || !last) return null;
  const target = Number(goal.target);
  const ends = [last.month, goal.deadline, goal.estimated].filter((m): m is string => !!m);
  const end = ends.reduce((a, b) => (index(b) > index(a) ? b : a));
  const span = Math.max(1, index(end) - index(first.month));
  const ticks = niceTicks(Math.max(target, ...months.map((m) => Number(m.value))) * 1.05);
  const top = ticks.at(-1) ?? target;
  const x = (month: string) =>
    PAD.left + ((W - PAD.left - PAD.right) * (index(month) - index(first.month))) / span;
  const y = (value: number) => PAD.top + (H - PAD.top - PAD.bottom) * (1 - value / top);
  const every = Math.max(1, Math.ceil(span / 6));
  const labels = Array.from({ length: Math.floor(span / every) + 1 }, (_, i) =>
    shiftMonth(first.month, i * every),
  );
  const path = months.map((m) => `${x(m.month)},${y(Number(m.value))}`).join(" ");

  return (
    <figure className="flex flex-col gap-2">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label={g.trajectoryLabel(goal.name)}
      >
        {ticks.map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} stroke={GRID} />
            <text
              x={PAD.left - 8}
              y={y(v) + 4}
              textAnchor="end"
              className="tabular fill-muted text-[11px]"
            >
              {formatEurWhole(String(v))}
            </text>
          </g>
        ))}
        {labels.map((m) => (
          <text
            key={m}
            x={x(m)}
            y={H - 10}
            // Kept inside the frame at both ends.
            textAnchor={
              x(m) < PAD.left + 40 ? "start" : x(m) > W - PAD.right - 40 ? "end" : "middle"
            }
            className="fill-muted text-[11px]"
          >
            {monthLabel(m)}
          </text>
        ))}
        <line
          x1={PAD.left}
          x2={W - PAD.right}
          y1={y(target)}
          y2={y(target)}
          stroke="var(--color-fg)"
          strokeWidth={1}
        />
        <text x={W - PAD.right} y={y(target) - 6} textAnchor="end" className="fill-fg text-[12px]">
          {g.legendTarget} {formatEurWhole(goal.target)}
        </text>
        {goal.deadline && first.expected !== null && (
          <line
            x1={x(first.month)}
            y1={y(Number(first.expected))}
            x2={x(goal.deadline)}
            y2={y(target)}
            stroke={CONTEXT}
            strokeWidth={2}
            strokeDasharray="2 4"
          />
        )}
        {goal.estimated && goal.status !== "reached" && (
          <line
            x1={x(last.month)}
            y1={y(Number(last.value))}
            x2={x(goal.estimated)}
            y2={y(target)}
            stroke={ACCENT}
            strokeWidth={2}
            strokeDasharray="7 5"
          />
        )}
        <polyline
          points={path}
          fill="none"
          stroke={ACCENT}
          strokeWidth={2}
          strokeLinejoin="round"
        />
        {months.map((m) => (
          <circle
            key={m.month}
            cx={x(m.month)}
            cy={y(Number(m.value))}
            r={4}
            fill={ACCENT}
            stroke="var(--color-surface)"
            strokeWidth={2}
          >
            <title>{`${monthLabel(m.month)}: ${formatEurWhole(m.value)}`}</title>
          </circle>
        ))}
      </svg>
      <figcaption className="flex flex-wrap gap-4 text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="w-5 border-t-2" style={{ borderColor: ACCENT }} />
          {g.legendValue}
        </span>
        {goal.deadline && (
          <span className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="w-5 border-t-2 border-dotted"
              style={{ borderColor: CONTEXT }}
            />
            {g.legendExpected}
          </span>
        )}
        {goal.estimated && goal.status !== "reached" && (
          <span className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="w-5 border-t-2 border-dashed"
              style={{ borderColor: ACCENT }}
            />
            {g.legendProjection}
          </span>
        )}
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="w-5 border-t border-fg" />
          {g.legendTarget}
        </span>
      </figcaption>
    </figure>
  );
}
