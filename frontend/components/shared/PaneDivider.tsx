"use client";

/**
 * Draggable divider between the Analysis and Results panes (`lg` and above only — below
 * it the panes are tabs and there is nothing to divide).
 *
 * What it moves is the Analysis pane's width; Results is `flex-1` and takes whatever is
 * left, which is why widening Results means narrowing Analysis. The pixel minimums that
 * stop either pane collapsing are CSS `min-width`/`max-width` in `page.tsx`, not clamping
 * here, so shrinking the window re-resolves them for free.
 */

import { useRef } from "react";

import { cn } from "@/lib/format";
import {
  DEFAULT_ANALYSIS_PERCENT,
  MAX_ANALYSIS_PERCENT,
  MIN_ANALYSIS_PERCENT,
  clampAnalysisPercent,
  setAnalysisPanePercent,
} from "@/lib/preferences";

/** Arrow-key step, in percentage points. */
const STEP = 2;

export default function PaneDivider({
  percent,
  rowRef,
  analysisRef,
}: {
  percent: number;
  /** The flex row both panes live in — the width every percentage is measured against. */
  rowRef: React.RefObject<HTMLDivElement | null>;
  /** The pane being resized, read back each move to see what CSS actually allowed. */
  analysisRef: React.RefObject<HTMLElement | null>;
}) {
  /**
   * Where the pointer went down, and what the pane's width was then. The drag is applied
   * as a *delta* from that pair rather than derived from the pointer's absolute position,
   * because the value being set is the Analysis pane's width while the pointer's position
   * is measured from the row's left edge — and the History pane sits between the two. A
   * position-based calculation would silently fold History's 280px into the width and
   * make the pane jump on grab.
   */
  const drag = useRef<{ x: number; percent: number } | null>(null);

  /**
   * A drag writes the CSS variable straight to the DOM instead of going through React.
   * Nothing in the three panes is memoised, so routing ~120 pointer events per second
   * through state would re-render 35 checkboxes and 35 metric rows on every frame. React
   * renders twice per drag instead — once when it starts, once when the committed value
   * lands in the store — and the DOM reconciles because React writes back the same value.
   */
  const percentAt = (clientX: number): number | null => {
    const start = drag.current;
    const row = rowRef.current;
    if (!start || !row) return null;
    const width = row.getBoundingClientRect().width;
    if (width === 0) return null;
    return clampAnalysisPercent(
      start.percent + ((clientX - start.x) / width) * 100,
    );
  };

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const next = percentAt(event.clientX);
    if (next === null) return;
    const row = rowRef.current;
    if (!row) return;
    row.style.setProperty("--analysis-w", `${next}%`);

    /*
     * CSS `min-width`/`max-width` owns the pixel floors, so the value just written may have
     * been clipped. Re-baseline the drag against what actually rendered: without this, a
     * drag past the stop keeps inflating the percentage while the pane stays put, and
     * dragging back does nothing until the surplus is unwound — the dead zone that makes a
     * divider feel broken.
     */
    const pane = analysisRef.current;
    if (!pane) return;
    const rowWidth = row.getBoundingClientRect().width;
    if (rowWidth === 0) return;
    const actual = (pane.getBoundingClientRect().width / rowWidth) * 100;
    if (Math.abs(actual - next) > 0.1) {
      drag.current = { x: event.clientX, percent: actual };
      row.style.setProperty("--analysis-w", `${actual}%`);
    }
  };

  const endDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return;
    const next = percentAt(event.clientX);
    drag.current = null;
    event.currentTarget.releasePointerCapture(event.pointerId);
    if (next !== null) setAnalysisPanePercent(next);
  };

  /**
   * The rendered width as a percentage, which is not the stored value whenever CSS has
   * clamped it. Arrow keys step from *this* for the same reason the drag re-baselines:
   * stepping from a stored 15% while the pane is really sitting at its 360px floor would
   * move the number several times before the pane budged.
   */
  const renderedPercent = (): number => {
    const row = rowRef.current;
    const pane = analysisRef.current;
    if (!row || !pane) return percent;
    const width = row.getBoundingClientRect().width;
    if (width === 0) return percent;
    return (pane.getBoundingClientRect().width / width) * 100;
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const next =
      event.key === "ArrowLeft"
        ? renderedPercent() - STEP
        : event.key === "ArrowRight"
          ? renderedPercent() + STEP
          : event.key === "Home"
            ? MIN_ANALYSIS_PERCENT
            : event.key === "End"
              ? MAX_ANALYSIS_PERCENT
              : null;
    if (next === null) return;
    event.preventDefault();
    setAnalysisPanePercent(next);
  };

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-controls="pane-analyze"
      aria-label="Resize the results panel"
      aria-valuenow={Math.round(percent)}
      aria-valuemin={MIN_ANALYSIS_PERCENT}
      aria-valuemax={MAX_ANALYSIS_PERCENT}
      tabIndex={0}
      onPointerDown={(event) => {
        drag.current = { x: event.clientX, percent };
        event.currentTarget.setPointerCapture(event.pointerId);
      }}
      onPointerMove={onPointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      onKeyDown={onKeyDown}
      onDoubleClick={() => setAnalysisPanePercent(DEFAULT_ANALYSIS_PERCENT)}
      title="Drag to resize · double-click to reset"
      className={cn(
        // The hairline itself, replacing the `lg:border-r` the Analysis pane used to draw.
        "bg-border relative hidden w-px shrink-0 lg:block",
        "hover:bg-accent focus-visible:bg-accent transition-colors",
      )}
    >
      {/*
        A 1px line is not a pointer target. This widens the grab area to ~9px without
        taking any layout space, so the panes still meet on a hairline.
      */}
      <span
        aria-hidden
        className="absolute inset-y-0 -right-1 -left-1 cursor-col-resize"
      />
    </div>
  );
}
