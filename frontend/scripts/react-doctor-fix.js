#!/usr/bin/env node
/* eslint-disable no-console */
/**
 * react-doctor codemod — `yarn react-doctor:fix`
 *
 * Mechanical, repo-wide auto-fix for the safest high-volume react-doctor
 * rule violations. Pure string transforms — no AST, no Babel — because the
 * target patterns are unambiguous and visiting every JSX node would 10x
 * the runtime on a 337-file codebase.
 *
 * Rules handled:
 *   1. design-no-redundant-size-axes  (1970 hits)
 *      Tailwind: `w-N h-N` → `size-N`  (and the `h-N w-N` flip).
 *      Only fires when both axes match exactly. Skips arbitrary values
 *      like `w-[14px] h-[14px]` — Tailwind v3.4 doesn't shorthand those.
 *
 *   2. design-no-three-period-ellipsis  (87 hits)
 *      Replace literal "..." inside JSX text nodes (between `>` and `<`)
 *      with the proper Unicode ellipsis "…". Never touches code, strings,
 *      or template literals — only text the user sees.
 *
 *   3. design-no-em-dash-in-jsx-text  (248 hits)
 *      Replace " — " (space + em-dash + space) inside JSX text nodes
 *      with ", " — the safe mechanical default per the react-doctor help
 *      text. Only fires in JSX prose, never in code or strings.
 *
 * Run on the same file set react-doctor scans (everything under src/).
 * Idempotent — running twice produces zero additional changes.
 *
 * Usage: yarn react-doctor:fix         # in-place
 *        yarn react-doctor:fix --dry   # report only, no writes
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', 'src');
const DRY = process.argv.includes('--dry');
const EXTS = new Set(['.js', '.jsx', '.ts', '.tsx']);

/* ------------------------------ rule 1 ------------------------------ */

// Match `w-N` and `h-N` where N is the SAME token. Tailwind size tokens:
// digits (5), digit+fraction (1/2), `px`, `0`, `auto`, `full`, `screen`,
// `min`, `max`, `fit`. We only collapse safe overlap (size-N supports a
// subset). Keep the regex tight to avoid false positives.
const SIZE_TOKENS = String.raw`(?:0|px|auto|full|screen|min|max|fit|\d+(?:\.\d+)?(?:\/\d+)?)`;

// Within a className token list, find adjacent `w-X` `h-X` (or reverse).
// We allow whitespace OR responsive/state prefix variants on BOTH sides
// only if identical (e.g. `md:w-5 md:h-5` — same prefix). Cross-variant
// pairs (`w-5 md:h-5`) are NOT collapsed.
function collapseSizeAxes(content) {
  let n = 0;
  // Variant prefix: anything ending with ":" repeated — e.g. `md:`, `hover:md:`.
  const VARIANT = String.raw`((?:[a-z0-9-]+:)*)`;
  const reWH = new RegExp(
    `${VARIANT}w-(${SIZE_TOKENS})\\s+\\1h-\\2(?![\\w-])`,
    'g',
  );
  const reHW = new RegExp(
    `${VARIANT}h-(${SIZE_TOKENS})\\s+\\1w-\\2(?![\\w-])`,
    'g',
  );
  let out = content.replace(reWH, (_, v, sz) => {
    n += 1;
    return `${v}size-${sz}`;
  });
  out = out.replace(reHW, (_, v, sz) => {
    n += 1;
    return `${v}size-${sz}`;
  });
  return { out, n };
}

/* ------------------------------ rule 2 ------------------------------ */

// Replace `...` with `…` ONLY inside JSX text nodes: i.e. between a
// closing `>` and an opening `<`, with NO newlines, NO operators that
// could indicate the `>` is a comparison, and the body must look like
// short JSX prose. We deliberately skip:
//   - JS string literals ("loading...")
//   - Spread operators (`{...props}`, `[...arr, ...arr]`)
//   - Comments
//   - Inline expressions {`...`}
//   - Any `>` that is actually `>=` / `=>` / `>>` / a comparison
function fixEllipsisInJsxText(content) {
  let n = 0;
  // Strict JSX text run: must START on the SAME line as the `>` and END
  // before any `{`, `}`, newline, or another `<`. The opening `>` must
  // be preceded by an identifier or quote (real JSX close), not a comparison.
  const re = /([)A-Za-z0-9"'\]])>([^<>{}\n]{0,300}?)</g;
  const out = content.replace(re, (whole, pre, body) => {
    if (!body.includes('...')) return whole;
    const replaced = body.replace(/(\w|\s)\.{3}(?!\.)/g, (m, p) => {
      n += 1;
      return `${p}…`;
    });
    return `${pre}>${replaced}<`;
  });
  return { out, n };
}

/* ------------------------------ rule 3 ------------------------------ */

// Em-dash in JSX prose → comma. Same strict JSX-text safety net as the
// ellipsis fix: opening `>` must follow a real JSX-close marker (id /
// quote / `)` / `]`), no newlines, no curly braces. We collapse ` — `
// (space-dash-space) → `, `; bare `—` (no surrounding spaces) is rare
// in real prose and skipped.
function fixEmDashInJsxText(content) {
  let n = 0;
  const re = /([)A-Za-z0-9"'\]])>([^<>{}\n]{0,300}?)</g;
  const out = content.replace(re, (whole, pre, body) => {
    if (body.indexOf(' — ') === -1) return whole;
    const replaced = body.replace(/ — /g, () => {
      n += 1;
      return ', ';
    });
    return `${pre}>${replaced}<`;
  });
  return { out, n };
}

/* ------------------------------ walker ------------------------------ */

function walk(dir, files = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.')) continue;
    if (entry.name === 'node_modules' || entry.name === 'build') continue;
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(p, files);
    else if (EXTS.has(path.extname(entry.name))) files.push(p);
  }
  return files;
}

(function main() {
  if (!fs.existsSync(ROOT)) {
    console.error(`[react-doctor:fix] src/ not found at ${ROOT}`);
    process.exit(1);
  }
  const files = walk(ROOT);
  let totalSize = 0;
  let totalEll = 0;
  let totalEm = 0;
  let touched = 0;

  for (const f of files) {
    const src = fs.readFileSync(f, 'utf8');
    const r1 = collapseSizeAxes(src);
    const r2 = fixEllipsisInJsxText(r1.out);
    const r3 = fixEmDashInJsxText(r2.out);
    const next = r3.out;
    if (next !== src) {
      touched += 1;
      totalSize += r1.n;
      totalEll += r2.n;
      totalEm += r3.n;
      if (!DRY) fs.writeFileSync(f, next, 'utf8');
    }
  }

  console.log('[react-doctor:fix] summary');
  console.log(`  files scanned : ${files.length}`);
  console.log(`  files changed : ${touched}${DRY ? ' (dry-run)' : ''}`);
  console.log(`  size-axes rewrites : ${totalSize}`);
  console.log(`  ellipsis rewrites  : ${totalEll}`);
  console.log(`  em-dash rewrites   : ${totalEm}`);
  if (DRY) console.log('  --dry: no files written.');
})();
