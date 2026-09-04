"use client";

/**
 * Single-column pane navigation, below `lg` only (spec §9).
 *
 * The three panes are top-level tabs on tablet/phone, and this is the control that switches
 * between them. It floats over the bottom of the viewport: it is the app's primary
 * navigation on a phone, and the top edge is the hardest place on the screen for a thumb to
 * reach. Pane content scrolls underneath it — every pane's scroll container reserves
 * `--pane-menu-space` (`globals.css`) as bottom padding below `lg`, so the last row can
 * still be scrolled clear of the pill.
 *
 * Nothing is allowed to sit *statically* under the bar, which is why neither the Analysis
 * pane nor the History pane has a footer any more: their actions live in the pane headers
 * instead (`AnalyzeButton`, `ClearHistoryButton`, `ThemeToggle`). Padding around a fixed bar
 * only works for scrolling content; a pinned action bar would just be permanently covered.
 *
 * Two design-system exceptions live here, both deliberate and both confined to this one
 * element — don't "correct" them back:
 *
 *  - **`rounded-full`.** §12.4 is 4px radius everywhere, and `globals.css` enforces it by
 *    pinning `--radius-xs/sm/md/lg` all to 4px. A floating menu reads as floating because
 *    it is a pill; `rounded-full` is a separate Tailwind utility, so it escapes that pin.
 *  - **`shadow-md`.** §12.4 reserves it for toasts and modals. A menu hovering over the
 *    panes is the same elevation question, and the token is already theme-aware through
 *    `--shadow-color`, so the dark palette needs nothing extra.
 */

import { BarChart3, History, PenLine } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/format";

export type Tab = "history" | "analyze" | "results";

/**
 * Order is the on-screen order, and it is load-bearing: History left, Analyze centre,
 * Results right — the centre item being the one the app opens on (`page.tsx`).
 *
 * `Clock` would be the obvious History glyph but already means "this tier is slow" in
 * `TierSelector`, so History gets the dedicated icon.
 */
const TABS: { id: Tab; label: string; Icon: LucideIcon }[] = [
  { id: "history", label: "History", Icon: History },
  { id: "analyze", label: "Analyze", Icon: PenLine },
  { id: "results", label: "Results", Icon: BarChart3 },
];

/**
 * True while a textarea holds focus, which on a phone means the soft keyboard is up.
 *
 * A `position: fixed` element is anchored to the *layout* viewport, which the keyboard does
 * not shrink, so the bar would be stranded behind the keyboard — and iOS Safari additionally
 * displaces fixed elements while the keyboard animates. Rather than chase that with
 * `visualViewport` geometry, which iOS reports inconsistently and which jitters through the
 * animation, the bar simply steps aside: nobody navigates panes mid-sentence, and dismissing
 * the keyboard brings it straight back.
 *
 * `focusout` fires *before* the incoming element takes focus, and whether
 * `document.activeElement` is `body` or the new node at that moment is browser-dependent —
 * hence reading it after the event settles. Without the deferral, moving between Text A and
 * Text B in compare mode flashes the bar back in for a frame.
 *
 * The deferral is a timeout rather than `requestAnimationFrame` because rAF does not run at
 * all in a backgrounded tab: blur the textarea, switch tabs, come back, and the callback
 * that was supposed to bring the bar back never fired. A timer is throttled there, not
 * suspended.
 */
function useTextareaFocused() {
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    const sync = () =>
      setFocused(document.activeElement instanceof HTMLTextAreaElement);
    let pending = 0;
    const syncAfterFocusSettles = () => {
      window.clearTimeout(pending);
      pending = window.setTimeout(sync, 0);
    };

    document.addEventListener("focusin", sync);
    document.addEventListener("focusout", syncAfterFocusSettles);
    return () => {
      window.clearTimeout(pending);
      document.removeEventListener("focusin", sync);
      document.removeEventListener("focusout", syncAfterFocusSettles);
    };
  }, []);

  return focused;
}

export default function PaneTabBar({
  tab,
  onSelect,
}: {
  tab: Tab;
  onSelect: (tab: Tab) => void;
}) {
  const hidden = useTextareaFocused();

  return (
    /*
      The wrapper spans the viewport so the pill can centre itself, but it is
      `pointer-events-none` so the gutter around the pill is not a dead strip over the
      content scrolling beneath — only the pill itself takes taps. `z-40` sits under
      `Toast`'s `z-50`, which clears the bar rather than stacking with it.
    */
    <nav
      aria-label="Panes"
      role="tablist"
      className="pointer-events-none fixed inset-x-0 bottom-0 z-40 flex justify-center px-4 pt-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] lg:hidden"
    >
      {/*
        `inert` as well as the visual hide: an off-screen bar should not be a tab stop, and
        `translate`/`opacity` alone would leave all three buttons focusable behind the
        keyboard.

        The transition names `translate`, not `transform`: Tailwind v4 emits `translate-y-*`
        on the individual `translate` property, so a `transition-[…,transform]` here fades
        the bar but snaps it down in one frame.
      */}
      <div
        inert={hidden}
        className={cn(
          "border-border bg-surface flex items-center gap-1 rounded-full border p-1.5 shadow-md transition-[opacity,translate]",
          hidden
            ? "pointer-events-none translate-y-[150%] opacity-0"
            : "pointer-events-auto translate-y-0 opacity-100",
        )}
      >
        {TABS.map(({ id, label, Icon }) => (
          /*
            The label is visible, so it is the accessible name — no `aria-label`/`title`
            here, unlike the icon-only buttons on the `lg` collapse rail. `min-w` plus the
            vertical padding keeps each item above a 44px touch target, and the focus ring
            is the global `:focus-visible` rule, which the nav's own padding leaves room for.
          */
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            aria-controls={`pane-${id}`}
            onClick={() => onSelect(id)}
            className={cn(
              "flex min-w-[72px] flex-col items-center gap-1 rounded-full px-4 py-2 transition-colors",
              tab === id
                ? "bg-accent-soft text-accent font-medium"
                : "text-ink-muted hover:text-ink",
            )}
          >
            <Icon size={20} strokeWidth={1.5} aria-hidden />
            <span className="text-[11px] leading-none">{label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}
