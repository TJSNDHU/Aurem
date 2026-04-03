# OROÉ Design System
## Luxury Biotech Skincare | Polaris Built Inc.

Generated using ui-ux-pro-max design intelligence database.

---

## Brand Identity

| Attribute | Value |
|-----------|-------|
| Brand | OROÉ |
| Owner | Polaris Built Inc. |
| Target | 50+ premium skincare consumers |
| Positioning | Luxury biotech age reversal |
| Products | Age Reversal, BrightShield, ClearTech |

---

## Design Pattern

**Primary Style:** Dark Mode (OLED) + Liquid Glass
**Secondary Style:** Trust & Authority (for science sections)

### Style Rationale
- Dark Mode OLED: Deep black backgrounds convey luxury, reduce eye strain, highlight gold accents
- Liquid Glass: Morphing effects and iridescent gradients create premium feel
- Trust & Authority: Science/ingredients sections need credibility markers

---

## Color Tokens

### Core Palette (Obsidian + Warm Gold)

```css
:root {
  /* Backgrounds */
  --bg-deep: #020203;
  --bg-base: #050506;
  --bg-elevated: #0a0a0c;
  --bg-card: #0f0f11;
  
  /* Gold Accents */
  --gold-primary: #A16207;
  --gold-warm: #D4AF37;
  --gold-light: #F5DEB3;
  --gold-glow: rgba(212, 175, 55, 0.15);
  
  /* Text */
  --text-primary: #FFFFFF;
  --text-secondary: #A3A3A3;
  --text-muted: #6B6B6B;
  
  /* Borders */
  --border-subtle: rgba(255, 255, 255, 0.08);
  --border-gold: rgba(212, 175, 55, 0.3);
  
  /* Functional */
  --success: #22C55E;
  --warning: #F59E0B;
  --error: #EF4444;
}
```

### Product-Specific Accents

| Product | Accent Color | Usage |
|---------|--------------|-------|
| Age Reversal | Gold #D4AF37 | Premium hero, CTAs |
| BrightShield | Warm Ivory #F5DEB3 | Luminosity, highlights |
| ClearTech | Silver #C0C0C0 | Technology, precision |

---

## Typography

### Font Pairing: Luxury Minimalist

**Heading:** Bodoni Moda  
**Body:** Jost  

```css
@import url('https://fonts.googleapis.com/css2?family=Bodoni+Moda:wght@400;500;600;700&family=Jost:wght@300;400;500;600;700&display=swap');

:root {
  --font-display: 'Bodoni Moda', serif;
  --font-body: 'Jost', sans-serif;
}
```

### Type Scale

| Element | Font | Size | Weight | Tracking |
|---------|------|------|--------|----------|
| Hero H1 | Bodoni Moda | 72px / 4.5rem | 400 | -0.02em |
| Section H2 | Bodoni Moda | 48px / 3rem | 400 | -0.01em |
| Product H3 | Bodoni Moda | 32px / 2rem | 500 | 0 |
| Body | Jost | 18px / 1.125rem | 300 | 0.01em |
| Caption | Jost | 14px / 0.875rem | 400 | 0.05em |
| Button | Jost | 14px / 0.875rem | 500 | 0.1em |

---

## Section Structure

### Page Flow

1. **Hero** - Full viewport, video/image background, gold overlay
2. **Age Reversal** - Product showcase, left image / right content
3. **BrightShield** - Alternate layout, right image / left content
4. **ClearTech** - Tech-focused, grid layout
5. **Science/Ingredients** - Trust markers, certificates, clinical data
6. **Ritual** - How to use, step-by-step routine
7. **Footer** - Polaris Built Inc. attribution, legal

### Section Specifications

```
┌─────────────────────────────────────────────┐
│ HERO                                         │
│ height: 100vh                               │
│ background: video + overlay                 │
│ typography: Bodoni Moda 72px                │
│ CTA: gold border, uppercase Jost            │
├─────────────────────────────────────────────┤
│ PRODUCT SECTIONS                            │
│ padding: 120px 0                            │
│ max-width: 1200px                           │
│ layout: 50/50 split                         │
│ animation: fade-in on scroll               │
├─────────────────────────────────────────────┤
│ SCIENCE                                      │
│ background: --bg-elevated                   │
│ badges: certification icons                 │
│ metrics: animated counters                  │
├─────────────────────────────────────────────┤
│ RITUAL                                       │
│ layout: 3-column steps                      │
│ icons: gold stroke, no fill                 │
│ numbers: Bodoni Moda display                │
├─────────────────────────────────────────────┤
│ FOOTER                                       │
│ background: --bg-deep                       │
│ text: Polaris Built Inc.                    │
│ links: gold on hover                        │
└─────────────────────────────────────────────┘
```

---

## CTA Strategy

### Primary CTA
- Background: transparent
- Border: 1px solid var(--gold-warm)
- Text: uppercase, letter-spacing: 0.1em
- Hover: background var(--gold-glow), border var(--gold-warm)

### Secondary CTA
- Background: transparent
- Border: 1px solid var(--border-subtle)
- Text: var(--text-secondary)
- Hover: text var(--text-primary)

```css
.btn-primary {
  background: transparent;
  border: 1px solid var(--gold-warm);
  color: var(--gold-warm);
  padding: 16px 40px;
  font-family: var(--font-body);
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  transition: all 0.3s ease;
}

.btn-primary:hover {
  background: var(--gold-glow);
  box-shadow: 0 0 30px var(--gold-glow);
}
```

---

## Effects & Animation

### Scroll Animations
- Fade-in: opacity 0 → 1, translateY 30px → 0
- Duration: 600ms
- Easing: cubic-bezier(0.16, 1, 0.3, 1)
- Stagger: 100ms between elements

### Hover Effects
- Scale: 1.02 on product images
- Glow: box-shadow with gold-glow on CTAs
- Underline: animated width 0 → 100% on links

### Gold Glow Effect
```css
.gold-glow {
  box-shadow: 
    0 0 20px rgba(212, 175, 55, 0.1),
    0 0 40px rgba(212, 175, 55, 0.05);
}
```

---

## Anti-Patterns to Avoid

| ❌ Don't | ✅ Do |
|----------|-------|
| Pure white backgrounds | Deep black #020203 |
| Bright neon accents | Warm gold #D4AF37 |
| Sans-serif headlines | Serif display (Bodoni) |
| Rounded corners > 8px | Sharp or subtle radius |
| Cluttered layouts | Generous whitespace |
| Generic stock photos | Premium product photography |
| Pop-up modals on load | Scroll-triggered reveals |
| Autoplay video with sound | Muted ambient video |

---

## Accessibility Checklist

- [ ] Text contrast 7:1+ (WCAG AAA)
- [ ] Gold on dark: use #A16207 (not #D4AF37) for text
- [ ] Focus states visible (gold ring)
- [ ] Reduced motion media query
- [ ] Alt text on all product images
- [ ] Skip to content link

---

## Implementation Notes

### React Component Structure
```
/frontend/src/oroe/
├── pages/
│   └── OroeLanding.jsx
├── components/
│   ├── OroeHero.jsx
│   ├── ProductShowcase.jsx
│   ├── ScienceSection.jsx
│   ├── RitualSteps.jsx
│   └── OroeFooter.jsx
└── styles/
    └── oroe-design-system.css
```

### CSS Variables File
Create `/frontend/src/oroe/styles/oroe-design-system.css` with all tokens above.

### Brand Compliance
**CRITICAL:** All references must attribute to **Polaris Built Inc.**, never Reroots Aesthetics Inc.

---

*Generated with ui-ux-pro-max design intelligence*
