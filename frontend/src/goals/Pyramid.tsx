import { useId } from "react";
import type { GoalsOut, Tier } from "../api/generated";
import { useI18n } from "../i18n";
import { formatEurWhole, formatPercent } from "../lib/money";
import { PYRAMID, TIERS, tierColour } from "./shared";

/**
 * The pyramid (F-GOAL-7) as a stone monument: three tiers of block courses on a Roman column,
 * the emergency fund, under a gilded capstone, the pleasure goals (F-GOAL-10), bare stone with
 * a padlock while locked. Each tier fills from the bottom to its progress, the column from its
 * foot. Colours are tokens (§7): the tiers', the foundation's, the capstone's `goal-gold*` and
 * the `goal-stone*` greys; light and shade are the palette's lightest and darkest greys at low
 * opacity.
 */

const WIDTH = 500;
const HEIGHT = 480;
const LABEL_X = 338;
const LIGHT = "var(--color-neutral-50)";
const DARK = "var(--color-neutral-900)";
const STONE = "var(--color-goal-stone)";
const STONE_TOP = "var(--color-goal-stone-top)";
const EDGE = "var(--color-goal-stone-edge)";

// The pyramid: an apex, a base standing on the column's abacus, and a ridge set off to the
// right so the left face catches the light and the right one stays in shade.
const AX = 170;
const AY = 14;
const BY = 224;
const HALF_BASE = 124;
const RIDGE = 28;
const SPAN = BY - AY;
const COURSES = 4;
const BRICK = 16;
/** The capstone: the pyramidion from the apex down to the top course of the short term. */
const CAP_BOTTOM = AY + 46;
const TIERS_ABOVE = PYRAMID.filter((tier) => tier !== "precaution" && tier !== "pleasure");

const half = (y: number) => (HALF_BASE * (y - AY)) / SPAN;
const ridge = (y: number) => AX + (RIDGE * (y - AY)) / SPAN;
const pt = (x: number, y: number) => `${x.toFixed(1)},${y.toFixed(1)}`;
const clamp = (p: number) => Math.max(0, Math.min(1, p));

/** A block's own shade, the same on every render: stone is never quite even. */
function grain(a: number, b: number): { tint: string; alpha: number } {
  const s = Math.sin(a * 12.9898 + b * 78.233) * 43758.5453;
  const n = s - Math.floor(s);
  return { tint: n > 0.5 ? LIGHT : DARK, alpha: Math.abs(n - 0.5) * 0.16 };
}

type Block = { x: number; y: number; w: number; h: number; tint: string; alpha: number };

function tierShape(index: number) {
  const step = (BY - CAP_BOTTOM) / TIERS_ABOVE.length;
  const bottom = BY - index * step;
  const top = bottom - step;
  const rowH = step / COURSES;
  const left: Block[] = [];
  const right: Block[] = [];
  const joints: number[] = [];
  for (let r = 0; r < COURSES; r++) {
    const yb = bottom - r * rowH;
    const row = index * COURSES + r;
    if (r > 0) joints.push(yb);
    // Rows staggered by half a block; the right face's blocks narrower, in perspective.
    const offset = (row % 2) * (BRICK / 2);
    for (let k = 0, x = AX - half(yb) - offset; x < ridge(yb); k++, x += BRICK) {
      left.push({ x, y: yb - rowH, w: BRICK, h: rowH, ...grain(row, k) });
    }
    for (let k = 0, x = ridge(yb) - offset / 2; x < AX + half(yb); k++, x += BRICK / 2) {
      right.push({ x, y: yb - rowH, w: BRICK / 2, h: rowH, ...grain(row + 40, k) });
    }
  }
  return {
    bottom,
    top,
    left: [
      pt(AX - half(bottom), bottom),
      pt(ridge(bottom), bottom),
      pt(ridge(top), top),
      pt(AX - half(top), top),
    ].join(" "),
    right: [
      pt(ridge(bottom), bottom),
      pt(AX + half(bottom), bottom),
      pt(AX + half(top), top),
      pt(ridge(top), top),
    ].join(" "),
    outline: [
      pt(AX - half(bottom), bottom),
      pt(AX + half(bottom), bottom),
      pt(AX + half(top), top),
      pt(AX - half(top), top),
    ].join(" "),
    leftBlocks: left,
    rightBlocks: right,
    joints,
  };
}

const SHAPES = TIERS_ABOVE.map((_, i) => tierShape(i));

