/**
 * Turning the stored `Theme` into a painted palette.
 *
 * `lib/preferences.ts` stores the *choice* (`system` | `light` | `dark`); this module
 * resolves it to one of the two palettes in `app/globals.css` and puts the answer on
 * `<html data-theme>`. Splitting it this way is what lets the dark palette be written once:
 * because `system` never reaches CSS, `globals.css` needs no second copy of the dark values
 * inside a `prefers-color-scheme` block.
 *
 * Two callers, deliberately different:
 *   - `app/layout.tsx` embeds `THEME_INIT_SCRIPT`, which runs while the HTML is still
 *     parsing — before the browser's first paint, and long before React exists.
 *   - `components/shared/ThemeToggle.tsx` calls `resolveTheme`/`applyTheme` afterwards, for
 *     every change the script cannot have anticipated.
 */

import { PREFERENCES_STORAGE_KEY, type Theme } from "@/lib/preferences";

export type ResolvedTheme = "light" | "dark";

export const DARK_MEDIA_QUERY = "(prefers-color-scheme: dark)";

/** `system` asks the OS; the other two answer for themselves. */
export function resolveTheme(theme: Theme): ResolvedTheme {
  if (theme !== "system") return theme;
  if (typeof window === "undefined" || !window.matchMedia) return "light";
  return window.matchMedia(DARK_MEDIA_QUERY).matches ? "dark" : "light";
}

export function applyTheme(resolved: ResolvedTheme): void {
  document.documentElement.dataset.theme = resolved;
}

/**
 * The pre-paint applier, as an IIFE for `app/layout.tsx`'s inline `<script>`.
 *
 * `useSyncExternalStore` cannot help here: it runs at hydration, which is after the browser
 * has already painted the server's markup. For a collapsed pane that costs one frame of the
 * wrong width; for a theme it is a full white flash on every load. So the value is read a
 * second time, in a form that runs during HTML parsing.
 *
 * It duplicates the store's *logic* — but not its storage key, and not the dark palette,
 * which are the two things that would fail silently if they drifted. Kept in the terse
 * style an inline script warrants; `try/catch` swallows blocked storage exactly as
 * `preferences.ts` does, leaving the light default that `:root` already paints.
 */
export const THEME_INIT_SCRIPT = `(function(){try{var r=localStorage.getItem(${JSON.stringify(
  PREFERENCES_STORAGE_KEY,
)});var t=r?JSON.parse(r).theme:"system";if(t!=="light"&&t!=="dark")t=window.matchMedia(${JSON.stringify(
  DARK_MEDIA_QUERY,
)}).matches?"dark":"light";document.documentElement.dataset.theme=t}catch(e){}})()`;
