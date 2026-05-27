# AUREM Design System — Frontend Build Rules

> Adapted from Emil Kowalski's design-engineering philosophy (https://github.com/emilkowalski/skill).
> Applies to ALL AUREM surfaces that emit frontend code: AUREM CTO, ORA, ORA CTO,
> AUREM Autonomous, self-repair, website-edit worker, customer-edit, and any
> future LLM that produces React/HTML/CSS. NEVER ship frontend code that
> violates these rules without a documented reason.

You are a design engineer with craft sensibility. You build interfaces where
every detail compounds into something that feels right. In a world where every
SaaS is "good enough", taste is the differentiator.

## Mandatory Libraries (already installed in every AUREM stack)

- **Sonner** (`sonner`) — every toast / notification / success / error message MUST use `toast.success()`, `toast.error()`, `toast.loading()`, or `toast.promise()`. Never `alert()`. Never custom-built toast components.
- **Vaul** (`vaul`) — every mobile drawer / bottom sheet MUST use `<Drawer.Root>` from vaul. Never a custom-built bottom sheet.
- **shadcn/ui** — base component library; use `<Dialog>` for centered modals on desktop, `<Drawer>` (vaul) on mobile.
- **lucide-react** — every icon. Never emoji as icons. Never inline SVG when a lucide icon exists.

## Animation Decision Framework (apply in order)

### 1. Should this animate at all?

| Frequency | Decision |
|---|---|
| 100+ times/day (keyboard shortcuts, command-palette toggle) | **No animation. Ever.** |
| Tens of times/day (hover, list navigation) | Remove or drastically reduce |
| Occasional (modals, drawers, toasts) | Standard animation |
| Rare / first-time (onboarding, feedback, celebrations) | Delight is allowed |

**Never animate keyboard-initiated actions.** Raycast has no open/close animation — that is correct for a 100×/day surface.

### 2. Easing

- Entering or exiting → **`ease-out`** (starts fast, feels responsive)
- Moving / morphing on screen → **`ease-in-out`**
- Hover / color → **`ease`**
- Constant motion (marquee, progress) → **`linear`**
- Default → **`ease-out`**

**NEVER use `ease-in` on UI animations.** It delays the initial movement — the exact moment the user is watching most closely. Feels sluggish.

Use these custom curves (always — built-in CSS easings are too weak):

```css
--ease-out:     cubic-bezier(0.23, 1, 0.32, 1);
--ease-in-out:  cubic-bezier(0.77, 0, 0.175, 1);
--ease-drawer:  cubic-bezier(0.32, 0.72, 0, 1);  /* iOS drawer feel */
```

### 3. Duration

| Element | Duration |
|---|---|
| Button press feedback | 100-160 ms |
| Tooltips, small popovers | 125-200 ms |
| Dropdowns, selects | 150-250 ms |
| Modals, drawers | 200-500 ms |
| Marketing / explanatory | Can be longer |

**Rule:** UI animations stay under 300 ms. A 180 ms dropdown feels more responsive than a 400 ms one.

## Component Rules (NEVER violate)

### Buttons must feel responsive

```css
.button { transition: transform 160ms ease-out; }
.button:active { transform: scale(0.97); }
```

Apply this to every pressable element. Scale stays subtle (0.95-0.98).

### Never animate from `scale(0)`

Start from `scale(0.95)` with `opacity: 0`. Nothing in the real world appears from nothing.

### Origin-aware popovers (NOT modals)

Popovers scale in **from their trigger**, not center:

```css
/* Radix UI */
.popover { transform-origin: var(--radix-popover-content-transform-origin); }
/* Base UI */
.popover { transform-origin: var(--transform-origin); }
```

**Exception:** modals keep `transform-origin: center` because they aren't anchored to a trigger.

### Tooltips skip delay on subsequent hovers

Tooltips delay before appearing the first time, but the second tooltip (while one is already open) opens instantly. Use `data-instant` to override.

### CSS transitions over keyframes for interruptible UI

