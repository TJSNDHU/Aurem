/**
 * SaveToGithubDialog.jsx — iter D-47
 *
 * Modal dialog that lists the user's GitHub repos + branches and
 * commits the current project's manifest.json + chat history markdown
 * to the chosen target. The OAuth/PAT token saved via D-42 powers
 * every GitHub API call server-side.
 */
import React, { useEffect, useState } from "react";
import { X, Github, CheckCircle2, ExternalLink, AlertCircle,
         Loader2, Rocket } from "lucide-react";
import { devAuthHeaders } from "./DeveloperShell";
import { pushVerifyEvent, useVerifyRows, canShowDeploy } from "./VerificationBadge"; // iter D-52
import "./DevCtoChatPanel.animations.css";              // iter D-51

const API = process.env.REACT_APP_BACKEND_URL || "";


export default function SaveToGithubDialog({ open, projectId, onClose,
                                              onDeployRequested }) {
  // step: "pick" → "saving" → "pushing" → "success" | "error"
  const [step, setStep]       = useState("pick");
  const [repos, setRepos]     = useState(null);
  const [branches, setBranches] = useState(null);
  const [repo, setRepo]       = useState("");
  const [branch, setBranch]   = useState("");
  const [message, setMessage] = useState("Save from AUREM CTO chat");
  const [result, setResult]   = useState(null);
  const [err, setErr]         = useState(null);
  // iter D-51 — push animation drives progress 0→100 over ~1.5s as the
  // GitHub commit POST resolves. Auto-dismiss timer fires 3s after success.
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (!open) return;
    setStep("pick"); setResult(null); setErr(null);
    setRepos(null); setBranches(null); setRepo(""); setBranch("");
    setProgress(0);
    fetch(`${API}/api/developers/github/repos`,
            { headers: devAuthHeaders() })
      .then(r => r.ok ? r.json() : r.json().then(j => Promise.reject(j)))
      .then(j => setRepos(j.items || []))
      .catch(j => setErr(j?.detail || "Could not list repos. "
                                     + "Connect GitHub on /developers/connect first."));
  }, [open]);

  useEffect(() => {
    if (!repo) { setBranches(null); return; }
    const r = repos?.find(x => x.full_name === repo);
    if (!r) return;
    setBranches(null); setBranch(r.default_branch || "main");
    fetch(`${API}/api/developers/github/repos/${r.owner}/${r.name}/branches`,
            { headers: devAuthHeaders() })
      .then(x => x.ok ? x.json() : x.json().then(j => Promise.reject(j)))
      .then(j => {
        setBranches(j.items || []);
        if (j.items?.some(b => b.name === (r.default_branch || "main"))) {
          setBranch(r.default_branch || "main");
        } else if (j.items?.[0]) {
          setBranch(j.items[0].name);
        }
      })
      .catch(j => setErr(j?.detail || "Could not list branches."));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repo]);

  async function commit() {
    setStep("saving"); setErr(null); setProgress(0);
    // iter D-51 — animated progress: jump to 35% on send, 75% on roundtrip
    // start, 100% on success. Also fires the D-52 verification badge.
    pushVerifyEvent("github", { status: "checking",
                                  detail: `pushing to ${repo}` });
    setTimeout(() => setProgress(35), 50);
    try {
      const [owner, name] = repo.split("/");
      setProgress(60);
      const r = await fetch(`${API}/api/developers/github/commit`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body: JSON.stringify({
          owner, repo: name, branch, project_id: projectId, message,
        }),
      });
      setProgress(85);
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "commit_failed");

      // iter D-52 — verify the commit ACTUALLY landed on GitHub before
      // we paint green. We don't trust the commit endpoint's local
      // response; we re-read from the GitHub API.
      let verified = j;
      try {
        const vr = await fetch(`${API}/api/developers/cto/verify/github`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...devAuthHeaders() },
          body: JSON.stringify({
            owner, repo: name, branch,
            expected_sha: j.commit_sha || "",
          }),
        });
        const vj = await vr.json();
        if (vj.found) {
          verified = { ...j, verified_sha: vj.sha,
                        verified_url: vj.url || j.view_url };
          pushVerifyEvent("github", {
            status: "green",
            detail: `commit ${vj.short_sha}`,
            url:    vj.url || j.view_url,
          });
        } else {
          // Push endpoint claimed success but GitHub doesn't see it
          // (token scope issue, branch protection, etc.) — show RED.
          pushVerifyEvent("github", {
            status: "red",
            detail: vj.error || "commit not found on GitHub",
          });
        }
      } catch {
        pushVerifyEvent("github", { status: "red",
                                      detail: "verify probe failed" });
      }

      setProgress(100);
      setResult(verified); setStep("success");
    } catch (e) {
      pushVerifyEvent("github", { status: "red",
                                    detail: String(e.message || e) });
      setErr(String(e.message || e)); setStep("error");
    }
  }

  if (!open) return null;

  return (
    <div data-testid="save-to-github-dialog"
         role="dialog" aria-modal="true"
         style={{ position: "fixed", inset: 0,
                  background: "rgba(0,0,0,0.50)",
                  display: "flex", alignItems: "center",
                  justifyContent: "center",
                  zIndex: 999, padding: 16 }}>
      <div style={{ width: "100%", maxWidth: 520,
                     background: "#16110d", color: "#F0EDE8",
                     border: "1px solid rgba(255,255,255,0.10)",
                     borderRadius: 8, padding: 20,
                     boxShadow: "0 18px 48px rgba(0,0,0,0.40)" }}>

        {step === "pick" || step === "saving" ? (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 10,
                           marginBottom: 14 }}>
              <Github size={18} style={{ color: "#FF8C35" }} />
              <h3 style={{ margin: 0, fontSize: 16,
                            fontFamily: "'Cinzel', serif",
                            color: "#E8C86A" }}>
                Save to GitHub
              </h3>
              <button onClick={onClose}
                      data-testid="save-to-github-close"
                      style={{ marginLeft: "auto",
                               background: "transparent", border: "none",
                               color: "#a1958a", cursor: "pointer", padding: 4 }}>
                <X size={15} />
              </button>
            </div>
            <p style={{ fontSize: 12, color: "#a1958a", marginBottom: 14 }}>
              Commits <code>aurem/{projectId}/manifest.json</code> and
              {" "}<code>aurem/{projectId}/aurem-chat.md</code> to the
              repo and branch you pick. The OAuth token from your
              Connect page is used server-side.
            </p>

            {/* Account row */}
            <div style={{ display: "flex", alignItems: "center", gap: 8,
                           padding: "8px 10px", borderRadius: 4,
                           background: "rgba(74,222,128,0.06)",
                           border: "1px solid rgba(74,222,128,0.20)",
                           marginBottom: 14 }}>
              <span style={{ width: 6, height: 6, borderRadius: 999,
                              background: "#4ade80" }} />
              <span style={{ fontSize: 12 }}>
                GitHub account connected
              </span>
            </div>

            {/* Repo dropdown */}
            <label style={{ display: "block", fontSize: 11,
                             letterSpacing: 0.6,
                             textTransform: "uppercase",
                             color: "#a1958a", marginBottom: 6 }}>
              Select repo
            </label>
            <select data-testid="save-github-repo-select"
                    value={repo}
                    onChange={e => setRepo(e.target.value)}
                    disabled={!repos || step === "saving"}
                    style={{ width: "100%", padding: "9px 10px",
                             background: "rgba(255,255,255,0.04)",
                             border: "1px solid rgba(255,255,255,0.10)",
                             color: "#F0EDE8", borderRadius: 4,
                             fontFamily: "'JetBrains Mono', monospace",
                             fontSize: 12, marginBottom: 12,
                             outline: "none" }}>
              <option value="">{repos === null ? "Loading repos…"
                                                : repos.length
                                                  ? "— choose a repo —"
                                                  : "No repos found"}</option>
              {(repos || []).map(r => (
                <option key={r.full_name} value={r.full_name}>
                  {r.full_name}{r.private ? "  (private)" : ""}
                </option>
              ))}
            </select>

            {/* Branch dropdown */}
            <label style={{ display: "block", fontSize: 11,
                             letterSpacing: 0.6,
                             textTransform: "uppercase",
                             color: "#a1958a", marginBottom: 6 }}>
              Select branch
            </label>
            <select data-testid="save-github-branch-select"
                    value={branch}
                    onChange={e => setBranch(e.target.value)}
                    disabled={!repo || !branches || step === "saving"}
                    style={{ width: "100%", padding: "9px 10px",
                             background: "rgba(255,255,255,0.04)",
                             border: "1px solid rgba(255,255,255,0.10)",
                             color: "#F0EDE8", borderRadius: 4,
                             fontFamily: "'JetBrains Mono', monospace",
                             fontSize: 12, marginBottom: 12,
                             outline: "none" }}>
              {!branches && repo && (
                <option value="">Loading branches…</option>
              )}
              {(branches || []).map(b => (
                <option key={b.name} value={b.name}>{b.name}</option>
              ))}
            </select>

            <label style={{ display: "block", fontSize: 11,
                             letterSpacing: 0.6,
                             textTransform: "uppercase",
                             color: "#a1958a", marginBottom: 6 }}>
              Commit message
            </label>
            <input data-testid="save-github-message"
                    value={message}
                    onChange={e => setMessage(e.target.value)}
                    disabled={step === "saving"}
                    style={{ width: "100%", padding: "9px 10px",
                             background: "rgba(255,255,255,0.04)",
                             border: "1px solid rgba(255,255,255,0.10)",
                             color: "#F0EDE8", borderRadius: 4,
                             fontFamily: "inherit",
                             fontSize: 12, marginBottom: 12,
                             outline: "none", boxSizing: "border-box" }} />

            {err && (
              <div data-testid="save-github-error"
                   style={{ padding: 10, marginBottom: 12,
                            background: "rgba(255,96,96,0.10)",
                            border: "1px solid rgba(255,96,96,0.30)",
                            borderRadius: 4, color: "#FF6060", fontSize: 12,
                            display: "flex", gap: 8, alignItems: "center" }}>
                <AlertCircle size={13} /> {err}
              </div>
            )}

            <div style={{ display: "flex", gap: 8,
                           justifyContent: "flex-end", marginTop: 6 }}>
              <button onClick={onClose}
                      data-testid="save-github-cancel"
                      disabled={step === "saving"}
                      style={{ padding: "8px 16px",
                               background: "rgba(255,255,255,0.04)",
                               border: "1px solid rgba(255,255,255,0.10)",
                               color: "#F0EDE8", borderRadius: 4,
                               fontSize: 13, cursor: "pointer" }}>
                Cancel
              </button>
              <button onClick={commit}
                      data-testid="save-github-save"
                      disabled={!repo || !branch || step === "saving"}
                      style={{ padding: "8px 16px",
                               background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
                               color: "#fff", border: "none", borderRadius: 4,
                               fontSize: 13, fontWeight: 500,
                               cursor: (!repo || !branch || step === "saving")
                                 ? "not-allowed" : "pointer",
                               opacity: (!repo || !branch || step === "saving") ? 0.5 : 1,
                               display: "inline-flex", alignItems: "center", gap: 6 }}>
                {step === "saving"
                  ? <><Loader2 size={13} className="aurem-anim-spin" /> Pushing…</>
                  : <><Github size={13} /> Save to Github</>}
              </button>
            </div>
            {step === "saving" && (
              <div data-testid="save-github-progress"
                   className="aurem-anim-progress"
                   style={{ marginTop: 14 }}>
                <span className="fill"
                       style={{ transform: `scaleX(${progress / 100})` }} />
              </div>
            )}
          </>
        ) : step === "success" ? (
          <SuccessCelebration result={result}
                               onClose={onClose}
                               onDeployRequested={onDeployRequested} />
        ) : (
          <div data-testid="save-github-error-state"
                style={{ textAlign: "center", padding: "12px 4px" }}>
            <AlertCircle size={42}
                          style={{ color: "#FF6060", marginBottom: 10 }} />
            <h3 style={{ margin: "0 0 8px", fontSize: 15,
                          color: "#FF6060" }}>
              Save failed
            </h3>
            <p style={{ fontSize: 13, color: "#a1958a",
                         margin: "0 0 14px" }}>
              {err}
            </p>
            <button onClick={() => setStep("pick")}
                    style={{ padding: "8px 16px",
                             background: "rgba(255,255,255,0.04)",
                             border: "1px solid rgba(255,255,255,0.10)",
                             color: "#F0EDE8", borderRadius: 4,
                             fontSize: 13, cursor: "pointer" }}>
              Try again
            </button>
          </div>
        )}
      </div>
    </div>
  );
}


