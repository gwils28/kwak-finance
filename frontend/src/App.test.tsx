import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./App";

afterEach(() => vi.unstubAllGlobals());

test("shows the API version when the backend is healthy", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(Response.json({ status: "ok", version: "0.0.0" })),
  );
  render(<App />);
  expect(screen.getByRole("heading", { name: "Kwak Finance" })).toBeInTheDocument();
  expect(await screen.findByText("API ok · v0.0.0")).toBeInTheDocument();
});

test("reports an unreachable backend", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network")));
  render(<App />);
  expect(await screen.findByText("API unreachable")).toBeInTheDocument();
});
