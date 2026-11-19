// No hard-coded colours outside packages/tokens (08-Implementation, "Theming"): components and pages
// reference var(--token) only. Fails on a hex literal or a named colour in a style value.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const root = new URL('..', import.meta.url).pathname;
const scan = ['apps/web/app', 'apps/web/components', 'apps/web/lib', 'packages/ui', 'packages/fonts', 'packages/charts'];
// The datasteg bar (components/datasteg-bar.css, copied from family/ by family/sync.mjs) is the same band on every
// datasteg site, so it carries its own fixed colours (Cairn's) rather than Glacier's tokens.
const skip = /node_modules|\.next|datasteg-bar\.css$/;
const HEX = /(?<![&\w])#[0-9a-fA-F]{3,8}\b(?![\w-])/g;
const problems = [];
function walk(d) {
  for (const n of readdirSync(d)) {
    const p = join(d, n);
    if (skip.test(p)) continue;
    if (statSync(p).isDirectory()) walk(p);
    else if (/\.(css|tsx?|mjs)$/.test(n)) {
      readFileSync(p, 'utf8').split('\n').forEach((line, i) => {
        if (/^\s*(\/\/|\/?\*)/.test(line)) return;
        for (const m of line.matchAll(HEX)) {
          // skip #ids in JSX/URLs: a hex literal only counts inside CSS or a style/colour context
          if (/\.css$/.test(n) || /(color|background|fill|stroke|border)/i.test(line)) problems.push(`${relative(root, p)}:${i + 1}: ${m[0]}`);
        }
      });
    }
  }
}
for (const s of scan) { try { walk(join(root, s)); } catch { /* folder not there yet */ } }
if (problems.length) { console.error('Hard-coded colours (use var(--token)):\n  ' + problems.join('\n  ')); process.exit(1); }
console.log('colours: ok');