const CAPSTONE = {
  left: [pt(AX - half(CAP_BOTTOM), CAP_BOTTOM), pt(ridge(CAP_BOTTOM), CAP_BOTTOM), pt(AX, AY)].join(
    " ",
  ),
  right: [
    pt(ridge(CAP_BOTTOM), CAP_BOTTOM),
    pt(AX + half(CAP_BOTTOM), CAP_BOTTOM),
    pt(AX, AY),
  ].join(" "),
};

// The column, from the abacus the pyramid stands on down to its plinth.
const ABACUS = { x: AX - 138, y: BY + 8, w: 276, h: 14, depth: 8 };
const ECHINUS = { x: AX - 118, y: ABACUS.y + ABACUS.h, w: 236, h: 17 };
const BELL_BOTTOM = ECHINUS.y + 56;
const SHAFT_TOP_HALF = 88;
const SHAFT_BOTTOM_HALF = 94;
const NECK_H = 10;
const SHAFT_TOP = BELL_BOTTOM + NECK_H;
const SHAFT_BOTTOM = SHAFT_TOP + 92;
const PLINTH = { x: AX - 134, y: SHAFT_BOTTOM + 36, w: 268, h: 24, depth: 8 };
const COLUMN_TOP = ABACUS.y - ABACUS.depth;
const COLUMN_BOTTOM = PLINTH.y + PLINTH.h;

const column = (() => {
  const cx = AX;
  const abacusTop = [
    pt(ABACUS.x, ABACUS.y),
    pt(ABACUS.x + ABACUS.w, ABACUS.y),
    pt(ABACUS.x + ABACUS.w - 10, ABACUS.y - ABACUS.depth),
    pt(ABACUS.x + 10, ABACUS.y - ABACUS.depth),
  ].join(" ");
  const plinthTop = [
    pt(PLINTH.x + 10, PLINTH.y - PLINTH.depth),
    pt(PLINTH.x + PLINTH.w - 10, PLINTH.y - PLINTH.depth),
    pt(PLINTH.x + PLINTH.w, PLINTH.y),
    pt(PLINTH.x, PLINTH.y),
  ].join(" ");
  const bell = `M ${cx - 114} ${ECHINUS.y + 6} C ${cx - 110} ${BELL_BOTTOM - 18}, ${cx - SHAFT_TOP_HALF - 8} ${BELL_BOTTOM - 6}, ${cx - SHAFT_TOP_HALF - 4} ${BELL_BOTTOM} L ${cx + SHAFT_TOP_HALF + 4} ${BELL_BOTTOM} C ${cx + SHAFT_TOP_HALF + 8} ${BELL_BOTTOM - 6}, ${cx + 110} ${BELL_BOTTOM - 18}, ${cx + 114} ${ECHINUS.y + 6} Z`;
  const shaft = `M ${cx - SHAFT_TOP_HALF} ${SHAFT_TOP} L ${cx + SHAFT_TOP_HALF} ${SHAFT_TOP} L ${cx + SHAFT_BOTTOM_HALF} ${SHAFT_BOTTOM} L ${cx - SHAFT_BOTTOM_HALF} ${SHAFT_BOTTOM} Z`;
  // Acanthus: pointed leaves, veined, their tips curling out under the echinus.
  const count = 11;
  const leaves = Array.from({ length: count }, (_, k) => {
    const u = (k + 0.5) / count;
    const bx = cx - SHAFT_TOP_HALF - 2 + u * (SHAFT_TOP_HALF * 2 + 4);
    const lean = (u - 0.5) * 40;
    const tipX = bx + lean;
    const tipY = ECHINUS.y + ECHINUS.h - 2;
    const w = 11;
    let veins = "";
    for (let j = 1; j <= 4; j++) {
      const f = j / 5;
      const vx = bx + (tipX - bx) * f * 0.8;
      const vy = BELL_BOTTOM + (tipY - BELL_BOTTOM) * f;
      veins += `M ${vx} ${vy} l -6 -5 M ${vx} ${vy} l 6 -5 `;
    }
    return {
      d: `M ${bx - w} ${BELL_BOTTOM} C ${bx - w - 2} ${BELL_BOTTOM - 24}, ${tipX - 10} ${tipY + 14}, ${tipX} ${tipY} C ${tipX + 10} ${tipY + 14}, ${bx + w + 2} ${BELL_BOTTOM - 24}, ${bx + w} ${BELL_BOTTOM} Z`,
      rib: `M ${bx} ${BELL_BOTTOM} Q ${bx + lean * 0.4} ${(BELL_BOTTOM + tipY) / 2} ${tipX} ${tipY + 3}`,
      veins,
      shaded: k % 2 === 1,
    };
  });
  const volute = (vx: number, dir: 1 | -1) => {
    const vy = ECHINUS.y + ECHINUS.h / 2 + 4;
    let d = "";
    for (let a = 0; a <= Math.PI * 5; a += 0.25) {
      const r = 13.5 - (a / (Math.PI * 5)) * 12;
      d += `${a === 0 ? "M" : "L"} ${(vx + dir * r * Math.cos(a)).toFixed(1)} ${(vy + r * Math.sin(a)).toFixed(1)} `;
    }
    return { cx: vx, cy: vy, r: 15, spiral: d };
  };
  // Flutes closer together towards the edges, as on a cylinder.
  const flutes = Array.from({ length: 11 }, (_, i) => {
    const theta = -Math.PI / 2 + (Math.PI * (i + 1)) / 12;
    const w = Math.max(1, 6 * Math.cos(theta));
    const x = cx + SHAFT_TOP_HALF * 0.98 * Math.sin(theta);
    return { x, highlight: x + w / 2 + 1, w };
  });
  const rings = [
    {
      x: cx - SHAFT_TOP_HALF - 6,
      y: BELL_BOTTOM,
      w: (SHAFT_TOP_HALF + 6) * 2,
      h: NECK_H,
      rx: 5,
      top: true,
    },
    {
      x: cx - SHAFT_BOTTOM_HALF - 8,
      y: SHAFT_BOTTOM,
      w: (SHAFT_BOTTOM_HALF + 8) * 2,
      h: 10,
      rx: 5,
      top: true,
    },
    {
      x: cx - SHAFT_BOTTOM_HALF - 4,
      y: SHAFT_BOTTOM + 10,
      w: (SHAFT_BOTTOM_HALF + 4) * 2,
      h: 5,
      rx: 2,
      top: false,
    },
    {
      x: cx - SHAFT_BOTTOM_HALF - 16,
      y: SHAFT_BOTTOM + 15,
      w: (SHAFT_BOTTOM_HALF + 16) * 2,
      h: 13,
      rx: 6.5,
      top: true,
    },
  ];
  return {
    abacusTop,
    plinthTop,
    bell,
    shaft,
    leaves,
    volutes: [volute(ECHINUS.x + 4, 1), volute(ECHINUS.x + ECHINUS.w - 4, -1)],
    flutes,
    rings,
  };
})();

