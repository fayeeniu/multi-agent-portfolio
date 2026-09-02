"use client";

import { useEffect, useState } from "react";

type Theme = "dark" | "light";

function readTheme(): Theme {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    setTheme(readTheme());
  }, []);

  function toggle() {
    const current = theme ?? readTheme();
    const next: Theme = current === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("research-theme", next);
    } catch {
      /* private mode */
    }
  }

  const resolved = theme ?? "dark";
  const toLight = resolved === "dark";

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggle}
      aria-pressed={resolved === "dark"}
      aria-label={toLight ? "Switch to light appearance" : "Switch to dark appearance"}
    >
      {toLight ? "Light" : "Dark"}
    </button>
  );
}
