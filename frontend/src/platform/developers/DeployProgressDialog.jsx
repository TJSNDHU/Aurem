/**
 * DeployProgressDialog.jsx — iter D-51
 *
 * Shown after a successful GitHub push. Renders a 4-step stepper:
 *
 *   ✅ Pushed       (already done, marker green)
 *   ⏳ Building…    (spinner while we wait for prod /api/version
 *                    to flip to the new iter)
 *   ⏳ Deploying…   (we keep polling — the verifier router does the work)
 *   ✅ Live!        (when /api/developers/cto/verify/deploy returns
 *                    found:true)
 *
 * On success we also push a green row to the VerificationBadge.
 * On failure (timeout) we push a red row + show "Try again" CTA.
 *
 * Pure presentational + one POST to /api/developers/cto/verify/deploy.
 */
import React, { useEffect, useState } from "react";
import { Rocket, CheckCircle2, AlertCircle, Loader2, ExternalLink, X }
  from "lucide-react";
import { devAuthHeaders } from "./DeveloperShell";
import { pushVerifyEvent } from "./VerificationBadge";

const API = process.env.REACT_APP_BACKEND_URL || "";

const STEPS = [
  { id: "pushed",    label: "Code pushed to GitHub" },
  { id: "building",  label: "Building production bundle…" },
  { id: "deploying", label: "Deploying to aurem.live…" },
  { id: "live",      label: "Live on aurem.live!" },
];

