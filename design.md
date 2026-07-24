# Design System — Style Guide
### General-purpose UI/UX bible for this project
**Single source of truth for every page, every agent, every PR.**

> This doc is domain-agnostic on purpose — it doesn't assume a specific app's screens. Fill in §8 (Page Notes) once the actual screens are scoped; everything else (colors, type, components, motion) applies regardless of what you end up building.

---

## 0. Design Thesis

This product is warm, organic, and calm — the opposite of a cold enterprise dashboard. The palette is a soft cream canvas with sage-green and warm-beige accents: think natural light, paper, plants, tea — not glass, neon, or glow. The UI should feel unhurried and tactile: soft surfaces, warm neutrals, generous whitespace, and rounded (not sharp) corners.

Three rules override everything else in this document:
1. **Cream is the canvas, sage is the voice.** The background is never stark white or black — it's the warm off-white `#FDF6ED`. The one brand color is the sage green (`#778873`) — used deliberately, not sprinkled everywhere.
2. **Soft edges, soft shadows — not hairlines.** Unlike a cold dashboard aesthetic, this system uses gentle drop shadows and rounded corners to feel tactile and approachable, not razor-sharp and clinical.
3. **Status colors stay in the same warm family.** Success, warning, and danger are muted, earthy tones (leaf green, mustard, terracotta) — never a saturated neon red/green that would clash with the palette.

---

## 1. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Framework | React (Next.js or Vite — pick per project needs) | Server Components if using Next.js App Router |
| Styling | Tailwind CSS v4 + CSS variables | Tokens defined once in `globals.css`, never hardcode hex in components |
| Component primitives | **shadcn/ui** (`new-york` style, custom theme below) | You own the code — extend via `cva` variants |
| Animation | **Motion** (`motion/react`) | Soft, gentle transitions — nothing snappy or mechanical; this palette calls for slower, organic easing |
| Icons | `lucide-react`, 1.5px stroke | Rounded icon style fits the soft aesthetic better than sharp/geometric icon sets |
| Tables | `@tanstack/react-table` + shadcn `Table` | For any data-heavy views |
| Forms | `react-hook-form` + `zod` | Inline errors, no `alert()` |
| Charts | shadcn Charts (Recharts) | Use the palette's tones for series colors — never default chart-library blues/reds |
| Toasts | `sonner` | All feedback |
| Theme | `next-themes` (optional) | This palette is light-first by design — if a dark mode is needed later, derive it from the same hues (deep mossy greens/browns), don't just invert to black |

---

## 2. Color System

### 2.1 Your palette, mapped to tokens

```css
:root {
  --background:         #FDF6ED;   /* warm cream canvas */
  --surface:              #F6EEE0;  /* chrome / nav plane, one step warmer than background */
  --card:                 #FFFFFF;  /* card fill — pure white lifts gently off the cream base */
  --card-hover:            #FBF8F2;
  --popover:               #FFFFFF; /* dialogs, dropdowns — same as card, distinguished by shadow */
  --border:                #DCCFC0; /* your palette's beige, used as the universal border/divider color */
  --border-strong:          #C9B8A4; /* a step darker, for emphasis borders (active states, focus) */

  --foreground:             #33392E; /* dark mossy charcoal — not pure black, keeps warmth */
  --muted-foreground:       #6B7566; /* muted body/secondary text, derived from the sage family */
  --muted-foreground-2:     #9CA395; /* tertiary/disabled text */

  --primary:                #778873; /* sage green — the one brand color */
  --primary-foreground:     #FDF6ED; /* cream text on sage fill */
  --primary-hover:           #6A7A66;

  --secondary:               #A1BC98; /* lighter sage — secondary actions, hover accents, chart series 2 */
  --secondary-foreground:    #33392E;

  --tertiary:                 #DCCFC0; /* warm beige — tags, subtle fills, borders */
}
```

### 2.2 Status colors — kept in the same warm family

Bright saturated red/green would clash badly with this palette, so every semantic status color is pulled toward the same earthy register:

