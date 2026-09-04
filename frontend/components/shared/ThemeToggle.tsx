"use client";

/**
 * Colour-scheme control: one button cycling system → light → dark.
 *
 * It is also the component that keeps `<html data-theme>` correct after the inline script
 * in `app/layout.tsx` has run — see the effect below.
 */

import { Monitor, Moon, Sun } from "lucide-react";
import { useLayoutEffect, useSyncExternalStore } from "react";

import { cn } from "@/lib/format";
import {
  getThemeServerSnapshot,
  getThemeSnapshot,
  setTheme,
  subscribe,
  type Theme,
} from "@/lib/preferences";
import { applyTheme, DARK_MEDIA_QUERY, resolveTheme } from "@/lib/theme";

/** Cycle order, and the order the icons and labels are indexed by. */
const ORDER: Theme[] = ["system", "light", "dark"];

const ICONS = { system: Monitor, light: Sun, dark: Moon } as const;
const LABELS: Record<Theme, string> = {
  system: "system",
  light: "light",
  dark: "dark",
};

export default function ThemeToggle({ className }: { className?: string }) {
  const theme = useSyncExternalStore(
    subscribe,
    getThemeSnapshot,
    getThemeServerSnapshot,
  );

  /**
   * The one place `data-theme` is maintained after first paint, covering three cases that
   * would otherwise each need their own mechanism:
   *
   *  1. The reader picks a theme — `setTheme` re-renders this component and the effect runs.
   *  2. The OS flips while the choice is `system` — the media-query listener re-applies.
   *  3. React's dev-only Strict Mode remount, which resets `<html>` to the attributes it
   *     manages from JSX and so wipes what the inline script wrote. Next's
   *     `preventing-flash-before-hydration` guide calls this out and prescribes exactly
   *     this fix; it is a no-op in production.
   *
   * `useLayoutEffect` rather than `useEffect` so case 3 is corrected before the browser
   * paints the remount.
   */
  useLayoutEffect(() => {
    applyTheme(resolveTheme(theme));
    if (theme !== "system") return;

    const media = window.matchMedia(DARK_MEDIA_QUERY);
    const onChange = () => applyTheme(resolveTheme("system"));
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [theme]);

  const next = ORDER[(ORDER.indexOf(theme) + 1) % ORDER.length];
  const Icon = ICONS[theme];

  /*
    A cycling button gives no visual clue what the next click does, so the label carries
    both the current state and the next one. It is the accessible name *and* the tooltip:
    the icon is `aria-hidden`.

    It deliberately does *not* say what `system` currently resolves to. That answer comes
    from `matchMedia`, which the server cannot read — rendering it here would make the
    label a hydration mismatch, and one that never self-corrects, since a reader already on
    `system` produces no post-hydration re-render to fix it.
  */
  const label = `Theme: ${LABELS[theme]}. Switch to ${LABELS[next]}.`;

  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      aria-label={label}
      title={label}
      className={cn(
        "text-ink-muted hover:text-ink hover:bg-accent-soft rounded p-1 transition-colors",
        className,
      )}
    >
      <Icon size={16} strokeWidth={1.5} aria-hidden />
    </button>
  );
}
