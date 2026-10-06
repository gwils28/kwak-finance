import { QueryClient } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { configureApiClient } from "./api/client";
import { createAppRouter } from "./router";
import { applyTheme, initialTheme } from "./theme";
import "./styles/tokens.css";

applyTheme(initialTheme());
configureApiClient();

const queryClient = new QueryClient();
const router = createAppRouter(queryClient);

const root = document.getElementById("root");
if (!root) throw new Error("#root element missing");

createRoot(root).render(
  <StrictMode>
    <App queryClient={queryClient} router={router} />
  </StrictMode>,
);
