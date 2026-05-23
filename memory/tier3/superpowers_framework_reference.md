# Superpowers — Agentic Skills Framework Reference for AUREM

> Source: https://github.com/obra/superpowers
> 136k Stars | By Jesse Vincent (Prime Radiant) | MIT License | v5.0.7
> Saved: February 2026
> STATUS: USER DIRECTIVE — "Work as per this from now"

## What Is It?

Superpowers is a **complete software development workflow for coding agents** — a composable "skills" framework that enforces structured development methodology. Instead of agents jumping into code, they follow a mandatory pipeline: brainstorm → spec → plan → TDD implementation → review → merge.

---

## Core Workflow (Mandatory Pipeline)

| Step | Skill | What Happens |
|------|-------|-------------|
| 1 | **brainstorming** | Agent asks what you're really trying to do. Refines ideas through questions. Presents design in digestible chunks for validation. |
| 2 | **using-git-worktrees** | Creates isolated workspace on new branch. Runs setup. Verifies clean test baseline. |
| 3 | **writing-plans** | Breaks work into bite-sized tasks (2-5 min each). Every task has exact file paths, complete code, verification steps. |
| 4 | **subagent-driven-development** | Dispatches fresh subagent per task with two-stage review (spec compliance → code quality). |
| 5 | **test-driven-development** | Enforces RED-GREEN-REFACTOR: write failing test → watch it fail → write minimal code → watch it pass → commit. |
| 6 | **requesting-code-review** | Reviews against plan, reports issues by severity. Critical issues block progress. |
| 7 | **finishing-a-development-branch** | Verifies tests, presents options (merge/PR/keep/discard), cleans up. |

**Key principle:** The agent checks for relevant skills before any task. These are mandatory workflows, not suggestions.

---

## Skills Library

### Testing
- **test-driven-development** — RED-GREEN-REFACTOR cycle (includes testing anti-patterns reference)

### Debugging
- **systematic-debugging** — 4-phase root cause process (root-cause-tracing, defense-in-depth, condition-based-waiting)
- **verification-before-completion** — Ensure it's actually fixed before declaring success

### Collaboration
- **brainstorming** — Socratic design refinement
- **writing-plans** — Detailed implementation plans
- **executing-plans** — Batch execution with checkpoints
- **dispatching-parallel-agents** — Concurrent subagent workflows
- **requesting-code-review** — Pre-review checklist
- **receiving-code-review** — Responding to feedback
- **using-git-worktrees** — Parallel development branches
- **finishing-a-development-branch** — Merge/PR decision workflow
- **subagent-driven-development** — Fast iteration with two-stage review

### Meta
- **writing-skills** — Create new skills following best practices
- **using-superpowers** — Introduction to the skills system

---

## Philosophy (AUREM Must Adopt)

1. **Test-Driven Development** — Write tests first, always
2. **Systematic over ad-hoc** — Process over guessing
3. **Complexity reduction** — Simplicity as primary goal
4. **Evidence over claims** — Verify before declaring success
5. **YAGNI** — You Aren't Gonna Need It
6. **DRY** — Don't Repeat Yourself

---

## Cross-Platform Support
- Claude Code (official plugin marketplace)
- Cursor (plugin marketplace)
- Codex (manual install)
- OpenCode (manual install)
- GitHub Copilot CLI
- Gemini CLI

---

## How AUREM Should Apply Superpowers Methodology

### For ORA AI Co-Pilot Development
- Enforce brainstorming skill before any new feature implementation
- Use subagent-driven-development for parallel task execution
- Every ORA AI response should follow systematic-debugging for troubleshooting

### For Platform Development
- All new features go through: brainstorm → plan → TDD → review → merge
- Use dispatching-parallel-agents for independent module development
- Verification-before-completion on every bug fix

### For Agent Orchestration
- Two-stage review pattern (spec compliance → code quality) for all automated workflows
- Bite-sized tasks (2-5 min) with exact file paths and verification steps
- Git worktrees for isolated feature development

---

## Key Links
- Repository: https://github.com/obra/superpowers
- Blog: https://blog.fsck.com/2025/10/09/superpowers/
- Discord: https://discord.gg/Jd8Vphy9jq
- Prime Radiant: https://primeradiant.com/
