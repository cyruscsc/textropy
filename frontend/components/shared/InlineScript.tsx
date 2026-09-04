"use client";

/**
 * A `<script>` that runs while the browser parses the document, and is inert afterwards.
 *
 * The two renders disagree on purpose. `type="text/javascript"` on the server makes the
 * parser execute the tag before first paint; `type="text/plain"` on the client makes
 * React's reconciliation see an inert tag, so its "scripts inside React components are
 * never executed" warning never fires — a fair description, since a script React inserted
 * via a DOM update really would not run. `suppressHydrationWarning` covers the resulting
 * `type` diff: the DOM wins, which is right, because it holds a script that already ran.
 *
 * `"use client"` is load-bearing, not habit. A Server Component's body is only ever
 * evaluated on the server, so `typeof window` would be baked as `undefined` and the client
 * would still see an executable tag.
 *
 * ARCHITECTURE.md §3 has the rest: why a script is the only thing early enough to prevent
 * the flash, and why the naive inline `<script>` silently discarded its own DOM write.
 */
export default function InlineScript({ html }: { html: string }) {
  return (
    <script
      type={typeof window === "undefined" ? "text/javascript" : "text/plain"}
      suppressHydrationWarning
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
