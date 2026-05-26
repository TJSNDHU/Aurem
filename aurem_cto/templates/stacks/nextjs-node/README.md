# Next.js + Node

Single-container stack. Next.js App Router serves UI + API routes at
`/api/*`. MongoDB sidecar for state.

  - Best for: SaaS landings + dashboards + thin APIs.
  - Tradeoff: heavier cold start than React+FastAPI, but one deploy unit.
