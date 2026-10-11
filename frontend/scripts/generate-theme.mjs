// Generates src/theme/palette.css: the colour tokens behind Tailwind's palette classes.
//
// Tailwind colour utilities (bg-*, text-*, border-*) are mapped in tailwind.config.js to
// CSS variables with *separate* scales per role, so one class can mean "tinted surface"
// as a background and "readable tint" as text in each theme. Light values are
// Tailwind's defaults; dark values are a navy/charcoal design (not an inversion):
// tinted surfaces stay dark, solid fills stay saturated (white text remains readable),
// and coloured text moves to light tints.
//
// Run: node scripts/generate-theme.mjs   (from frontend/)
import { writeFileSync, mkdirSync } from 'node:fs';

const STEPS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950];

const LIGHT = {
  slate: ['#f8fafc', '#f1f5f9', '#e2e8f0', '#cbd5e1', '#94a3b8', '#64748b', '#475569', '#334155', '#1e293b', '#0f172a', '#020617'],
  red: ['#fef2f2', '#fee2e2', '#fecaca', '#fca5a5', '#f87171', '#ef4444', '#dc2626', '#b91c1c', '#991b1b', '#7f1d1d', '#450a0a'],
  amber: ['#fffbeb', '#fef3c7', '#fde68a', '#fcd34d', '#fbbf24', '#f59e0b', '#d97706', '#b45309', '#92400e', '#78350f', '#451a03'],
  emerald: ['#ecfdf5', '#d1fae5', '#a7f3d0', '#6ee7b7', '#34d399', '#10b981', '#059669', '#047857', '#065f46', '#064e3b', '#022c22'],
  blue: ['#eff6ff', '#dbeafe', '#bfdbfe', '#93c5fd', '#60a5fa', '#3b82f6', '#2563eb', '#1d4ed8', '#1e40af', '#1e3a8a', '#172554'],
  purple: ['#faf5ff', '#f3e8ff', '#e9d5ff', '#d8b4fe', '#c084fc', '#a855f7', '#9333ea', '#7e22ce', '#6b21a8', '#581c87', '#3b0764'],
};

// Dark theme, per role. Arrays follow STEPS.
const DARK_BG = {
  slate: ['#121c2e', '#172338', '#1e2c45', '#293a58', '#3a4d70', '#56698c', '#2c3d5c', '#24344f', '#1b2840', '#0d1626', '#080e19'],
  red: ['#2a121a', '#391621', '#4b1c29', '#6a2433', '#f87171', '#ef4444', '#dc2626', '#c42a2a', '#a11f1f', '#7f1d1d', '#3a0b0e'],
  amber: ['#281d0b', '#37280c', '#4a3510', '#6a4a12', '#fbbf24', '#f59e0b', '#d97706', '#b45309', '#92400e', '#78350f', '#2a1a06'],
  emerald: ['#0b2520', '#0e3129', '#134236', '#1a5a47', '#34d399', '#10b981', '#059669', '#047857', '#065f46', '#064e3b', '#062419'],
  blue: ['#0f203b', '#132a4d', '#1a3764', '#244988', '#60a5fa', '#3b82f6', '#2563eb', '#1d4ed8', '#1e40af', '#1e3a8a', '#0c1834'],
  purple: ['#211634', '#2b1c46', '#39255c', '#4f327d', '#c084fc', '#a855f7', '#9333ea', '#7e22ce', '#6b21a8', '#581c87', '#2a0a46'],
};
const DARK_TEXT = {
  // 50–300 stay light (they are used on dark fills in both themes); 400–950 become the
  // readable text ramp: 400 most muted … 900/950 strongest.
  slate: ['#f8fafc', '#f1f5f9', '#e2e8f0', '#cbd5e1', '#71809a', '#8a98b0', '#a2aec2', '#bac5d5', '#d3dbe6', '#e7edf5', '#f4f7fb'],
  red: ['#fef2f2', '#fee2e2', '#fecaca', '#fca5a5', '#f87171', '#f87171', '#fb7f7f', '#fa8f8f', '#fca5a5', '#fecaca', '#fee2e2'],
  amber: ['#fffbeb', '#fef3c7', '#fde68a', '#fcd34d', '#fbbf24', '#fbbf24', '#f9b52a', '#fbbf24', '#fcd34d', '#fde68a', '#fef3c7'],
  emerald: ['#ecfdf5', '#d1fae5', '#a7f3d0', '#6ee7b7', '#34d399', '#34d399', '#3ddba2', '#4ade9f', '#6ee7b7', '#a7f3d0', '#d1fae5'],
  blue: ['#eff6ff', '#dbeafe', '#bfdbfe', '#93c5fd', '#60a5fa', '#60a5fa', '#6aaefc', '#7ab8fd', '#93c5fd', '#bfdbfe', '#dbeafe'],
  purple: ['#faf5ff', '#f3e8ff', '#e9d5ff', '#d8b4fe', '#c084fc', '#c084fc', '#c993fd', '#d0a2fd', '#d8b4fe', '#e9d5ff', '#f3e8ff'],
};
const DARK_BORDER = {
  slate: ['#18243a', '#1b2840', '#22324d', '#2c3e5e', '#3d5274', '#56698c', '#3d5274', '#2c3e5e', '#22324d', '#18243a', '#101a2c'],
  red: ['#3a1620', '#3d1820', '#5a2230', '#7a2b3a', '#f87171', '#ef4444', '#dc2626', '#b91c1c', '#991b1b', '#7f1d1d', '#450a0a'],
  amber: ['#3a2a0c', '#3d2c0d', '#5c4211', '#7a5714', '#fbbf24', '#f59e0b', '#d97706', '#b45309', '#92400e', '#78350f', '#451a03'],
  emerald: ['#0f3329', '#10372d', '#145142', '#1b6a55', '#34d399', '#10b981', '#059669', '#047857', '#065f46', '#064e3b', '#022c22'],
  blue: ['#172e52', '#1a3358', '#20406e', '#2a5394', '#3b82f6', '#3b82f6', '#2563eb', '#1d4ed8', '#1e40af', '#1e3a8a', '#172554'],
  purple: ['#2e1f48', '#33224f', '#46306b', '#5b3c8a', '#c084fc', '#a855f7', '#9333ea', '#7e22ce', '#6b21a8', '#581c87', '#3b0764'],
};