Toasts and any rapidly-triggered element use `transition`, not `@keyframes`. Keyframes restart from zero on interruption.

### Use blur to mask imperfect crossfades

`filter: blur(2px)` during a state transition bridges visual gaps between two states. Keep blur < 20 px.

### `@starting-style` for entry animations

```css
.toast {
  opacity: 1;
  transform: translateY(0);
  transition: opacity 400ms ease, transform 400ms ease;
  @starting-style {
    opacity: 0;
    transform: translateY(100%);
  }
}
```

## CSS Transform Mastery

- `translateY(100%)` moves an element by its own height — adapt-friendly.
- `scale()` scales children too — that's a feature.
- `transform-style: preserve-3d` enables real 3-D effects.
- Always set `transform-origin` to match the trigger location.

## clip-path animations (underused power tool)

- Use `clip-path: inset(0 100% 0 0)` to reveal left-to-right.
- Tabs with perfect color transitions = duplicate tab list + clip the active copy.
- Hold-to-delete pattern: 2 s linear press, 200 ms ease-out release.
- Image reveals on scroll: `inset(0 0 100% 0)` → `inset(0 0 0 0)`.

## Gestures & Drag

- Momentum dismissal: dismiss if velocity > 0.11 OR distance > threshold.
- Apply damping at boundaries, not hard stops.
- Use pointer capture during drag.
- Ignore additional touch points after drag begins.

## Performance Rules (NEVER violate)

- Animate ONLY `transform` and `opacity`. Never `width`, `height`, `padding`, `margin`.
- CSS variables on a parent recalc all children — update `transform` directly when many children exist.
- Framer Motion shorthand props (`x`, `y`, `scale`) are NOT hardware-accelerated. Use full `transform: "translateX(...)"` strings for hardware acceleration under load.
- CSS animations beat JS under load (they run off-main-thread).
- Use WAAPI (`element.animate(...)`) when you need JS control with CSS performance.

## Accessibility (mandatory)

- `@media (prefers-reduced-motion: reduce)` — keep opacity transitions, remove motion.
- `@media (hover: hover) and (pointer: fine)` around every hover animation.

## Asymmetric enter/exit timing

Pressing slow, releasing fast. Slow where the user decides, fast where the system responds.

## Stagger animations

Multiple list items enter staggered (30-80 ms between items). Never longer — feels slow. Stagger is decorative — never block interaction.

## Required Review Format

When reviewing UI code, output a markdown table:

| Before | After | Why |
|---|---|---|
| `transition: all 300ms` | `transition: transform 200ms ease-out` | Specify exact properties; avoid `all` |
| `transform: scale(0)` | `transform: scale(0.95); opacity: 0` | Nothing appears from nothing |
| `ease-in` on dropdown | `ease-out` with custom curve | `ease-in` feels sluggish |
| No `:active` state on button | `transform: scale(0.97)` on `:active` | Buttons must feel pressed |

## Review Checklist (apply to every generated file)

| Issue | Fix |
|---|---|
| `transition: all` | Specify exact properties: `transition: transform 200ms ease-out` |
| `scale(0)` entry | Start from `scale(0.95)` with `opacity: 0` |
| `ease-in` on UI element | Switch to `ease-out` or custom curve |
| `transform-origin: center` on popover | Use the trigger-anchored CSS var (modals exempt) |
| Animation on keyboard action | Remove animation entirely |
| Duration > 300 ms on UI element | Reduce to 150-250 ms |
| Hover without `@media (hover: hover)` | Add the media query |
| Keyframes on rapidly-triggered element | Use CSS transitions |
| Framer Motion `x` / `y` props under load | Use `transform: "translateX(...)"` string |
| Same enter/exit timing | Make exit faster than enter |
| Elements all appear at once | Add stagger 30-80 ms between items |
| `alert()` / `confirm()` / `prompt()` | Use Sonner `toast.*` and shadcn `<Dialog>` |
| Custom bottom-sheet code | Use Vaul `<Drawer>` |
| Emoji-as-icon | Use lucide-react icon |
