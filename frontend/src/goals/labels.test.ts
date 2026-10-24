import { expect, test } from "vitest";
import { spreadLabels } from "./AnalysisCharts";

const box = { top: 0, bottom: 300 };

test("a label stays by its point when nothing is in its way", () => {
  expect(
    spreadLabels(
      [
        { x: 100, y: 200 },
        { x: 600, y: 200 },
      ],
      box,
    ),
  ).toEqual([200, 200]);
});

test("a label moves off another point, and off another label", () => {
  // The second point sits where the first label is written: that label moves up.
  const ys = spreadLabels(
    [
      { x: 100, y: 200 },
      { x: 180, y: 200 },
    ],
    box,
  );
  expect(ys[1]).toBe(200);
  expect(ys[0]).toBeLessThan(200 - 14);
  // Three labels near each other end up on three lines.
  const three = spreadLabels(
    [
      { x: 100, y: 100 },
      { x: 105, y: 100 },
      { x: 110, y: 100 },
    ],
    box,
  );
  expect(new Set(three).size).toBe(3);
});

test("labels stay within the plot", () => {
  const ys = spreadLabels(
    [
      { x: 100, y: 295 },
      { x: 180, y: 295 },
    ],
    box,
  );
  expect(Math.max(...ys)).toBeLessThanOrEqual(300);
  expect(Math.min(...ys)).toBeGreaterThanOrEqual(0);
});

test("a label written leftwards, near the right edge, avoids what is on its left", () => {
  const ys = spreadLabels(
    [
      { x: 600, y: 100, flip: true },
      { x: 520, y: 100 },
    ],
    box,
  );
  expect(ys[0]).not.toBe(100);
});
