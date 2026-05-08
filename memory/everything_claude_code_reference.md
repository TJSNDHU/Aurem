# Everything Claude Code (ECC) - Reference for AUREM

> Source: https://github.com/affaan-m/everything-claude-code
> 141k Stars | 155 Contributors | MIT License
> Saved: February 2026

## What Is It?

ECC is the **agent harness performance optimization system** — a comprehensive toolkit of skills, instincts, memory, security, and research-first development patterns for AI coding agents. It works across Claude Code, Codex, OpenCode, Cursor, and Gemini CLI.

---

## Why It Matters for AUREM

ECC provides battle-tested architectural patterns for:
1. **Multi-Agent Orchestration** — Planner, Generator, Evaluator agents in a GAN-style feedback loop
2. **Skill-Based Workflows** — Reusable, composable workflows (TDD, security audit, e2e testing, deep research)
3. **Hook-Based Automation** — Event-driven hooks (pre/post tool use, file edits, session lifecycle)
4. **Cross-Platform Plugin Architecture** — Single codebase serves 5+ AI coding tools
5. **Token Optimization** — Strategies to reduce LLM costs by 60-70%
6. **Security-First Development** — Secret detection, MCP server pinning, sandbox configurations

---

## Core Components (Catalog: 47 Agents / 79 Commands / 180 Skills)

### Agents (Subagent Delegation)
Agents handle delegated tasks with limited scope and specific tool access.

| Agent | Purpose |
|-------|---------|
| `planner` | Creates implementation blueprints |
| `architect` | System architecture design |
| `tdd-guide` | Enforces test-driven development |
| `code-reviewer` | Quality, security, maintainability review |
| `build-error-resolver` | Fix failing builds |
| `e2e-runner` | End-to-end test generation |
| `security-reviewer` | OWASP Top 10 audit |
| `refactor-cleaner` | Dead code removal |
| `doc-updater` | Documentation updates |
| `go-reviewer` / `python-reviewer` / `typescript-reviewer` | Language-specific reviews |
| `database-reviewer` | Database query auditing |

### Skills (Primary Workflow Surface)
Skills are the most important component. They can be invoked directly, suggested automatically, and reused by agents.

**Key Skills Relevant to AUREM:**