/** The pyramid on its column, the emergency fund, each filled to its progress (F-GOAL-7). */
export function Pyramid({ data }: { data: GoalsOut }) {
  const { t } = useI18n();
  const g = t.goals;
  // Clip ids must be unique on the page.
  const uid = useId().replace(/:/g, "");
  const id = (name: string) => `${uid}-${name}`;
  const byTier = new Map(data.pyramid.map((p) => [p.tier, p]));
  const counts = new Map(TIERS.map((tier) => [tier, 0]));
  for (const goal of data.goals) counts.set(goal.tier, (counts.get(goal.tier) ?? 0) + 1);
  const progress = (tier: Tier) => clamp(Number(byTier.get(tier)?.progress ?? 0));
  const label = (tier: Tier) => {
    const p = byTier.get(tier);
    return p?.progress == null ? g.noGoalInTier : formatPercent(p.progress);
  };
  const locked = !data.capstone.unlocked;
  const fundLevel = COLUMN_BOTTOM - (COLUMN_BOTTOM - COLUMN_TOP) * progress("precaution");
  const capFilled = locked ? 0 : (CAP_BOTTOM - AY) * progress("pleasure");
  const capLabel = () => {
    const value = label("pleasure");
    return locked && byTier.get("pleasure")?.progress != null
      ? `${g.status.locked} · ${value}`
      : value;
  };
  const gate = data.capstone;
  const missing = [
    ...(gate.precaution === null
      ? [g.gateNoPrecaution]
      : Number(gate.precaution) < 1
        ? [g.gatePrecaution(formatPercent(gate.precaution))]
        : []),
    ...(gate.ahead < gate.needed ? [g.gateAhead(gate.ahead, gate.counted, gate.needed)] : []),
  ];
  const shaftMid = (SHAFT_TOP + SHAFT_BOTTOM) / 2;
  const shade = (name: string) => `url(#${id(name)})`;

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
        className="mx-auto w-full max-w-md"
        role="img"
        aria-label={TIERS.map(
          (tier) => `${g.tiers[tier]}: ${tier === "pleasure" ? capLabel() : label(tier)}`,
        ).join(", ")}
      >
        <defs>
          <linearGradient id={id("cylinder")} x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stopColor={DARK} stopOpacity="0.14" />
            <stop offset="0.3" stopColor={LIGHT} stopOpacity="0.3" />
            <stop offset="0.55" stopColor={LIGHT} stopOpacity="0" />
            <stop offset="1" stopColor={DARK} stopOpacity="0.24" />
          </linearGradient>
          <linearGradient id={id("moulding")} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor={LIGHT} stopOpacity="0.45" />
            <stop offset="0.5" stopColor={LIGHT} stopOpacity="0" />
            <stop offset="1" stopColor={DARK} stopOpacity="0.22" />
          </linearGradient>
          <clipPath id={id("shaft")}>
            <path d={column.shaft} />
          </clipPath>
          <clipPath id={id("column")}>
            <ColumnSilhouette />
          </clipPath>
          <linearGradient id={id("gilt")} x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stopColor="var(--color-goal-gold-shine)" stopOpacity="0.85" />
            <stop offset="0.7" stopColor="var(--color-goal-gold-shine)" stopOpacity="0" />
          </linearGradient>
          <clipPath id={id("cap-left")}>
            <polygon points={CAPSTONE.left} />
          </clipPath>
          <clipPath id={id("cap-right")}>
            <polygon points={CAPSTONE.right} />
          </clipPath>
          {SHAPES.map((shape, i) => (
            <g key={TIERS_ABOVE[i]}>
              <clipPath id={id(`left-${i}`)}>
                <polygon points={shape.left} />
              </clipPath>
              <clipPath id={id(`right-${i}`)}>
                <polygon points={shape.right} />
              </clipPath>
            </g>
          ))}
        </defs>

        {/* The column: stone, the emergency fund's colour rising from its foot, then the carving. */}
        <g fill={STONE}>
          <ColumnSilhouette leafShade />
        </g>
        <g clipPath={`url(#${id("column")})`}>
          <rect
            x={0}
            y={fundLevel}
            width={WIDTH}
            height={COLUMN_BOTTOM - fundLevel}
            fill={tierColour("precaution")}
          />
        </g>
        <g stroke={EDGE} strokeWidth={1}>
          <polygon points={column.plinthTop} fill={shade("moulding")} fillOpacity={0.6} />
          <rect {...rect(PLINTH)} fill={shade("moulding")} />
          {column.rings.map((r) => (
            <rect
              key={r.y}
              x={r.x}
              y={r.y}
              width={r.w}
              height={r.h}
              rx={r.rx}
              fill={shade("moulding")}
            />
          ))}
        </g>
        <g clipPath={`url(#${id("shaft")})`}>
          {column.flutes.map((f) => (
            <g key={f.x}>
              <line
                x1={f.x}
                x2={f.x}
                y1={SHAFT_TOP + 6}
                y2={SHAFT_BOTTOM - 6}
                stroke={DARK}
                strokeOpacity={0.2}
                strokeWidth={f.w}
                strokeLinecap="round"
              />
              <line
                x1={f.highlight}
                x2={f.highlight}
                y1={SHAFT_TOP + 6}
                y2={SHAFT_BOTTOM - 6}
                stroke={LIGHT}
                strokeOpacity={0.45}
              />
            </g>
          ))}
          <rect
            x={AX - SHAFT_BOTTOM_HALF}
            y={SHAFT_TOP}
            width={SHAFT_BOTTOM_HALF * 2}
            height={SHAFT_BOTTOM - SHAFT_TOP}
            fill={shade("cylinder")}
          />
        </g>
        <g stroke={EDGE} strokeWidth={1}>
          <path d={column.shaft} fill="none" />
          <path d={column.bell} fill={shade("cylinder")} fillOpacity={0.7} />
          {column.leaves.map((leaf) => (
            <g key={leaf.d}>
              <path d={leaf.d} fill={shade("moulding")} fillOpacity={0.5} strokeWidth={0.8} />
              <path d={leaf.rib} fill="none" strokeWidth={0.8} />
              <path d={leaf.veins} fill="none" strokeWidth={0.5} strokeOpacity={0.8} />
            </g>
          ))}
          <rect {...rect(ECHINUS)} rx={8} fill={shade("moulding")} />
          {column.volutes.map((v) => (
            <g key={v.cx}>
              <circle cx={v.cx} cy={v.cy} r={v.r} fill={shade("moulding")} fillOpacity={0.6} />
              <path d={v.spiral} fill="none" strokeWidth={1.4} strokeLinecap="round" />
            </g>
          ))}
          <circle cx={AX} cy={ECHINUS.y + ECHINUS.h / 2} r={5} fill="none" />
          <polygon points={column.abacusTop} fill={shade("moulding")} fillOpacity={0.5} />
          <rect {...rect(ABACUS)} fill={shade("moulding")} />
        </g>
        <Label
          y={shaftMid}
          fromX={AX + SHAFT_BOTTOM_HALF + 10}
          name={g.tierShort.precaution}
          value={label("precaution")}
        />

        {/* The pyramid: block courses on two faces, each tier filled from the bottom. */}
        {SHAPES.map((shape, i) => {
          const tier = TIERS_ABOVE[i] as Tier;
          const height = shape.bottom - shape.top;
          const filled = height * progress(tier);
          const mid = (shape.bottom + shape.top) / 2;
          return (
            <g key={tier}>
              <polygon points={shape.left} fill={STONE} />
              <polygon points={shape.right} fill={STONE} />
              <g clipPath={`url(#${id(`left-${i}`)})`}>
                <rect
                  x={0}
                  y={shape.bottom - filled}
                  width={WIDTH}
                  height={filled}
                  fill={tierColour(tier)}
                />
                <Blocks blocks={shape.leftBlocks} joints={shape.joints} highlight />
              </g>
              <g clipPath={`url(#${id(`right-${i}`)})`}>
                <rect
                  x={0}
                  y={shape.bottom - filled}
                  width={WIDTH}
                  height={filled}
                  fill={tierColour(tier)}
                />
                <rect
                  x={0}
                  y={shape.top}
                  width={WIDTH}
                  height={height}
                  fill={DARK}
                  fillOpacity={0.17}
                />
                <Blocks blocks={shape.rightBlocks} joints={shape.joints} />
              </g>
              {/* A surface gap between the tiers. */}
              <polygon
                points={shape.outline}
                fill="none"
                stroke="var(--color-surface)"
                strokeWidth={3}
                strokeLinejoin="round"
              />
              <Label
                y={mid}
                fromX={AX + half(mid) + 8}
                name={g.tierShort[tier]}
                value={label(tier)}
              />
            </g>
          );
        })}

        {/* The capstone: gilded from its base as the pleasure goals fill, or stone and a padlock. */}
        <g>
          <polygon points={CAPSTONE.left} fill={STONE} />
          <polygon points={CAPSTONE.right} fill={STONE} />
          <g clipPath={`url(#${id("cap-left")})`}>
            <rect
              x={0}
              y={CAP_BOTTOM - capFilled}
              width={WIDTH}
              height={capFilled}
              fill={tierColour("pleasure")}
            />
            <rect
              x={0}
              y={CAP_BOTTOM - capFilled}
              width={WIDTH}
              height={capFilled}
              fill={shade("gilt")}
            />
          </g>
          <g clipPath={`url(#${id("cap-right")})`}>
            <rect
              x={0}
              y={CAP_BOTTOM - capFilled}
              width={WIDTH}
              height={capFilled}
              fill={tierColour("pleasure")}
            />
            <rect
              x={0}
              y={AY}
              width={WIDTH}
              height={CAP_BOTTOM - AY}
              fill={DARK}
              fillOpacity={0.17}
            />
          </g>
          <line
            x1={AX - half(CAP_BOTTOM)}
            x2={AX + half(CAP_BOTTOM)}
            y1={CAP_BOTTOM}
            y2={CAP_BOTTOM}
            stroke="var(--color-surface)"
            strokeWidth={3}
          />
          {locked && <Padlock x={AX + 1} y={CAP_BOTTOM - 16} />}
          <Label
            y={AY + (CAP_BOTTOM - AY) * 0.6}
            fromX={AX + half(AY + (CAP_BOTTOM - AY) * 0.6) + 8}
            name={g.tierShort.pleasure}
            value={capLabel()}
          />
        </g>
      </svg>
      <p className="text-sm text-muted">
        {locked ? g.capstoneLocked(missing) : g.capstoneUnlocked}
      </p>
      <ul className="flex flex-col gap-1 text-sm">
        {[...PYRAMID].reverse().map((tier) => {
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

const rect = (r: { x: number; y: number; w: number; h: number }) => ({
  x: r.x,
  y: r.y,
  width: r.w,
  height: r.h,
});

/** Every part of the column, filled with the group's colour: its stone, or a clip. */
function ColumnSilhouette({ leafShade = false }: { leafShade?: boolean }) {
  return (
    <>
      <polygon points={column.plinthTop} fill={leafShade ? STONE_TOP : undefined} />
      <rect {...rect(PLINTH)} />
      {column.rings.map((r) => (
        <rect
          key={r.y}
          x={r.x}
          y={r.y}
          width={r.w}
          height={r.h}
          rx={r.rx}
          fill={leafShade && r.top ? STONE_TOP : undefined}
        />
      ))}
      <path d={column.shaft} />
      <path d={column.bell} />
      {column.leaves.map((leaf) => (
        <path key={leaf.d} d={leaf.d} fill={leafShade && !leaf.shaded ? STONE_TOP : undefined} />
      ))}
      <rect {...rect(ECHINUS)} rx={8} fill={leafShade ? STONE_TOP : undefined} />
      {column.volutes.map((v) => (
        <circle key={v.cx} cx={v.cx} cy={v.cy} r={v.r} fill={leafShade ? STONE_TOP : undefined} />
      ))}
      <polygon points={column.abacusTop} fill={leafShade ? STONE_TOP : undefined} />
      <rect {...rect(ABACUS)} />
    </>
  );
}

/** A face's blocks: each with its grain, and joints sunk in with a lit edge. */
function Blocks({
  blocks,
  joints,
  highlight = false,
}: {
  blocks: Block[];
  joints: number[];
  highlight?: boolean;
}) {
  return (
    <>
      {blocks.map((b) => (
        <g key={`${b.x}-${b.y}`}>
          <rect x={b.x} y={b.y} width={b.w} height={b.h} fill={b.tint} fillOpacity={b.alpha} />
          <line
            x1={b.x}
            x2={b.x}
            y1={b.y}
            y2={b.y + b.h}
            stroke={DARK}
            strokeOpacity={0.24}
            strokeWidth={1.1}
          />
          {highlight && (
            <line
              x1={b.x + 1.2}
              x2={b.x + 1.2}
              y1={b.y}
              y2={b.y + b.h}
              stroke={LIGHT}
              strokeOpacity={0.35}
              strokeWidth={0.8}
            />
          )}
        </g>
      ))}
      {joints.map((y) => (
        <g key={y}>
          <line
            x1={0}
            x2={WIDTH}
            y1={y}
            y2={y}
            stroke={DARK}
            strokeOpacity={0.26}
            strokeWidth={1.3}
          />
          <line
            x1={0}
            x2={WIDTH}
            y1={y + 1.2}
            y2={y + 1.2}
            stroke={LIGHT}
            strokeOpacity={highlight ? 0.4 : 0.22}
            strokeWidth={0.8}
          />
        </g>
      ))}
    </>
  );
}

/** A small padlock, centred on (x, y), in the muted text colour. */
function Padlock({ x, y }: { x: number; y: number }) {
  return (
    <g stroke="var(--color-muted)" strokeWidth={1.6} fill="none">
      <path d={`M ${x - 4} ${y - 2} v -3 a 4 4 0 0 1 8 0 v 3`} />
      <rect x={x - 6} y={y - 2} width={12} height={9} rx={1.5} fill="var(--color-goal-stone-top)" />
    </g>
  );
}

/** A tier's name and progress to the right, joined to it by a dotted leader. */
function Label({
  y,
  fromX,
  name,
  value,
}: {
  y: number;
  fromX: number;
  name: string;
  value: string;
}) {
  return (
    <g>
      <line
        x1={fromX}
        x2={LABEL_X - 8}
        y1={y}
        y2={y}
        stroke="var(--color-border)"
        strokeDasharray="2 4"
      />
      <text x={LABEL_X} y={y - 3} className="fill-fg text-[13px] font-semibold">
        {name}
      </text>
      <text x={LABEL_X} y={y + 14} className="tabular fill-muted text-[13px]">
        {value}
      </text>
    </g>
  );
}