/* ──────────────────────────────────────────────────────────────────
 * SuccessCelebration — iter D-51
 *
 * Animated "code pushed!" panel rendered inside the same modal. Shows:
 *   • Big checkmark with pop animation
 *   • Confetti burst (8 dots flying outward)
 *   • Real commit SHA + view link
 *   • Orange Deploy CTA button — when clicked, fires
 *     `onDeployRequested(result)` so the parent can open the
 *     DeployProgressDialog. The dialog auto-fades 3s if neither button
 *     is clicked.
 * ────────────────────────────────────────────────────────────────── */
function SuccessCelebration({ result, onClose, onDeployRequested }) {
  const [fadingOut, setFadingOut] = useState(false);
  // iter D-52a — Deploy CTA is GATED on the verification rows. Until
  // GitHub verify flips to GREEN (real commit confirmed by GitHub API),
  // the button stays hidden. If any row goes RED, the button never
  // appears. Founder mandate: no fake deploys.
  const verifyRows = useVerifyRows();
  const deployAllowed = canShowDeploy(verifyRows);

  // 3-second auto-dismiss — disabled if user is hovering or has clicked
  // the deploy button (we let the deploy dialog take over).
  useEffect(() => {
    const t = setTimeout(() => setFadingOut(true), 3000);
    const t2 = setTimeout(() => { try { onClose && onClose(); } catch {} },
                           3500);
    return () => { clearTimeout(t); clearTimeout(t2); };
  }, [onClose]);

  const sha = (result?.verified_sha || result?.commit_sha || "").slice(0, 9);
  const url = result?.verified_url || result?.view_url || "";

  // 8 confetti dots scattered around — radial offsets in px.
  const dots = [
    { x:  -60, y: -50, c: "#FF8C35" },
    { x:   60, y: -50, c: "#E8C86A" },
    { x:  -80, y:  10, c: "#4ade80" },
    { x:   80, y:  10, c: "#FF6B00" },
    { x:  -40, y:  60, c: "#FFC857" },
    { x:   40, y:  60, c: "#4ade80" },
    { x:    0, y: -80, c: "#FF8C35" },
    { x:    0, y:  80, c: "#E8C86A" },
  ];

  return (
    <div data-testid="save-github-success"
         className={fadingOut ? "aurem-anim-fade-out" : "aurem-anim-pop"}
         style={{ textAlign: "center", padding: "16px 4px",
                  position: "relative" }}>
      {/* Confetti layer */}
      <div style={{ position: "absolute", inset: 0,
                     pointerEvents: "none", overflow: "visible" }}>
        {dots.map((d, i) => (
          <span key={i}
                className="aurem-anim-confetti-dot"
                style={{ background: d.c,
                         ["--cx"]: `${d.x}px`,
                         ["--cy"]: `${d.y}px` }} />
        ))}
      </div>

      <CheckCircle2 size={56}
                     className="aurem-anim-pop"
                     style={{ color: "#4ade80", marginBottom: 10 }} />
      <h3 style={{ margin: "0 0 6px",
                    fontFamily: "'Cinzel', serif",
                    fontSize: 19, color: "#E8C86A" }}>
        Code pushed to GitHub!
      </h3>
      <p style={{ fontSize: 13, color: "#a1958a",
                   margin: "0 0 6px" }}>
        <code>{result?.owner}/{result?.repo}</code>
        {" "}on branch <code>{result?.branch}</code>
      </p>
      {sha && (
        <div data-testid="save-github-commit-sha"
             style={{ fontSize: 11, color: "#a1958a",
                       fontFamily: "'JetBrains Mono', monospace",
                       marginBottom: 14 }}>
          commit <strong style={{ color: "#FF8C35" }}>{sha}</strong>
        </div>
      )}
      <div style={{ display: "flex", gap: 8,
                     justifyContent: "center", flexWrap: "wrap" }}>
        {url && (
          <a href={url} target="_blank" rel="noreferrer"
              data-testid="save-github-view-link"
              style={{ padding: "8px 16px",
                       background: "rgba(255,107,0,0.10)",
                       border: "1px solid rgba(255,107,0,0.40)",
                       color: "#FF8C35", borderRadius: 4,
                       fontSize: 13, textDecoration: "none",
                       display: "inline-flex", alignItems: "center", gap: 6 }}>
            View on GitHub <ExternalLink size={11} />
          </a>
        )}
        {onDeployRequested && deployAllowed && (
          <button onClick={() => onDeployRequested(result)}
                  data-testid="save-github-deploy-cta"
                  style={{ padding: "8px 16px",
                           background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
                           color: "#fff", border: "none", borderRadius: 4,
                           fontSize: 13, fontWeight: 500,
                           cursor: "pointer",
                           display: "inline-flex", alignItems: "center",
                           gap: 6 }}>
            <Rocket size={14} /> Deploy to aurem.live
          </button>
        )}
        {onDeployRequested && !deployAllowed && (
          <div data-testid="save-github-deploy-blocked"
               style={{ padding: "8px 14px", fontSize: 12,
                        color: "#a1958a",
                        background: "rgba(255,255,255,0.04)",
                        border: "1px solid rgba(255,255,255,0.08)",
                        borderRadius: 4 }}>
            Deploy unlocks once GitHub verification turns ✅ GREEN
          </div>
        )}
      </div>
    </div>
  );
}
