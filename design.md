# Design System — Style Guide
### Colors, Typography & Theming — applies to any project
**Single source of truth for palette, type, and theme. Framework- and stack-agnostic.**

> This doc intentionally says nothing about frameworks, libraries, or components. It defines the *look* — color, type, and theming rules — so it can be applied to any UI stack (web, mobile, native, whatever). Wire these tokens into your project's own styling system (CSS variables, a theme object, design tokens file, etc.).

---

## 0. Design Thesis

This product is warm, organic, and calm — the opposite of a cold enterprise dashboard. The palette is a soft cream canvas with sage-green and warm-beige accents: think natural light, paper, plants, tea — not glass, neon, or glow. The overall feel should be unhurried and tactile: soft surfaces, warm neutrals, generous whitespace.

Three rules override everything else in this document:
1. **Cream is the canvas, sage is the voice.** The background is never stark white or black — it's the warm off-white `#FDF6ED`. The one brand color is the sage green (`#778873`) — used deliberately, not sprinkled everywhere.
2. **Warm, not clinical.** Every color choice should feel tactile and approachable, not razor-sharp or cold.
3. **Status colors stay in the same warm family.** Success, warning, and danger are muted, earthy tones (leaf green, mustard, terracotta) — never a saturated neon red/green that would clash with the palette.

---

## 1. Color System

### 1.1 Core palette

| Token | Hex | Role |
|---|---|---|
| `background` | `#FDF6ED` | Warm cream canvas — the base of every screen |
| `surface` | `#F6EEE0` | Chrome / nav plane, one step warmer than background |
| `card` | `#FFFFFF` | Card / panel fill — pure white lifts gently off the cream base |
| `card-hover` | `#FBF8F2` | Hover state for card surfaces |
| `popover` | `#FFFFFF` | Dialogs, dropdowns, menus — same as card |
| `border` | `#DCCFC0` | Universal border/divider color (warm beige) |
| `border-strong` | `#C9B8A4` | A step darker — emphasis borders, active/focus states |
| `foreground` | `#33392E` | Dark mossy charcoal — primary text; not pure black, keeps warmth |
| `muted-foreground` | `#6B7566` | Secondary/body text, derived from the sage family |
| `muted-foreground-2` | `#9CA395` | Tertiary/disabled text |
| `primary` | `#778873` | Sage green — the one brand color |
| `primary-foreground` | `#FDF6ED` | Text/icons on a primary-filled surface |
| `primary-hover` | `#6A7A66` | Hover/active state of primary |
| `secondary` | `#A1BC98` | Lighter sage — secondary actions, hover accents, chart series 2 |
| `secondary-foreground` | `#33392E` | Text on secondary surfaces |
| `tertiary` | `#DCCFC0` | Warm beige — tags, subtle fills, borders |

### 1.2 Status colors — kept in the same warm family

Bright saturated red/green would clash with this palette, so every semantic status color is pulled toward the same earthy register:

| State | Color | Hex | Feel |
|---|---|---|---|
| Success / Complete / Approved | leaf green | `#8BAF7C` | Distinct from primary sage, still clearly "green" |
| Info / In progress / Active | dusty blue | `#7C93A8` | The one cool tone allowed — balances the warm palette without clashing |
| Warning / Pending / Due soon | mustard | `#D9A441` | Warm amber, sits naturally next to the beige tertiary |
| Danger / Error / Overdue | terracotta | `#C97064` | Muted rust-red, not a harsh alert red |
| Neutral / Inactive / Archived | warm gray | `#9C9186` | A grayed-down beige rather than a cold gray |

**Usage pattern:** pair color with a label — never rely on color alone to convey status. Use the full-strength color sparingly (small dots, icons, borders); use low-opacity tints (e.g. ~10% opacity) of the same color for backgrounds or soft emphasis, rather than a hard saturated fill.

### 1.3 Hard rule

Every color used anywhere in the UI must come from §1.1 or §1.2. If a screen feels like it needs a new color, it's almost always solved by adjusting the *opacity* of an existing token rather than introducing a new hue. Never hardcode a one-off hex value outside this token list — always reference the named token.

---

## 2. Typography

| Role | Font | Used for |
|---|---|---|
| Display / headings | A warm serif — **Fraunces** (or Lora / Source Serif 4 as alternatives) | Page titles, hero headings, anything that should feel handwritten-adjacent and warm |
| UI / body | A clean humanist sans — **Inter** (or Work Sans / General Sans) | Navigation, buttons, body copy, labels, general content |
| Monospace (only if needed) | **JetBrains Mono** or **Space Mono** | Reference codes, IDs, timestamps — used sparingly, not a core part of the visual identity |

### Type scale & usage

| Size role | Font | Weight/tracking | Used for |
|---|---|---|---|
| Hero / page title | Serif | Medium, tight tracking | Page titles, hero headings |
| Section header | Serif | Medium | Section headers, card/panel titles |
| Label / nav / button | Sans | Medium | Nav items, labels, buttons |
| Body | Sans | Regular, muted-foreground | Body copy |
| Meta / caption | Sans | Regular, muted-foreground, small | Timestamps, helper text, captions |

**Rule of thumb:** headings get the serif for warmth; everything functional (buttons, nav, forms, labels, tables) stays in the sans for legibility. Don't set the serif for body paragraphs longer than a line or two — it slows reading at length.

---

## 3. Theming

- This palette is **light-first by design**. If a dark mode is needed, derive it from the same hues (deep mossy greens and browns) rather than simply inverting to black/white — the warmth is the point, and it should survive in dark mode too.
- Contrast: `foreground` (`#33392E`) on `background` (`#FDF6ED`) and on `card` (`#FFFFFF`) comfortably clears WCAG AA. Don't lighten `foreground` further in the name of "softness" — the warmth already comes from the palette choice, not from washed-out text.
- Status is never color-only — always pair a status color with a text label or icon, regardless of platform.
- Keep the token names (`background`, `surface`, `card`, `primary`, `success`, etc.) consistent across light/dark or any future theme variants, so components never need to know which theme is active — only the token values change.

---

## 4. Quick Checklist

- [ ] Background uses `background` (`#FDF6ED`) or `surface`, never pure white/black
- [ ] The only colors anywhere trace back to §1.1 (palette) or §1.2 (status) — no new hues, no one-off hex values
- [ ] Headings use the serif, everything functional uses the sans
- [ ] Status is always color + label, never color alone
- [ ] Text contrast meets WCAG AA against its background token
- [ ] Any dark/alternate theme derives from the same warm hues rather than inverting to black/white
