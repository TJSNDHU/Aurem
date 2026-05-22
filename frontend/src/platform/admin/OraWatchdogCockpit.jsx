/**
 * OraWatchdogCockpit.jsx — iter 326ii (Phase 3 P2.X UI consolidation)
 *
 * Single pane of glass for the founder's overnight-autonomy watchdog.
 * Mounts the four cards built in iter 326w/cc/ee/gg into a 2-column
 * desktop grid (1-column on mobile).
 *
 *   ┌─────────────────────────────┬─────────────────────────────┐
 *   │  Daily LLM Spend            │  Email Channel Health       │
 *   ├─────────────────────────────┼─────────────────────────────┤
 *   │  Morning Brief              │  Recent ORA Decisions       │
 *   └─────────────────────────────┴─────────────────────────────┘
 *
 * Route: /admin/ora-watchdog
 */
import React from "react";
import DailySpendCard from "./DailySpendCard";
import EmailHealthCard from "./EmailHealthCard";
import MorningBriefCard from "./MorningBriefCard";
import RecentDecisionsPanel from "./RecentDecisionsPanel";

export default function OraWatchdogCockpit() {
  return (
    <div
      className="min-h-screen bg-zinc-950 text-zinc-100 p-4 md:p-8"
      data-testid="ora-watchdog-cockpit"
    >
      <div className="max-w-7xl mx-auto">
        <header className="mb-6 md:mb-8">
          <h1
            className="text-2xl md:text-3xl font-semibold tracking-tight"
            data-testid="ora-watchdog-title"
          >
            ORA Watchdog
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Single screen for overnight autonomous runs — spend, email,
            morning brief, and recent decisions.
          </p>
        </header>

        <div
          className="grid grid-cols-1 lg:grid-cols-2 gap-4 md:gap-6"
          data-testid="ora-watchdog-grid"
        >
          <DailySpendCard />
          <EmailHealthCard />
          <MorningBriefCard />
          <div
            className="rounded-lg border border-zinc-800 bg-zinc-950 overflow-hidden h-[520px]"
            data-testid="ora-watchdog-decisions-wrap"
          >
            <RecentDecisionsPanel />
          </div>
        </div>
      </div>
    </div>
  );
}