export default function DeployProgressDialog({
  open, expectedIter, targetUrl = "https://aurem.live",
  commitSha = "", commitUrl = "", onClose,
}) {
  // current state: "pushed" | "building" | "deploying" | "live" | "failed"
  const [state, setState]    = useState("pushed");
  const [elapsed, setElapsed] = useState(0);
  const [version, setVersion] = useState("");

  useEffect(() => {
    if (!open) return undefined;
    setState("pushed"); setElapsed(0); setVersion("");

    const startedAt = Date.now();
    let alive = true;
    const tick = setInterval(() => {
      if (!alive) return;
      const s = Math.round((Date.now() - startedAt) / 1000);
      setElapsed(s);
      // Drive the visible step from elapsed seconds — backend polling
      // is doing the real work; this just keeps the UX honest.
      if (s >= 1 && s < 5)        setState((cur) => cur === "pushed"   ? "building"  : cur);
      else if (s >= 5 && s < 60)  setState((cur) => cur === "building" ? "deploying" : cur);
    }, 1000);

    // Fire the real deploy verification probe — polls /api/version
    // every 5 s up to 120 s.
    pushVerifyEvent("deploy", { status: "checking",
                                  detail: `target ${expectedIter}` });

    fetch(`${API}/api/developers/cto/verify/deploy`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...devAuthHeaders() },
      body: JSON.stringify({
        target_url:    targetUrl,
        expected_iter: expectedIter,
        timeout_s:     120,
        poll_every_s:  5,
      }),
    })
      .then((r) => r.json())
      .then((j) => {
        if (!alive) return;
        if (j.found) {
          setState("live");
          setVersion(j.iter || expectedIter);
          pushVerifyEvent("deploy", {
            status: "green",
            detail: `${j.iter} live in ${j.elapsed_s}s`,
            url:    targetUrl,
          });
        } else {
          setState("failed");
          setVersion(j.iter || "");
          pushVerifyEvent("deploy", {
            status: "red",
            detail: `stuck on ${j.iter || "unknown"}`,
          });
        }
      })
      .catch(() => {
        if (!alive) return;
        setState("failed");
        pushVerifyEvent("deploy", { status: "red",
                                      detail: "probe failed" });
      });

    return () => { alive = false; clearInterval(tick); };
  }, [open, expectedIter, targetUrl]);

  if (!open) return null;

  const stateRank = ["pushed", "building", "deploying", "live"].indexOf(state);
  const failed    = state === "failed";

  return (
    <div data-testid="deploy-progress-dialog"
         role="dialog" aria-modal="true"
         style={{ position: "fixed", inset: 0,
                  background: "rgba(0,0,0,0.55)",
                  display: "flex", alignItems: "center",
                  justifyContent: "center",
                  zIndex: 1000, padding: 16 }}>
      <div style={{ width: "100%", maxWidth: 460,
                     background: "#16110d", color: "#F0EDE8",
                     border: "1px solid rgba(255,107,0,0.30)",
                     borderRadius: 8, padding: 22,
                     boxShadow: "0 18px 48px rgba(0,0,0,0.50)" }}>

        <div style={{ display: "flex", alignItems: "center", gap: 10,
                       marginBottom: 16 }}>
          <Rocket size={20} style={{ color: "#FF8C35" }} />
          <h3 style={{ margin: 0, fontSize: 17,
                        fontFamily: "'Cinzel', serif",
                        color: "#E8C86A" }}>
            Deploying to aurem.live
          </h3>
          <button onClick={onClose}
                  data-testid="deploy-progress-close"
                  style={{ marginLeft: "auto",
                           background: "transparent", border: "none",
                           color: "#a1958a", cursor: "pointer", padding: 4 }}>
            <X size={15} />
          </button>
        </div>

        {/* Stepper */}
        <div style={{ marginBottom: 18 }}>
          {STEPS.map((step, idx) => {
            const done   = idx <  stateRank || state === "live";
            const active = idx === stateRank && !failed && state !== "live";
            const isLive = step.id === "live" && state === "live";
            const cls    = isLive    ? "aurem-deploy-step done"
                          : done     ? "aurem-deploy-step done"
                          : active   ? "aurem-deploy-step active"
                                      : "aurem-deploy-step";
            return (
              <div key={step.id}
                   data-testid={`deploy-step-${step.id}`}
                   className={cls}>
                <span className="marker">
                  {isLive || done
                    ? <CheckCircle2 size={15}
                                     className={isLive ? "aurem-anim-pop" : ""} />
                    : active
                    ? <Loader2 size={15} className="aurem-anim-spin" />
                    : <span style={{ width: 8, height: 8, borderRadius: 999,
                                      background: "rgba(255,255,255,0.15)" }} />}
                </span>
                <span>{step.label}</span>
              </div>
            );
          })}
        </div>

        {/* Footer info */}
        {state !== "live" && !failed && (
          <div style={{ fontSize: 11, color: "#a1958a",
                         fontFamily: "'JetBrains Mono', monospace",
                         marginBottom: 12 }}>
            Polling /api/version on {targetUrl.replace(/^https?:\/\//, "")} ·
            elapsed {elapsed}s · target iter {expectedIter}
          </div>
        )}

        {state === "live" && (
          <div data-testid="deploy-progress-live"
               style={{ padding: 12, borderRadius: 6,
                        background: "rgba(74,222,128,0.08)",
                        border: "1px solid rgba(74,222,128,0.30)",
                        marginBottom: 12, fontSize: 13 }}>
            ✨ <strong>{version}</strong> is live on aurem.live —
            verified via /api/version.
          </div>
        )}

        {failed && (
          <div data-testid="deploy-progress-failed"
               style={{ padding: 12, borderRadius: 6,
                        background: "rgba(255,96,96,0.08)",
                        border: "1px solid rgba(255,96,96,0.30)",
                        marginBottom: 12, fontSize: 13, color: "#FF6060",
                        display: "flex", gap: 8, alignItems: "flex-start" }}>
            <AlertCircle size={15} style={{ flex: "0 0 15px",
                                              marginTop: 1 }} />
            <div>
              Deploy did not flip to <code>{expectedIter}</code> within 2
              minutes. {version ? <>Current live iter: <code>{version}</code>.</> : ""}
              {" "}Check the Hetzner restart / build logs.
            </div>
          </div>
        )}

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          {commitUrl && (
            <a href={commitUrl} target="_blank" rel="noreferrer"
                data-testid="deploy-progress-view-commit"
                style={{ padding: "8px 14px",
                         background: "rgba(255,107,0,0.10)",
                         border: "1px solid rgba(255,107,0,0.40)",
                         color: "#FF8C35", borderRadius: 4,
                         fontSize: 12, textDecoration: "none",
                         display: "inline-flex", alignItems: "center",
                         gap: 5 }}>
              commit {commitSha.slice(0, 7)} <ExternalLink size={11} />
            </a>
          )}
          {(state === "live" || failed) && (
            <button onClick={onClose}
                    data-testid="deploy-progress-done"
                    style={{ padding: "8px 16px",
                             background: state === "live"
                               ? "linear-gradient(135deg, #FF6B00, #FF8C35)"
                               : "rgba(255,255,255,0.04)",
                             color: state === "live" ? "#fff" : "#F0EDE8",
                             border: state === "live"
                               ? "none"
                               : "1px solid rgba(255,255,255,0.10)",
                             borderRadius: 4, fontSize: 13,
                             fontWeight: 500, cursor: "pointer" }}>
              {state === "live" ? "Done" : "Close"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
