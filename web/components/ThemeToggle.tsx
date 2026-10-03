"use client";

import { useEffect, useState } from "react";
import { Icon } from "./Icon";

// Toggles light/dark by setting data-theme on <html>, persisted to localStorage.
export function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("theme");
    const isDark = saved ? saved === "dark" : true; // default to dark
    document.documentElement.dataset.theme = isDark ? "dark" : "light";
    setDark(isDark);
  }, []);

  function toggle() {
    const next = !dark;
    document.documentElement.dataset.theme = next ? "dark" : "light";
    localStorage.setItem("theme", next ? "dark" : "light");
    setDark(next);
  }

  return (
    <button className="btn-icon" onClick={toggle} title={dark ? "Light mode" : "Dark mode"}>
      <Icon name={dark ? "bulb" : "sparkle"} size={16} />
    </button>
  );
}
