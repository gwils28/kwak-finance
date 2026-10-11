import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";

// The first render of a test file can exceed the default 1s on a busy CI runner.
configure({ asyncUtilTimeout: 5000 });
