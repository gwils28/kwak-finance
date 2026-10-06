import { useState } from "react";
import { useI18n } from "../i18n";
import { applyTheme, initialTheme, type Theme } from "../theme";
import { Button } from "./ui";

export function ThemeToggle() {
  const { t } = useI18n();
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    setTheme(next);
  };
  return (
    <Button variant="ghost" onClick={toggle}>
      {theme === "dark" ? t.common.lightTheme : t.common.darkTheme}
    </Button>
  );
}
