# ReRoots Performance Maintenance Guide

## 🎯 Current Performance Status
- **Mobile Score**: 80-90+ (target)
- **Desktop Score**: 90-95+ (target)
- **LCP**: < 2.5s
- **CLS**: 0
- **INP**: < 200ms

---

## 🚨 Critical Rules (DO NOT BREAK)

### 1. Hero Image
```
NEVER change these without performance review:
- Preload hint in index.html
- fetchpriority="high" attribute
- Cloudinary CDN routing (res.cloudinary.com)
- aspect-ratio: 16/9 on hero container
```

### 2. JavaScript Budget
```
Current Homepage JS: ~150KB (gzipped)
Budget: 200KB max

If adding a feature:
- Add 50KB? → Find 50KB to lazy-load elsewhere
- New dependency? → Check bundle size first (bundlephobia.com)
```

### 3. Image Rules
```
✅ DO:
- Upload to Cloudinary for auto-optimization
- Use srcset for responsive images
- Add width/height attributes (prevents CLS)
- Use loading="lazy" for below-fold images

❌ DON'T:
- Upload raw images > 500KB
- Use loading="lazy" on hero image
- Skip the Cloudinary CDN
```

---

## 📦 Bundle Optimization

### Lazy-Loaded (Good - Keep these lazy)
- Admin components (InfluencerManager, TeamManager, etc.)
- framer-motion (via LazyMotion)
- Secondary pages (LaVela, Oroe, BrandShowcase)
- Chat widget (initializes on click only)

### Bundled (Critical - Keep these in main bundle)
- React core
- React Router
- Tailwind CSS
- Lucide icons (tree-shaken)

---

## 🖼️ Image Guidelines

### Cloudinary URL Format
```
https://res.cloudinary.com/ddpphzqdg/image/fetch/w_{WIDTH},q_auto,f_auto/{ENCODED_URL}
```

### Recommended Sizes
- Hero: 1920w (desktop), 1024w (tablet), 640w (mobile)
- Product cards: 400w
- Thumbnails: 200w

### Format Priority
1. AVIF (best compression)
2. WebP (good fallback)
3. JPEG (universal fallback)

---

## 🔤 Font Guidelines

### Self-Hosted Fonts (DO NOT ADD GOOGLE FONTS)
```css
/* Fonts are loaded via @fontsource packages */
@import '@fontsource/playfair-display/400.css';
@import '@fontsource/manrope/400.css';
```

### If Adding a New Font
1. Install via @fontsource: `yarn add @fontsource/[font-name]`
2. Import only needed weights
3. Update this guide

---

## ⚡ Animation Guidelines

### INP Optimization
```javascript
// For below-fold animations, use requestIdleCallback
if ('requestIdleCallback' in window) {
  requestIdleCallback(() => startAnimation());
}
```

### Framer Motion
- Use `<LazyMotion features={domAnimation}>` (NOT full motion)
- Use `m.div` instead of `motion.div`
- Add `viewport={{ once: true }}` to prevent re-animations

---

## 🔍 Performance Testing Checklist

Before deploying new features:

- [ ] Run PageSpeed Insights (mobile + desktop)
- [ ] Check bundle size with `yarn build && yarn analyze`
- [ ] Verify no new Google Fonts requests (Network tab)
- [ ] Test INP with Chrome DevTools (Performance tab, 6x CPU slowdown)
- [ ] Verify CLS = 0 (no layout shifts)

---

## 🛠️ Useful Commands

```bash
# Check bundle size
cd frontend && yarn build && du -sh build/static/js/*.js

# Find large dependencies
npx source-map-explorer build/static/js/*.js

# Test API response times
curl -w "Time: %{time_total}s\n" -o /dev/null -s https://reroots.ca/api/products
```

---

## 📊 Third-Party Script Rules

### PostHog Analytics
- Deferred 2 seconds after page load
- DO NOT move to immediate loading

### Future: Partytown
If adding more analytics (FB Pixel, GTM), use Partytown to run in Web Worker.

---

## 🚀 Quick Wins (If Score Drops)

1. **LCP slow?** → Check hero image is using Cloudinary
2. **TBT high?** → Look for synchronous imports that should be lazy
3. **CLS > 0?** → Add width/height to images, aspect-ratio to containers
4. **INP > 200ms?** → Use requestIdleCallback for animations

---

## 📞 Contact

For performance questions, check:
- `/app/memory/PRD.md` - Product requirements
- This guide - Performance rules
- PageSpeed Insights - Current metrics

Last Updated: February 2026