| State | Color | Hex | Feel |
|---|---|---|---|
| Success / Complete / Approved | leaf green | `#8BAF7C` | Distinct from primary sage, still clearly "green" |
| Info / In progress / Active | dusty blue | `#7C93A8` | The one cool tone allowed — balances the warm palette without clashing |
| Warning / Pending / Due soon | mustard | `#D9A441` | Warm amber, sits naturally next to the beige tertiary |
| Danger / Error / Overdue | terracotta | `#C97064` | Muted rust-red, not a harsh alert red |
| Neutral / Inactive / Archived | warm gray | `#9C9186` | A grayed-down beige rather than a cold gray |

```css
--success: #8BAF7C;
--info:    #7C93A8;
--warning: #D9A441;
--danger:  #C97064;
--neutral-state: #9C9186;
```

Rendering pattern: a small filled dot (6–8px) + plain `text-muted-foreground` label — the dot carries the color, the text stays neutral. Only use a soft tinted background (`bg-{color}/10`) for a status when it needs more visual weight (e.g. an alert banner), and even then, pair it with a matching soft border (`border-{color}/25`), never a hard saturated fill.

### 2.3 Hard rule

Every color used anywhere in the UI must come from §2.1 or §2.2. If a screen feels like it needs a new color, it's almost always solved by adjusting *opacity* of an existing token (e.g. `bg-primary/10` for a soft highlight) rather than introducing a new hue.

---

## 3. Typography

| Role | Font | Used for |
|---|---|---|
| Display / headings | A warm serif — **Fraunces** (or Lora / Source Serif 4 as alternatives) | Page titles, hero headings, anything that should feel handwritten-adjacent and warm |
| UI / body | A clean humanist sans — **Inter** (or Work Sans / General Sans) | Nav, buttons, body copy, form labels, table content |
| Monospace (only if the project needs IDs/codes/timestamps) | **JetBrains Mono** or **Space Mono** | Reference codes, timestamps — used sparingly, not a core part of the visual identity like it might be in a data-heavy product |

Scale:
```
text-3xl  font-serif font-medium tracking-tight     → Page titles / hero headings
text-xl   font-serif font-medium                     → Section headers, card titles
text-sm   font-sans font-medium                       → Nav items, labels, buttons
text-sm   font-sans font-normal text-muted-foreground → Body copy
text-xs   font-sans text-muted-foreground              → Meta text, timestamps, helper copy
```

Headings get the serif for warmth; everything functional (buttons, nav, forms, tables) stays in the sans for legibility. Don't use the serif for body paragraphs longer than a line or two — it slows reading at length.

---

## 4. Layout System

### 4.1 General shell

- Corner radius: generous — `rounded-2xl` (16px) for cards and major panels, `rounded-lg` (12px) for buttons and inputs. This palette wants softness; don't go below 12px anywhere visible.
- Shadows, used deliberately (unlike a hairline-only system): a soft, warm-toned shadow — e.g. `shadow-[0_2px_20px_rgba(51,57,46,0.06)]` — rather than Tailwind's default cool-gray shadow. Cards lift gently off the cream background instead of being separated purely by borders.
- Borders: `border border-border` (the beige tone) still used for internal dividers (table rows, list items) — shadows are for *elevation* (cards floating above background), borders are for *division* (rows within a list).
- Spacing: generous — `p-6`–`p-8` card padding, `gap-6`–`gap-8` section spacing. This is a calm, unhurried product; don't compress it into a dense dashboard layout unless the actual use case demands high data density.

### 4.2 Navigation

- Sidebar or top nav (pick based on the project): `bg-surface`, no hard border — separate it from content with a soft shadow or a wide gap rather than a hairline, to keep the "no cold dividers" feeling consistent.
- Active nav item: `bg-primary/10 text-primary` (a soft sage tint), not a saturated fill — keeps the calm register even in the "selected" state.

---

## 5. Core Component Patterns

### 5.1 Buttons
- **Primary**: `bg-primary text-primary-foreground rounded-lg`, `hover:bg-primary-hover`. One per view/section.
- **Secondary**: `bg-secondary/20 text-foreground border border-secondary/40 rounded-lg` — a soft tinted fill rather than a plain outline, fitting the warmer, softer visual language.
- **Ghost**: `text-muted-foreground hover:text-foreground hover:bg-tertiary/30` — for low-emphasis/icon actions.
- **Destructive**: `text-danger border border-danger/30 bg-danger/5`, confirmed via a dialog before firing — never a hard solid-red button.

