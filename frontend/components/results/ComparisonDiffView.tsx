"use client";

/**
 * Word-level diff of Text A against Text B (spec §11).
 *
 * Purely presentational: it re-derives an alignment client-side so the reader can *see*
 * what the Tier 1 comparison metrics are measuring. It is not the backend's LCS — that
 * value comes from the response like every other metric.
 */

import { useMemo, useState } from "react";

import { cn } from "@/lib/format";

/**
 * The LCS table is O(n·m); beyond this many words per side the diff is skipped rather
 * than freezing the pane. The metrics themselves are unaffected.
 */
const MAX_WORDS = 1200;

type DiffOp = { type: "equal" | "insert" | "delete"; tokens: string[] };

function tokenize(text: string): string[] {
  const trimmed = text.trim();
  return trimmed ? trimmed.split(/\s+/) : [];
}

function diffWords(a: string[], b: string[]): DiffOp[] {
  const rows = a.length;
  const cols = b.length;
  // lengths[i][j] = LCS length of a[i:] and b[j:], flattened.
  const lengths = new Int32Array((rows + 1) * (cols + 1));
  const at = (i: number, j: number) => i * (cols + 1) + j;

  for (let i = rows - 1; i >= 0; i -= 1) {
    for (let j = cols - 1; j >= 0; j -= 1) {
      lengths[at(i, j)] =
        a[i] === b[j]
          ? lengths[at(i + 1, j + 1)] + 1
          : Math.max(lengths[at(i + 1, j)], lengths[at(i, j + 1)]);
    }
  }

  const ops: DiffOp[] = [];
  const push = (type: DiffOp["type"], token: string) => {
    const last = ops[ops.length - 1];
    if (last && last.type === type) last.tokens.push(token);
    else ops.push({ type, tokens: [token] });
  };

  let i = 0;
  let j = 0;
  while (i < rows && j < cols) {
    if (a[i] === b[j]) {
      push("equal", a[i]);
      i += 1;
      j += 1;
    } else if (lengths[at(i + 1, j)] >= lengths[at(i, j + 1)]) {
      push("delete", a[i]);
      i += 1;
    } else {
      push("insert", b[j]);
      j += 1;
    }
  }
  while (i < rows) push("delete", a[i++]);
  while (j < cols) push("insert", b[j++]);

  return ops;
}

export default function ComparisonDiffView({
  textA,
  textB,
}: {
  textA: string;
  textB: string;
}) {
  const [open, setOpen] = useState(false);

  const wordsA = useMemo(() => tokenize(textA), [textA]);
  const wordsB = useMemo(() => tokenize(textB), [textB]);
  const tooLarge = wordsA.length > MAX_WORDS || wordsB.length > MAX_WORDS;

  const ops = useMemo(
    () => (open && !tooLarge ? diffWords(wordsA, wordsB) : []),
    [open, tooLarge, wordsA, wordsB],
  );

  return (
    <section className="flex flex-col gap-2">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        className="text-ink-muted hover:text-ink self-start rounded text-sm transition-colors"
      >
        {open ? "Hide" : "Show"} word-level diff
      </button>

      {open ? (
        tooLarge ? (
          <p className="text-ink-muted text-sm">
            Texts are too long to diff in the browser ({MAX_WORDS.toLocaleString("en-US")}{" "}
            word limit per side).
          </p>
        ) : (
          <>
            <p className="text-ink-muted text-xs">
              <span className="text-negative">Struck through</span> is only in Text A;{" "}
              <span className="text-positive">highlighted</span> is only in Text B.
            </p>
            <p className="border-border bg-surface max-h-64 overflow-y-auto rounded border p-3 text-sm leading-relaxed">
              {ops.map((op, index) => (
                <span
                  key={index}
                  className={cn(
                    op.type === "delete" && "bg-negative/10 text-negative line-through",
                    op.type === "insert" && "bg-positive/10 text-positive",
                  )}
                >
                  {op.tokens.join(" ")}{" "}
                </span>
              ))}
            </p>
          </>
        )
      ) : null}
    </section>
  );
}