| Skill | AUREM Application |
|-------|-------------------|
| `api-design` | REST API design patterns for our SaaS endpoints |
| `backend-patterns` | API design, database, caching strategies |
| `deep-research` | Multi-source research with synthesis (ORA AI co-pilot upgrade) |
| `e2e-testing` | Playwright E2E tests for platform QA |
| `eval-harness` | Eval-driven development for AI features |
| `frontend-patterns` | React/Next.js patterns for dashboard components |
| `security-review` | Comprehensive security checklist for multi-tenant SaaS |
| `tdd-workflow` | Test-driven development with 80%+ coverage |
| `verification-loop` | Build, test, lint, typecheck, security pipeline |
| `content-engine` | Platform-native social content (marketing features) |
| `mcp-server-patterns` | Build MCP servers with Node/TypeScript SDK |
| `strategic-compact` | Context window management for long AI sessions |
| `fal-ai-media` | Unified media generation (images, video, audio) |
| `investor-materials` | Decks, memos, models (for AUREM's business layer) |

### Hooks (Event-Driven Automation)
Hooks fire on tool events — pre/post execution guards.

| Hook Event | Use Case |
|------------|----------|
| `PreToolUse` | Block dangerous operations, detect secrets in prompts |
| `PostToolUse` | Auto-format code after edits, TypeScript checking |
| `SessionStart` | Initialize workspace, load context |
| `SessionEnd` | Cleanup, save session state |
| `beforeShellExecution` | Block dev servers outside tmux, git push review |
| `afterFileEdit` | Auto-format + console.log warning |
| `beforeSubmitPrompt` | Detect secrets (sk-, ghp_, AKIA patterns) |

### Rules (Always-Follow Guidelines)
Organized into `common/` (language-agnostic) + language-specific directories:
- `rules/common/` — Universal principles
- `rules/typescript/` — TS/JS patterns
- `rules/python/` — Python patterns
- `rules/golang/` — Go patterns

---

## Key Architectural Patterns

### 1. GAN-Style Generator-Evaluator Harness
Based on Anthropic's March 2026 harness design pattern:
- **Planner Agent** creates the blueprint
- **Generator Agent** writes the implementation
- **Evaluator Agent** reviews and provides adversarial feedback
- Creates a feedback loop producing production-quality applications

**AUREM Application:** Could power ORA AI's code generation or automated CRM workflow creation.

### 2. DRY Adapter Pattern (Cross-Platform Hooks)
A single set of hook scripts shared across Claude Code, Cursor, OpenCode via a thin adapter layer that transforms platform-specific JSON formats.

**AUREM Application:** If AUREM builds a developer-facing API or plugin system, this pattern ensures cross-platform compatibility.

### 3. Token Optimization Strategy
| Setting | Default | Recommended | Impact |
|---------|---------|-------------|--------|
| `model` | opus | sonnet | ~60% cost reduction |
| `MAX_THINKING_TOKENS` | 31,999 | 10,000 | ~70% reduction in thinking cost |
| `AUTOCOMPACT_PCT` | 95 | 50 | Better quality in long sessions |

**AUREM Application:** Direct cost savings for ORA AI chat and any LLM-powered features.

### 4. Multi-Agent Workflow
- Explorer (read-only evidence gathering)
- Reviewer (correctness + security review)
- Docs Researcher (API verification)

**AUREM Application:** ORA AI co-pilot could use a similar multi-agent pattern — one agent gathers CRM data, another analyzes it, a third generates recommendations.

---

## Cross-Tool Feature Parity Matrix

| Feature | Claude Code | Cursor | Codex | OpenCode |
|---------|------------|--------|-------|----------|
| Agents | 47 | Shared | Shared | 12 |
| Commands | 79 | Shared | Instruction-based | 31 |
| Skills | 180 | Shared | 10 | 37 |
| Hook Events | 8 | 15 | None | 11 |
| Rules | 34 | 34 | Instruction-based | 13 |
| MCP Servers | 14 | Shared | 7 | Full |

---

## Strategic Recommendations for AUREM Integration

### Immediate (P1)
- **Adopt `verification-loop` skill pattern** for AUREM's CI/CD pipeline (build -> test -> lint -> typecheck -> security)
- **Implement token optimization** settings for ORA AI to reduce LLM costs by 60%+
- **Use `security-review` checklist** for multi-tenant security audit

### Medium-Term (P2)
- **GAN-Style Harness** for ORA AI code/workflow generation — planner creates CRM automation blueprint, generator writes it, evaluator validates
- **Multi-Agent Pattern** for ORA AI co-pilot — parallel research + analysis + recommendation agents
- **Hook-based automation** for AUREM's API Gateway — pre/post execution guards, secret detection

### Long-Term (P3)
- **Cross-platform plugin architecture** if AUREM expands to developer-facing tools
- **Skill marketplace** — allow AUREM tenants to create and share custom automation skills
- **Content engine integration** for automated marketing content generation

---

## Installation Reference (For Developer Use)
```bash
# Clone
git clone https://github.com/affaan-m/everything-claude-code.git

# Quick install (Claude Code)
cd everything-claude-code && ./install.sh

# Manual install (selective)
cp -r agents/*.md ~/.claude/agents/
cp -r rules/common ~/.claude/rules/
cp -r skills/search-first ~/.claude/skills/

# Cursor
./install.sh --target cursor typescript

# Codex
npm install && bash scripts/sync-ecc-to-codex.sh
```

---

## Key Links
- **Repository:** https://github.com/affaan-m/everything-claude-code
- **Website:** https://ecc.tools
- **Shorthand Guide:** https://x.com/affaanmustafa/status/2012378465664745795
- **Longform Guide:** https://x.com/affaanmustafa/status/2014040193557471352
- **Security Guide:** https://github.com/affaan-m/everything-claude-code/blob/main/the-security-guide.md
