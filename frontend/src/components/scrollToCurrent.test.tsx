import { render } from "@testing-library/react";
import { expect, test } from "vitest";
import { useScrollToCurrent } from "./scrollToCurrent";

function rect(left: number, right: number) {
  return () => ({ left, right, top: 0, bottom: 0, width: right - left, height: 0 }) as DOMRect;
}

function Frame({ ready }: { ready: boolean }) {
  const ref = useScrollToCurrent<HTMLDivElement>(ready ? "k" : null);
  return (
    <div ref={ref} data-testid="frame">
      <table>
        <thead>
          <tr>
            <th>Line</th>
            <th aria-current="date">Nov</th>
          </tr>
        </thead>
      </table>
    </div>
  );
}

test("a wide table scrolls so that the current month's column ends at its right edge", () => {
  const proto = HTMLElement.prototype;
  const original = proto.getBoundingClientRect;
  proto.getBoundingClientRect = function (this: HTMLElement) {
    if (this.dataset.testid === "frame") return rect(0, 400)();
    if (this.getAttribute("aria-current") === "date") return rect(900, 1000)();
    return rect(0, 0)();
  };
  try {
    const { getByTestId, rerender } = render(<Frame ready={false} />);
    expect(getByTestId("frame").scrollLeft).toBe(0);
    rerender(<Frame ready />);
    expect(getByTestId("frame").scrollLeft).toBe(600);
  } finally {
    proto.getBoundingClientRect = original;
  }
});
