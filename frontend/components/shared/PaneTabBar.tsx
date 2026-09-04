"use client";

/**
 * Single-column pane navigation, below `lg` only (spec §9).
 *
 * The three panes are top-level tabs on tablet/phone, and this is the control that switches
 * between them. It sits at the *bottom* of the viewport: it is the app's primary navigation
 * on a phone, and the top edge is the hardest place on the screen for a thumb to reach.
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
 *
 * The bar is in normal flow rather than `position: fixed`, which is what keeps it off the
 * Analyze button: `AnalysisFormPane` and `HistoryPane` both end in an 89px bordered footer,
 * and overlaying them would mean threading a matching bottom padding through every pane's
 * scroll container. The gutter around the pill comes from this nav's own padding.
 */

import { BarChart3, History, PenLine } from "lucide-react";
import type { LucideIcon } from "lucide-react";

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

export default function PaneTabBar({
  tab,
  onSelect,
}: {
  tab: Tab;
  onSelect: (tab: Tab) => void;
}) {
  return (
    <nav
      aria-label="Panes"
      role="tablist"
      className="flex shrink-0 justify-center px-4 pt-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] lg:hidden"
    >
      <div className="border-border bg-surface flex items-center gap-1 rounded-full border p-1.5 shadow-md">
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
