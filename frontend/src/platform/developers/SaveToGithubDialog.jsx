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
         Loader2 } from "lucide-react";
import { devAuthHeaders } from "./DeveloperShell";

const API = process.env.REACT_APP_BACKEND_URL || "";


export default function SaveToGithubDialog({ open, projectId, onClose }) {
  // step: "pick" → "saving" → "success" | "error"
  const [step, setStep]       = useState("pick");
  const [repos, setRepos]     = useState(null);
  const [branches, setBranches] = useState(null);
  const [repo, setRepo]       = useState("");
  const [branch, setBranch]   = useState("");
  const [message, setMessage] = useState("Save from AUREM CTO chat");
  const [result, setResult]   = useState(null);
  const [err, setErr]         = useState(null);

  useEffect(() => {
    if (!open) return;
    setStep("pick"); setResult(null); setErr(null);
    setRepos(null); setBranches(null); setRepo(""); setBranch("");
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
    setStep("saving"); setErr(null);
    try {
      const [owner, name] = repo.split("/");
      const r = await fetch(`${API}/api/developers/github/commit`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body: JSON.stringify({
          owner, repo: name, branch, project_id: projectId, message,
        }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "commit_failed");
      setResult(j); setStep("success");
    } catch (e) { setErr(String(e.message || e)); setStep("error"); }
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
                  ? <><Loader2 size={13} className="aurem-spin" /> Saving…</>
                  : <><Github size={13} /> Save to Github</>}
              </button>
            </div>
          </>
        ) : step === "success" ? (
          <div data-testid="save-github-success"
                style={{ textAlign: "center", padding: "12px 4px" }}>
            <Github size={48}
                    style={{ color: "#FF8C35", marginBottom: 10 }} />
            <h3 style={{ margin: "0 0 6px",
                          fontFamily: "'Cinzel', serif",
                          fontSize: 18, color: "#E8C86A" }}>
              Successfully saved to GitHub!
            </h3>
            <p style={{ fontSize: 13, color: "#a1958a",
                         margin: "0 0 14px" }}>
              <code>{result?.owner}/{result?.repo}</code>
              {" "}on branch{" "}
              <code>{result?.branch}</code>
            </p>
            {result?.commit_sha && (
              <div style={{ fontSize: 11, color: "#a1958a",
                             fontFamily: "'JetBrains Mono', monospace",
                             marginBottom: 14 }}>
                commit {result.commit_sha.slice(0, 9)}
              </div>
            )}
            <div style={{ display: "flex", gap: 8,
                           justifyContent: "center" }}>
              <a href={result?.view_url} target="_blank" rel="noreferrer"
                  data-testid="save-github-view-link"
                  style={{ padding: "8px 16px",
                           background: "rgba(255,107,0,0.10)",
                           border: "1px solid rgba(255,107,0,0.40)",
                           color: "#FF8C35", borderRadius: 4,
                           fontSize: 13, textDecoration: "none",
                           display: "inline-flex", alignItems: "center", gap: 6 }}>
                View on GitHub <ExternalLink size={11} />
              </a>
              <button onClick={onClose}
                      data-testid="save-github-okay-got-it"
                      style={{ padding: "8px 16px",
                               background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
                               color: "#fff", border: "none", borderRadius: 4,
                               fontSize: 13, fontWeight: 500,
                               cursor: "pointer",
                               display: "inline-flex", alignItems: "center", gap: 6 }}>
                <CheckCircle2 size={13} /> Okay got it
              </button>
            </div>
          </div>
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
