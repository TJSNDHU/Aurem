# React + FastAPI

The AUREM CTO default stack. Used by 9/10 customers shipping a product
landing + dashboard + a small REST API.

  - `api/`: FastAPI (Python 3.11), routes prefixed `/api/*`.
  - `ui/`: React (CRA + craco), reverse-proxied by Caddy in front.
  - `mongo`: MongoDB 7 with named volume.

Ports: ui=3000, api=8001, mongo=27017. Deploy command stays identical
across all stacks: `git pull && docker compose up -d --build`.

## AUREM Design System (mandatory, pre-installed)

Every React project AUREM CTO scaffolds ships with these libraries
already in `package.json`:

  - **sonner** — toasts (`import { toast } from "sonner"`).
    Replace every `alert()` / `confirm()` / `window.confirm()` with
    `toast.success()` / `toast.error()` / `toast.loading()` /
    `toast.promise()`. Mount `<Toaster />` once at the app root.
  - **vaul** — mobile drawers / bottom-sheets (`import { Drawer } from "vaul"`).
    Use it instead of full-screen modals on mobile. Bake the iOS
    drawer easing curve into CSS: `--ease-drawer: cubic-bezier(0.32, 0.72, 0, 1);`
  - **lucide-react** — every icon. Never emoji as icons, never raw SVG
    when a lucide icon exists.

Global CSS rules already in `ui/src/styles/aurem-design.css`:

```css
:root {
  --ease-out:    cubic-bezier(0.23, 1, 0.32, 1);
  --ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
  --ease-drawer: cubic-bezier(0.32, 0.72, 0, 1);
}
button, .button, [role="button"] {
  transition: transform 160ms var(--ease-out);
}
button:active, .button:active, [role="button"]:active {
  transform: scale(0.97);
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

Animation rules every component generated for this stack MUST follow:

  - Animate ONLY `transform` and `opacity`.
  - Use `ease-out` (or the custom curve above) — NEVER `ease-in`.
  - Duration < 300 ms for UI; longer only for marketing/explanatory.
  - Never animate from `scale(0)` — start `scale(0.95) + opacity 0`.
  - Popovers use `transform-origin: var(--radix-popover-content-transform-origin)`,
    modals stay `center`.
  - Stagger lists 30-80 ms between items.