// Semantic tokens (used as bg-canvas, bg-accent, text-accent, border-line, ...).
const SEMANTIC = {
  light: {
    'bg-white': '#ffffff', 'bg-canvas': '#eef2f7', 'bg-accent': '#0b4f8a', 'bg-accent-strong': '#083b68',
    'bg-accent-soft': '#e6eef8', 'text-accent': '#0b4f8a', 'border-accent': '#0b4f8a', 'border-line': '#d9e0e8',
    'text-white': '#ffffff', 'border-white': '#ffffff',
  },
  dark: {
    'bg-white': '#0f1829', 'bg-canvas': '#070d18', 'bg-accent': '#2563eb', 'bg-accent-strong': '#1d4ed8',
    'bg-accent-soft': '#10233f', 'text-accent': '#5cc8ff', 'border-accent': '#38bdf8', 'border-line': '#1c2a42',
    'text-white': '#ffffff', 'border-white': '#0f1829',
  },
};

const rgb = (hex) => {
  const n = parseInt(hex.slice(1), 16);
  return `${(n >> 16) & 255} ${(n >> 8) & 255} ${n & 255}`;
};

function block(selector, roles, semantic) {
  const lines = [`${selector} {`];
  for (const [role, palettes] of Object.entries(roles)) {
    for (const [name, values] of Object.entries(palettes)) {
      values.forEach((hex, i) => lines.push(`  --${role}-${name}-${STEPS[i]}: ${rgb(hex)};`));
    }
  }
  for (const [k, hex] of Object.entries(semantic)) lines.push(`  --${k}: ${rgb(hex)};`);
  lines.push('}');
  return lines.join('\n');
}

const light = block(':root, :root[data-theme="light"]', { bg: LIGHT, text: LIGHT, border: LIGHT }, SEMANTIC.light);
const dark = block(':root[data-theme="dark"]', { bg: DARK_BG, text: DARK_TEXT, border: DARK_BORDER }, SEMANTIC.dark);

mkdirSync(new URL('../src/theme/', import.meta.url), { recursive: true });
writeFileSync(new URL('../src/theme/palette.css', import.meta.url),
  `/* Generated by scripts/generate-theme.mjs — edit that file, not this one. */\n${light}\n\n${dark}\n`);
console.log('wrote src/theme/palette.css');
