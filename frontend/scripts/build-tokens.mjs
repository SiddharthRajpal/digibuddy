// Regenerates src/styles/tokens.css from design/tokens.json (the design system's export).
// Usage: npm run tokens
import { readFileSync, writeFileSync } from "node:fs";

const t = JSON.parse(readFileSync(new URL("../design/tokens.json", import.meta.url), "utf8"));
const day = [];
const night = [];
const fixed = [];

for (const c of t.color.tokens) {
  day.push(`  --${c.name}: ${c.value.daylight};`);
  night.push(`  --${c.name}: ${c.value.lamplight};`);
}
for (const s of t.shadow.tokens) {
  day.push(`  --${s.name}: ${s.value.daylight};`);
  night.push(`  --${s.name}: ${s.value.lamplight};`);
}
for (const k of ["spacing", "radius", "duration"]) {
  for (const s of t[k].tokens) fixed.push(`  --${s.name}: ${s.value};`);
}
const fam = t.type.families;
fixed.push(`  --font-display: var(--font-grandstander), ${fam.display};`);
fixed.push(`  --font-body: var(--font-literata), ${fam.body};`);
fixed.push(`  --font-hand: var(--font-gaegu), ${fam.hand};`);

const famVar = { display: "--font-display", body: "--font-body", hand: "--font-hand" };
const classes = [];
for (const g of t.type.groups) {
  for (const st of g.styles) {
    const lines = [
      `  font-family: var(${famVar[g.family]});`,
      `  font-size: ${st.fontSize};`,
      `  line-height: ${st.lineHeight};`,
      `  font-weight: ${st.fontWeight};`,
    ];
    if (st.letterSpacing) lines.push(`  letter-spacing: ${st.letterSpacing};`);
    if (st.name === "caption" || st.name === "number-xl") lines.push("  font-variant-numeric: tabular-nums;");
    classes.push(`.t-${st.name} {\n${lines.join("\n")}\n}`);
  }
}

const css = `/*
 * DigiBuddy Storybook design tokens.
 * Generated from the design system's tokens.json. Do not edit by hand:
 * update the design system and regenerate.
 *
 * Themes: Daylight (default) and Lamplight (reading at night).
 * Lamplight applies with [data-theme="lamplight"], or with the system dark
 * preference when the user picked "Match my device" ([data-theme="system"]).
 */

:root {
${fixed.join("\n")}
}

:root,
[data-theme="daylight"] {
  color-scheme: light;
${day.join("\n")}
}

[data-theme="lamplight"] {
  color-scheme: dark;
${night.join("\n")}
}

@media (prefers-color-scheme: dark) {
  [data-theme="system"] {
    color-scheme: dark;
${night.map((l) => "  " + l).join("\n")}
  }
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --flip-duration: 0ms;
    --press-duration: 0ms;
  }
}

/* Type styles */
${classes.join("\n\n")}
`;

writeFileSync(new URL("../src/styles/tokens.css", import.meta.url), css);
console.log("wrote src/styles/tokens.css");
