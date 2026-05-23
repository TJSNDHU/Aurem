# Frontend Portability Audit — iter 331c Sprint 6.3

Scanned `/app/frontend/src/` for hardcoded URLs, credentials, paths,
and Emergent-specific imports.

## Methodology

```bash
grep -rln "aurem.live|preview.emergentagent|emergentagent.com" /app/frontend/src/
grep -rln "sk_live_|sk_test_|whsec_|pk_live_|eyJ"             /app/frontend/src/
grep -rln "localhost:8001|127.0.0.1:8001"                     /app/frontend/src/
grep -rE  "https?://[a-z0-9.-]+\.(com|io|app|live|net|org)"   /app/frontend/src/
```

## Findings

### Hardcoded credentials in frontend
**ZERO.** No `sk_live_*`, `sk_test_*`, `whsec_*`, `pk_live_*`, JWT, or
bearer-token literal found anywhere in `/app/frontend/src/`. ✓

### Hardcoded API endpoints (the only real lock-in)
Three real findings; all fixed in iter 331c Sprint 6.3:

| File | Before | After |
|---|---|---|
| `platform/PublicStatus.jsx:139` | `"https://aurem.live/api/public/status/badge.json"` | Falls back to `REACT_APP_PUBLIC_BASE_URL` then `REACT_APP_BACKEND_URL` |
| `hooks/useAuth.js:9` | `host.includes('aurem.live') ? 'https://aurem.live' : process.env.REACT_APP_BACKEND_URL` | Same-origin detection works on ANY custom domain (no aurem.live in code) |
| `platform/luxe/LuxeV2Pages.jsx:162` | `useApi('/api/repair/scores?url=https://aurem.live', ...)` | Uses `REACT_APP_PUBLIC_BASE_URL` then `window.location.origin` |

### Hardcoded localhost references
Three files reference `localhost:8001` as documented preview-only
fallbacks. These are CORRECT — the comment block in `lib/api.js` explains
the same-origin-vs-preview switch. No fix needed.

### Hardcoded brand references (acceptable, not lock-in)
~45 files reference `aurem.live` in one of the following ways:

- `<a href="https://aurem.live">` — intentional brand link in marketing pages
- `<link rel="canonical" href="https://aurem.live/...">` — SEO requirement
- `mailto:ora@aurem.live` — contact addresses
- Comments mentioning `aurem.live` to document past bugs
- `placeholder="..."` text mentioning the brand
- `imageOptimization.js` `'https://aurem.live'` as the SSR default
  Open Graph image fallback

**None of these break portability.** A new domain operator updates the
brand strings as part of the rebrand, not as part of the migration.
The codebase ships AS-IS to a new domain and the API layer works
immediately.

### Emergent-specific imports
**ZERO.** No `from emergentintegrations` or `import emergent...`
anywhere in the frontend. ✓

### Hardcoded paths
**ZERO.** The frontend has no `/app/...` or `/var/...` references.
All paths are URL paths through the React router. ✓

### Third-party URLs (legitimate)
The following non-our-own URLs appear as expected:
- `res.cloudinary.com` — image proxy (env-configurable)
- `fonts.googleapis.com` — webfonts
- `youtube.com/embed` — embedded video
- `img.shields.io` — status badges
- `wikipedia.org`, `tailwindcss.com` — docs links

## Summary

| Category | Found | Fixed | Status |
|---|---|---|---|
| Hardcoded API endpoints | 3 | 3 | ✓ |
| Hardcoded credentials | 0 | 0 | ✓ already clean |
| Emergent imports | 0 | 0 | ✓ already clean |
| Hardcoded `/app` paths | 0 | 0 | ✓ already clean |
| Brand references (acceptable) | ~45 | 0 (n/a) | ✓ acceptable |

**Verdict: AUREM frontend is portable.** To move to a new domain:

1. Set `REACT_APP_BACKEND_URL=https://your-new-domain.example.com`
2. Set `REACT_APP_PUBLIC_BASE_URL=https://your-new-domain.example.com` (optional, overrides for status badges + repair API)
3. (Optional rebrand) Replace `aurem.live` strings in marketing pages
   with your new domain. Pure cosmetic — does not affect functionality.

The same-origin detection in `hooks/useAuth.js` and `lib/api.js` means
the deployed app routes `/api/*` through the K8s ingress automatically
on any custom domain. No code changes needed for the API surface.

## Files Modified This Audit

- `/app/frontend/src/platform/PublicStatus.jsx` (1 line)
- `/app/frontend/src/hooks/useAuth.js` (1-line → 11-line block w/ proper detection)
- `/app/frontend/src/platform/luxe/LuxeV2Pages.jsx` (1 line)

Zero production functionality changed. Three API-endpoint fallbacks
hardened from `aurem.live`-only to env-driven.

## Env Vars Added

| Var | Purpose | Default |
|---|---|---|
| `REACT_APP_PUBLIC_BASE_URL` | Same-origin override for status badges / repair scans (NEW; optional) | (none — falls back to `REACT_APP_BACKEND_URL`) |

Update `MIGRATION_CHECKLIST.md` and `ORA_PORTABLE_MANIFEST.md` to
include `REACT_APP_PUBLIC_BASE_URL` as an optional addition.
