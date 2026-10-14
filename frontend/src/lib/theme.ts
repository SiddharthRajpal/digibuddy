"use client";

import { useCallback, useEffect, useState } from "react";

export type ThemeChoice = "daylight" | "lamplight" | "system";
const KEY = "digibuddy-theme";

export function readTheme(): ThemeChoice {
  try {
    const v = window.localStorage.getItem(KEY);
    if (v === "daylight" || v === "lamplight" || v === "system") return v;
  } catch {
    /* storage may be unavailable */
  }
  return "daylight";
}

export function applyTheme(choice: ThemeChoice): void {
  document.documentElement.dataset.theme = choice;
}

export function useTheme(): [ThemeChoice, (t: ThemeChoice) => void] {
  const [theme, setThemeState] = useState<ThemeChoice>("daylight");
  useEffect(() => setThemeState(readTheme()), []);
  const setTheme = useCallback((t: ThemeChoice) => {
    setThemeState(t);
    applyTheme(t);
    try {
      window.localStorage.setItem(KEY, t);
    } catch {
      /* ignore */
    }
  }, []);
  return [theme, setTheme];
}

/** Inline script for <head> so the saved theme applies before first paint. */
export const THEME_BOOT_SCRIPT = `try{var t=localStorage.getItem("${KEY}");document.documentElement.dataset.theme=(t==="lamplight"||t==="system")?t:"daylight"}catch(e){document.documentElement.dataset.theme="daylight"}`;
