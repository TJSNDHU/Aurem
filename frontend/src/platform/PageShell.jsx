/**
 * PageShell — wraps every admin/platform page to guarantee:
 *   1. Page mounts scrolled to the TOP of the content area (no carry-over
 *      scroll from the previously rendered page, no ancestor drift from
 *      children calling scrollIntoView on mount).
 *   2. Consistent flex layout that fills the content area without the child
 *      needing to set minHeight: 100vh (which was pushing AuremDashboard's
 *      parent container into a scrolled state).
 *
 * Usage:
 *   <PageShell>
 *     <ORACommandConsole />
 *   </PageShell>
 *
 * Implementation notes:
 *   - useLayoutEffect fires BEFORE browser paint, so the scroll reset
 *     happens on the very first frame, no visible jump.
 *   - We walk up from the shell until we hit <body>, resetting scrollTop on
 *     every ancestor that can scroll (including overflow-hidden containers
 *     that Chrome silently scrolls via scrollIntoView on focused children).
 *   - A MutationObserver safety net re-resets once if a child mounts late
 *     with auto-focus / scrollIntoView (common with SSE / async data).
 */
import React, { useLayoutEffect, useRef } from "react";

export default function PageShell({ children, className = "", style }) {
  const ref = useRef(null);

  useLayoutEffect(() => {
    const shell = ref.current;
    if (!shell) return;

    const resetAll = () => {
      try {
        window.scrollTo(0, 0);
      } catch {
        /* ignore */
      }
      // Walk up from the shell, zeroing any ancestor with a non-zero scrollTop.
      let el = shell;
      while (el && el !== document.body && el.parentElement) {
        el = el.parentElement;
        if (el.scrollTop !== 0) el.scrollTop = 0;
      }
    };

    resetAll();
    // Run across a few frames to beat late-mounting children that call
    // scrollIntoView (e.g. a live feed div with an empty initial state).
    const r1 = requestAnimationFrame(resetAll);
    const r2 = requestAnimationFrame(() => requestAnimationFrame(resetAll));
    const t1 = setTimeout(resetAll, 60);
    const t2 = setTimeout(resetAll, 250);

    // MutationObserver catches async content mounts (SSE, lazy imports, etc.)
    // that could re-scroll an ancestor. We observe once and detach quickly.
    const mo = new MutationObserver(() => resetAll());
    mo.observe(shell, { childList: true, subtree: true });
    const moStop = setTimeout(() => mo.disconnect(), 1500);

    return () => {
      cancelAnimationFrame(r1);
      cancelAnimationFrame(r2);
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(moStop);
      mo.disconnect();
    };
  }, []);

  return (
    <div
      ref={ref}
      data-page-shell
      className={className}
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        minHeight: 0, // critical: lets flex child shrink so parent scroll is respected
        overflow: "auto",
        ...style,
      }}
    >
      {children}
    </div>
  );
}
