// Run `make openapi` from the repo root: it dumps the backend schema, then generates src/api/generated.
// No import of defineConfig: the generator runs through `pnpm dlx` (see package.json), so it
// is not a project dependency.
export default {
  input: "openapi.json",
  output: "src/api/generated",
  plugins: [
    "@hey-api/typescript",
    "@hey-api/sdk",
    // No baseUrl baked in: src/api/client.ts points it at the page origin.
    { name: "@hey-api/client-fetch", baseUrl: false },
  ],
};
