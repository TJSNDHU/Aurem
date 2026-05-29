# SPEC 04 — UI / UX Design Brief

> Read fifth. Updated 2026-05-28, iter D-57.

## Design intent

AUREM looks like a **command terminal that respects the founder's
expertise** — Emil Kowalski-inspired editorial darkness with a single
sovereign accent (gold + orange). Never AI-slop pastel gradients,
never centered hero stacks, never generic SaaS cards.

## Brand vocabulary

- **Sovereign Black** — primary background.
- **Founder Gold (`#E8C86A`)** — section headings, brand wordmarks.
- **AUREM Orange (`#FF6B00 → #FF8C35`)** — interactive accents,
  primary CTA gradients.
- **Phantom Beige (`#F0EDE8`)** — body text on dark.
- **Stone Gray (`#a1958a`)** — muted labels, timestamps.
- **State colors** — `#4ade80` (green/success), `#FFC857` (amber/checking),
  `#FF6060` (red/error).

## Color palette (canonical)

```
--dash-bg            #0F0F1A     (charcoal blue-black)
--dash-surface       #16110d     (deep brown-black for dialogs)
--dash-border        rgba(255,255,255,0.10)
--dash-divider       rgba(255,255,255,0.06)
--dash-text          #F0EDE8
--dash-text-muted    #a1958a
--dash-gold          #E8C86A
--dash-orange        #FF6B00
--dash-orange-2      #FF8C35
--dash-green         #4ade80
--dash-amber         #FFC857
--dash-red           #FF6060
```

## Typography

| Use                                    | Font                              | Size           | Weight |
|---|---|---|---|
| Brand wordmark / dialog titles         | Cinzel (serif)                    | 17–22 px       | 500    |
| Section labels (small caps)            | JetBrains Mono                    | 10–11 px       | 500    |
| Body                                   | system-ui / Inter (we vary)       | 13–14 px       | 400    |
| Code / SHAs / timestamps               | JetBrains Mono                    | 10–11 px       | 400    |
| Mobile body                            | text-sm                           | 12 px          | 400    |

**Banned**: Roboto, Arial, default system "casual" sans, Comic-style
fonts, anything that looks like an AI-generated landing page.

## Component style

- **Buttons (primary)** — `linear-gradient(135deg, #FF6B00, #FF8C35)`
  + white text + 4 px radius.
- **Buttons (secondary)** — `rgba(255,255,255,0.04)` + 1 px border
  `var(--dash-border)`.
- **Pills / badges** — pill-shaped (border-radius 999 px) with 1 px
  tinted border + 10 % alpha background.
- **Cards / panels** — 1 px divider borders, NO drop shadows on the
  surfaces (we use shadow only on overlays / modals).
- **Modals** — 8 px radius, `#16110d` surface, `1 px solid
  rgba(255,107,0,0.30)` border, 18 px shadow.
- **Inputs / textareas** — `rgba(255,255,255,0.04)` background, 1 px
  border, 13 px text, no focus glow — just border color change.
- **Icons** — `lucide-react` only. Never emoji icons. Sizes 10–16 px.

## Layout rules

- **Left-aligned by default.** Centered hero stacks are banned.
- **2–3× more spacing** than feels comfortable.
- **Asymmetric ratios** for headers (3 / 2 split, not 1 / 1).
- **Grid is forbidden for content rows** — use flex with explicit gaps.
- **Hard divider lines (1 px)** between every major section instead of
  shadows or rounded cards.
- **Sticky composer at bottom** on chat surfaces.

## Mobile (≤ 768 px) rules — D-50 + D-57

- Stack composer textarea ABOVE the action row.
- Action row height = 52 px; textarea min-height = 44 px.
- Save-to-Github label hidden, icon only.
- Planning-bar chips → horizontal scroll, no wrap; hide scrollbar.
- `env(safe-area-inset-bottom)` added to composer padding for iPhone notch.
- ORA help bubble → hidden entirely (`isMobileViewport()` short-circuit).
- HotLeadsBar (D-57) → `overflow-x: auto; white-space: nowrap`.

## Motion (D-51)

- Animations only on `opacity` + `transform` (never `all`).
- `aurem-spin` — loading spinners (1 s linear infinite).
- `aurem-pop` — checkmark + celebration (0.45 s cubic-bezier
  `(.2, .9, .3, 1.4)`).
- `aurem-confetti` — 8 dots with random `--cx` / `--cy` offsets,
  0.9 s ease-out.
- `aurem-anim-progress` — gradient fill scaleX 0 → 1, transition 0.35 s.
- `aurem-fade-out` — 0.4 s ease-out for auto-dismiss panels.
- Steppers: yellow ⏳ Loader2 spin → green ✅ CheckCircle2 with
  `aurem-anim-pop`.

## Cursor + selection

- Selection color → `rgba(255,107,0,0.32)`.
- Pointer cursor on every clickable surface (`button`, `a`, role pills).

## Dashboard layout convention

```
┌──────────────────────────────────────────────┐
│ Sidebar (collapsible, 56 px collapsed)       │
├───────────┬──────────────────────────────────┤
│           │  HotLeadsBar  (auto-hide)       │
│  Sidebar  │  VerificationBadge (auto-hide)  │
│           │  ConfidenceBadge  (auto-hide)   │
│           │  Chat scroll area               │
│           │  PlanningBar (horizontal)       │
│           │  Composer (sticky bottom)       │
└───────────┴──────────────────────────────────┘
        Optional right drawer: CodebaseMap (D-55)
```

## Tone of voice (Rule Zero)

- 1–3 sentences in chat. No JSON. No tracebacks. No code dumps.
- Use Hinglish when the founder uses Hinglish.
- Brutal honesty over optimism — "blast 12 attempted, 0 delivered
  (WHAPI disabled)" > "blast sent ✅".
- Always end with one concrete next step or one tasteful enhancement
  suggestion. Never end with a question that the agent could have
  answered itself.

## "AI slop" things we never do

- Purple → pink gradients on white.
- Centered hero with floating phone mockup.
- Inter / Roboto everywhere.
- Equal-spacing card grids of 3 with shadows.
- Vague tagline "AI-powered platform for the future of business".
- Emoji icons inline (`🚀💡🤖`) — use `lucide-react` instead.
- Auto-generated avatar placeholders ("U", "A").
- "Try AUREM today!" CTAs — say what they will get instead.

## Accessibility minimums

- Color contrast AA on body text (white-on-dash-bg = 14.2 : 1).
- `data-testid` on every interactive element + every user-facing
  status indicator (per project rules).
- Focus rings — 2 px outline `#FF8C35` for keyboard users.
- ARIA labels on icon-only buttons.
- Modals with `role="dialog"` + `aria-modal="true"`.

## References

- Emil Kowalski (emilkowalski.com) — typography + spacing + motion.
- Linear (linear.app) — focused command-bar feel.
- Stripe Sigma (sigma.stripe.com) — terminal-style data density.
- Vercel dashboard — quiet dark gray surfaces, no shadows.