### 5.2 Cards
`bg-card rounded-2xl` + the soft shadow from §4.1 (no border needed when a shadow is present — pick one or the other, not both, to avoid a "boxed-in" feeling). Card header: serif `text-lg font-medium`, optional `text-sm text-muted-foreground` subtitle.

### 5.3 Status indicators
Per §2.2 — dot + plain muted text by default; a soft tinted pill (`bg-{color}/10 border border-{color}/25 rounded-full px-2.5 py-0.5`) only where more visual weight is warranted (e.g., a prominent alert banner, not a table cell).

### 5.4 Tables
`@tanstack/react-table` + shadcn `Table`. Header row `text-xs uppercase tracking-wide text-muted-foreground`, rows divided by `border-b border-border` (the beige tone reads as a soft warm line, not a cold hairline). Row hover: `bg-tertiary/15`.

### 5.5 Forms
Inputs: `bg-white border border-border rounded-lg`, focus state `border-primary ring-2 ring-primary/15` (a soft sage focus glow, not a hard blue ring — this is one of the only places the brand color shows up outside buttons). Inline errors: `text-xs text-danger`.

### 5.6 Empty / loading / error states
- Loading: soft pulsing skeleton blocks, `bg-tertiary/30 animate-pulse rounded-lg` — warm gray-beige, not cold gray.
- Empty: centered icon (lucide, rounded stroke, `text-muted-foreground-2`) + one warm, plain-language line + one primary action if applicable.
- Error: inline `Alert` with `bg-danger/5 border border-danger/25 text-danger`, never a full-page break.

---

## 6. Motion Guidelines

Motion here should feel unhurried — like something settling into place, not snapping.
- Page/content transitions: `opacity 0→1, y: 4→0`, 250–300ms, gentle ease-out (`[0.22, 1, 0.36, 1]` or similar) — slightly slower than a typical SaaS product, on purpose.
- Card/dialog entrances: soft scale + fade (`scale: 0.98→1, opacity 0→1`), 220ms.
- Status change: a brief, soft 400ms background tint flash in the new status color at very low opacity (`/8`), then settle — matches the calm register, no sharp flash.
- Respect `prefers-reduced-motion` globally.

---

## 7. Accessibility & Consistency Floor

- Visible focus state on every interactive element — the soft sage ring from §5.5, applied consistently (not just on inputs).
- Status is never color-only — dot/pill + text label always paired.
- Contrast: `--foreground` (#33392E) on `--background` (#FDF6ED) and `--card` (#FFFFFF) comfortably clears WCAG AA — don't lighten `--foreground` further for softness; softness comes from the palette choice, not from washing out text.
- Dialogs/sheets trap focus, close on `Esc`; toasts use `sonner`'s built-in `aria-live`.
- Responsive floor: works at 375px width.

---

## 8. Page Notes *(fill in once screens are scoped)*

This section is intentionally empty — once you know what you're building, add one entry per screen here (layout, key components, any screen-specific rules), following the pattern: page header → primary content → states (empty/loading/error) → responsive notes. Keep every screen's color, type, and component choices traceable back to §§1–7 above.

---

## 9. File/Folder Convention

```
components/ui/          shadcn primitives — cva variants only, don't hand-restyle
components/shared/       StatusDot/StatusPill, Skeleton, PageHeader, EmptyState — build ONCE, import everywhere
components/motion/       thin wrappers around Motion primitives (FadeIn, SoftScale)
lib/tokens.ts             re-export the §2 color map — no component ever writes bg-[#...] literally
```

---

## 10. Quick Checklist Before You Ship a Screen

- [ ] Background is `--background` (#FDF6ED) or `--surface`, never pure white/black
- [ ] Cards use the soft shadow + `rounded-2xl`, not hairline borders + sharp corners
- [ ] The only colors anywhere trace back to §2.1 (palette) or §2.2 (status) — no new hues
- [ ] Headings in the serif, everything functional in the sans
- [ ] One primary (sage-filled) button max per view
- [ ] Loading = soft pulsing skeleton, empty = icon + one warm line + one action, error = inline alert
- [ ] Motion is gentle/slow (250ms+, soft easing) — nothing snappy or mechanical
- [ ] Works at 375px, visible focus rings, status never color-only