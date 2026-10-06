import { expect, test } from "vitest";
import { niceTicks } from "./charts";

test.each([
  [2480, [0, 1000, 2000, 3000]],
  [1563, [0, 500, 1000, 1500, 2000]],
  [680, [0, 200, 400, 600, 800]],
  [42, [0, 20, 40, 60]],
  [0, [0, 100]],
])("niceTicks(%s)", (max, expected) => {
  expect(niceTicks(max)).toEqual(expected);
});
