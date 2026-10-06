import { useState } from "react";
import { applyTheme, initialTheme, type Theme } from "../theme";
import { Button } from "./ui";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    setTheme(next);
  };
  return (
    <Button variant="ghost" onClick={toggle}>
      {theme === "dark" ? "Light" : "Dark"} theme
    </Button>
  );
}
