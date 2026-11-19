// tokens.json -> tokens.css, by the Glacier rules (08-Implementation, "Sources of truth"):
// colour and shadow per theme (first theme on :root, the others under [data-theme="<id>"]),
// every other family as :root variables, --font-<key> from type.families, aliases {name} -> var(--name).
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const t = JSON.parse(readFileSync(join(here, 'tokens.json'), 'utf8'));
const themes = t.color.themes.map((x) => x.id);
const first = themes[0];
const NAME = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/;
const COLOR = /^(#[0-9a-fA-F]{3,8}|(rgb|rgba|hsl|hsla|oklch|oklab|lab|lch)\([^()]*\))$/;
const colorNames = new Set(t.color.tokens.map((x) => x.name));

const val = (v) => String(v).replace(/^\{([^}]+)\}$/, (_, n) => `var(--${n})`);
const perTheme = (tok) => {
  const v = typeof tok.value === 'object' && tok.value !== null ? tok.value : { [first]: tok.value };
  const out = {};
  for (const th of themes) out[th] = v[th] ?? v[first];
  return out;
};
const problems = [];
const checkColor = (name, v) => {
  const s = String(v);
  const alias = s.match(/^\{([^}]+)\}$/);
  if (alias) { if (!colorNames.has(alias[1]) || alias[1] === name) problems.push(`${name}: alias of missing token ${s}`); return; }
  if (!COLOR.test(s)) problems.push(`${name}: unreadable colour ${s}`);
};

const blocks = Object.fromEntries(themes.map((th) => [th, []]));
const seen = new Set();
for (const fam of ['color', 'shadow']) {
  for (const tok of t[fam]?.tokens ?? []) {
    if (!NAME.test(tok.name) || seen.has(tok.name)) { problems.push(`bad or duplicate name ${tok.name}`); continue; }
    seen.add(tok.name);
    const v = perTheme(tok);
    for (const th of themes) {
      if (fam === 'color') checkColor(tok.name, v[th]);
      blocks[th].push(`  --${tok.name}: ${val(v[th])};`);
    }
  }
}
const plain = [];
for (const [fam, body] of Object.entries(t)) {
  if (['name', 'version', 'color', 'shadow', 'type', 'meta'].includes(fam) || !body?.tokens) continue;
  for (const tok of body.tokens) {
    if (!NAME.test(tok.name) || seen.has(tok.name)) { problems.push(`bad or duplicate name ${tok.name}`); continue; }
    seen.add(tok.name);
    plain.push(`  --${tok.name}: ${val(tok.value)};`);
  }
}
for (const [k, stack] of Object.entries(t.type.families)) plain.push(`  --font-${k}: ${stack};`);

if (problems.length) { console.error('tokens.json problems:\n' + problems.join('\n')); process.exit(1); }

const dark = themes.find((x) => x === 'dark');
let css = `/* ${t.name} — generated from tokens.json by build.mjs. Do not edit. */\n`;
css += `:root {\n  color-scheme: light;\n${blocks[first].join('\n')}\n${plain.join('\n')}\n}\n`;
for (const th of themes.slice(1)) {
  css += `:root[data-theme="${th}"] {\n  color-scheme: ${th === 'dark' ? 'dark' : 'light'};\n${blocks[th].join('\n')}\n}\n`;
}
if (dark) {
  // Without JavaScript the theme script cannot run: follow the reader's system setting.
  css += `@media (prefers-color-scheme: dark) {\n  :root:not([data-theme]) {\n    color-scheme: dark;\n${blocks[dark].map((l) => '  ' + l).join('\n')}\n  }\n}\n`;
}
writeFileSync(join(here, 'tokens.css'), css);
console.log(`tokens.css: ${seen.size} tokens, themes ${themes.join(', ')}`);
