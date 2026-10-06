import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { configureApiClient } from "./api/client";
import { applyTheme, initialTheme } from "./theme";
import "./styles/tokens.css";

applyTheme(initialTheme());
configureApiClient();

const root = document.getElementById("root");
if (!root) throw new Error("#root element missing");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
