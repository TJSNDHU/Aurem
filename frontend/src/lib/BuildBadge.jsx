/**
 * BuildBadge — universal live build badge (iter 277 rev-c).
 *
 * Fetches `/api/health` and shows the backend version string + uptime so
 * admins can visually confirm the deployed build matches the latest code.
 * Prevents the "purana dikh raha hai" class of bugs where a static iter
 * number in a header fooled operators into thinking prod was stale.
 *
 * Usage:
 *   <BuildBadge />
 */
import React from "react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function BuildBadge() {
  const [info, setInfo] = React.useState({ v: null, uptime: 0 });

  React.useEffect(() => {
    let cancel = false;
    const poll = async () => {
      try {
        const r = await fetch(`${API}/api/health`, { cache: "no-store" });
        const d = await r.json();
        if (!cancel) setInfo({ v: d.v, uptime: d.uptime_seconds || 0 });
      } catch {
        /* ignore transient failures */
      }
    };
    poll();
    const id = setInterval(poll, 30_000);
    return () => {
      cancel = true;
      clearInterval(id);
    };
  }, []);

  if (!info.v) {
    return <span className="text-gray-500">loading…</span>;
  }

  const uptimeMin = Math.round(info.uptime / 60);
  const fresh = info.uptime < 600; // < 10 min = fresh deploy

  return (
    <span
      className="inline-flex items-center gap-1.5 text-[10px] font-mono"
      data-testid="build-badge"
      title={`Backend build ${info.v} · uptime ${uptimeMin} min`}
    >
      <span
        className={`size-1.5 rounded-full ${
          fresh ? "bg-emerald-400 animate-pulse" : "bg-amber-400"
        }`}
      />
      <span className="text-gray-400">{info.v}</span>
      <span className="text-gray-600">· {uptimeMin}m</span>
    </span>
  );
}
