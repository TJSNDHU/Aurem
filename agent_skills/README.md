# AUREM Agent Skills

These are reference skills for **Emergent** (the build agent), sourced from
[antigravity-awesome-skills](https://github.com/sickn33/antigravity-awesome-skills).
They are NOT for ORA's sales / outreach runtime — that lives in `/ora_skills/`.

## When to use

Consult these when building AUREM features:

| Skill | Use when |
|---|---|
| `@senior-fullstack`            | adding or touching React + FastAPI components |
| `@backend-dev-guidelines`      | writing new API handlers, services, or schedulers |
| `@security-auditor`            | before any auth / JWT / permission change |
| `@cc-skill-security-review`    | final security checklist before merge |
| `@test-driven-development`     | introducing a new pytest suite |
| `@api-design-principles`       | adding or versioning a public endpoint |
| `@react-patterns`              | designing a new React page / component tree |
| `@multi-agent-patterns`        | A2A agent architecture / skill-router decisions |
| `@startup-founder`             | product scope, pricing, or priority calls |

## Layout
- `senior-fullstack.md` — React + FastAPI end-to-end patterns
- `backend-dev-guidelines.md` — Python / Node API service patterns
- `security-auditor.md` — JWT, auth flows, timing attacks
- `cc-skill-security-review.md` — pre-merge security checklist
- `test-driven-development.md` — pytest TDD workflow
- `api-design-principles.md` — REST API best practices
- `react-patterns.md` — React idioms and anti-patterns
- `multi-agent-patterns.md` — A2A agent coordination
- `startup-founder.md` — product-manager toolkit

## Sourcing note
The full library (~1441 skills, ~4497 SKILL.md files) is cloned to `.agent/skills/`
and **gitignored**. Only the curated subset above is committed under
`/app/agent_skills/`.

Refresh: `git -C /app/.agent/skills pull --depth=1`
