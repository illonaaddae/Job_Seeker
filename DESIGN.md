---
version: 1
name: JobSeeker-dashboard
description: "A dense, near-black review queue for an automated job application engine. The canvas is #010102 with a four step charcoal surface ladder and three hairline weights carrying all hierarchy; there are no drop shadows except on surfaces that genuinely float. One lavender-blue accent (#5e6ad2) is spent on exactly four things: the brand mark, the primary action, the focus ring, and the current selection — never on data. Record state is carried by a 6px coloured dot beside neutral text rather than by filled pills, and the dot vocabulary means state and nothing else; other dimensions take a drawn glyph. Inter carries every size including the large figures; JetBrains Mono is restricted to small inline measurement. Controls are 8px, cards 12px, and nothing is a pill. Derived from the Linear design language (awesome-design-md/design-md/linear.app), translated from that system's marketing surface to a product Operate surface."

mode: operate

colors:
  # Dark is the primary theme and holds the source system's own values.
  accent: "#5e6ad2"
  accent-hover: "#828fff"
  accent-focus: "#5e69d1"
  accent-ink: "#ffffff"

  canvas: "#010102"
  surface: "#0f1011"
  surface-2: "#141516"
  surface-3: "#18191a"
  surface-4: "#191a1b"
  line: "#23252a"
  line-strong: "#34343a"
  line-tertiary: "#3e3e44"

  ink: "#f7f8f8"
  ink-2: "#d0d6e0"
  muted: "#8a8f98"
  ink-tertiary: "#62666d"

  # Status hues. The source system holds its marketing canvas to one accent and
  # documents that its product surface carries a wider label palette; a review
  # queue is that product surface, because the state of a row is the thing being
  # scanned. Used as a glyph beside neutral text, never as a chip fill.
  st-blue: "#4ea7fc"
  st-green: "#4cb782"
  st-amber: "#f2c94c"
  st-orange: "#f2994a"
  st-red: "#eb5757"
  st-violet: "#b59aff"
  st-grey: "#8a8f98"

  scrim: "rgb(0 0 0 / 0.6)"

colors-light:
  # Spread wider than a straight inversion: at #f7f8f8 canvas against #f4f5f6
  # controls the steps were ~1.2 L* apart and a search field had no ground.
  canvas: "#f1f2f4"
  surface: "#ffffff"
  surface-2: "#f7f8f9"
  surface-3: "#edeef1"
  surface-4: "#e1e3e8"
  line: "#dcdee3"
  line-strong: "#c8cbd2"
  line-tertiary: "#b4b8c1"
  ink: "#131416"
  ink-2: "#3b3f45"
  muted: "#64696e"
  ink-tertiary: "#9096a0"   # non-text only
  accent: "#5e6ad2"
  accent-hover: "#4d59c4"
  st-blue: "#2b6cb8"
  st-green: "#0f7a4f"
  st-amber: "#8a5a00"
  st-orange: "#a2510f"
  st-red: "#bf2a2a"
  st-violet: "#5b46c4"
  st-grey: "#8b9096"
  scrim: "rgb(16 20 25 / 0.32)"

typography:
  family-sans: '"Inter var", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif'
  family-mono: '"JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace'
  figure:
    fontSize: 26px
    fontWeight: 620
    lineHeight: 1.0
    letterSpacing: -0.028em
    family: sans          # NOT mono: see Typography
  display:
    fontSize: 22px
    fontSizeMobile: 20px
    fontWeight: 620
    lineHeight: 1.2
    letterSpacing: -0.021em
  title:
    fontSize: 16px
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: -0.013em
  body:
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: -0.006em
  sm:
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontSize: 12px
    fontWeight: 500
    lineHeight: 1.35
  micro:
    fontSize: 11px
    fontWeight: 400
    lineHeight: 1.3
  th:
    fontSize: 11px
    fontWeight: 550
    letterSpacing: 0.02em

rounded:
  tag: 6px
  control: 8px
  card: 12px
  panel: 16px

spacing:
  xxs: 2px
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px

components:
  panel:
    background: "{colors.surface}"
    border: "1px solid {colors.line}"
    rounded: "{rounded.card}"
    shadow: "inset 0 1px 0 rgb(255 255 255 / 0.04)"
  pop:
    background: "{colors.surface-2}"
    border: "1px solid {colors.line-strong}"
    rounded: "{rounded.card}"
    shadow: "0 6px 12px -6px rgb(0 0 0 / 0.5), 0 24px 48px -24px rgb(0 0 0 / 0.8)"
  tag:
    background: "{colors.surface-2}"
    border: "1px solid {colors.line}"
    textColor: "{colors.ink-2}"
    typography: "{typography.label}"
    rounded: "{rounded.tag}"
    padding: 3px 7px
    glyph: 6px round dot in the status hue
  btn-primary:
    background: "{colors.accent}"
    textColor: "{colors.accent-ink}"
    rounded: "{rounded.control}"
    padding: 8px 14px
    minHeight: 32px
  btn-secondary:
    background: "{colors.surface-2}"
    border: "1px solid {colors.line}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: 8px 14px
  btn-quiet:
    background: transparent
    textColor: "{colors.muted}"
    hoverBackground: "{colors.surface-2}"
  control:
    background: "{colors.surface-2}"
    border: "1px solid {colors.line}"
    rounded: "{rounded.control}"
    padding: 7px 10px
    minHeight: 32px
  segmented:
    track: "{colors.surface-2}"
    trackBorder: "1px solid {colors.line}"
    rounded: "{rounded.control}"
    selectedBackground: "{colors.surface-4}"
    selectedTextColor: "{colors.ink}"
    idleTextColor: "{colors.muted}"
  row:
    hoverBackground: "{colors.surface-2}"
    currentBackground: "{colors.surface-2}"
    currentRail: "inset 2px 0 0 {colors.accent}"
    separator: "1px solid {colors.line}"
  focus-ring:
    outline: "2px solid color-mix(in oklab, {colors.accent-focus} 55%, transparent)"
    offset: 1px
    radius: none           # inherits the element's own corners
  meter:
    track: "{colors.surface-4}"
    fill: "{colors.line-tertiary}"   # neutral by default
    height: 4px
    zero: draws no fill at all
  score:
    rail: "2px x {colors.line-tertiary}, always neutral"
    figure: mono, tabular; {colors.ink} at >=85, {colors.ink-2} below
---

## Overview

This is the dashboard for an engine that finds jobs, scores them, drafts
applications and sends them. The visitor is one person, in a task, several times
a day: they want to know what is waiting, which roles are worth their afternoon,
and whether a letter is good enough to send. That makes it an **Operate**
surface. Expression never gets to obscure state, and brand lives in precise
details rather than in decoration.

The world is the Linear design language, pinned by the project owner from
`awesome-design-md/design-md/linear.app`. That document describes Linear's
*marketing* canvas; this is a product surface, so three things were translated
rather than copied:

1. **Density.** Marketing spends 96px between sections. This spends 16px, runs
   44–56px rows, and holds a 1.15 type ratio instead of a display scale.
2. **A status palette.** The source keeps its marketing canvas to one accent and
   records in its own Known Gaps that Linear's product UI carries a wider label
   palette for priorities and states. A review queue is that surface. The hues
   are used as a glyph beside neutral text, never as a chip fill, so the accent
   stays as scarce as the source demands.
3. **A light theme.** The source ships none and documents none. The light values
   invert the ladder while keeping its structure and the identical accent.

**Key characteristics**

- `#010102` canvas — near-black with a faint blue cast, deliberately not `#000`.
- A four-step surface ladder plus three hairline weights carry all hierarchy.
- **No shadow** on cards or panels. Shadow is spent only on the run menu, the
  review drawer and toasts, which genuinely float.
- One accent, four uses: brand mark, primary action, focus ring, current
  selection. Never a section background, never a card fill, never decoration.
- One tag shape for the whole product; semantics ride in a 6px glyph.
- One type family. `JetBrains Mono` appears only where a number is a
  measurement being compared.
- 8px controls, 12px cards, 16px panels. **Nothing is a pill.**

## Colour

Restrained is the floor and this surface holds it. Neutrals plus one accent, with
the status hues confined to glyphs and meter fills.

The status vocabulary is grouped by **what the user must do**, not by which table
a value came from, which is why one map serves jobs, applications and replies:

| Tone | Meaning | Statuses |
|---|---|---|
| grey | inert, no action | `new` `scored` `expired` `rejected_by_me` `ghosted` `withdrawn` `auto_ack` `other` |
| amber | wants the user | `draft` `drafted` |
| blue | in play, no action | `shortlisted` `approved` |
| green | progressed | `applied` `sent` `replied` `interested` |
| violet | worth celebrating | `interview` `offer` |
| red | failed | `failed` `rejected` `rejection` |

**The dot means state and nothing else.** Reusing it for another dimension is
how a blue dot came to mean "shortlisted" in the Status column and "remote" in
the Location column of the same row. Non-state dimensions take a drawn glyph
instead — location gets a pin — via `Tag`'s `icon` prop.

**Match scores carry no hue.** They were banded green/blue/amber, which collided
with the dot vocabulary above; banding them with the accent instead failed for a
different reason, that the shortlist filters at 60 and real rows land at 78–90,
so a 75 threshold painted every rail accent and the signal said nothing. The
queue is sorted by score, so position ranks it; the rail is always neutral and
weight plus ink mark the top of the list (`>=85`).

**Nothing draws ink for zero.** A meter or funnel bar at 0 renders no fill at
all. A minimum-width sliver is a lie about the data, and it reads as a rendering
artifact besides. Likewise `stats === null` renders skeletons, never zeros — the
page must not assert "0 discovered" as a fact it does not have yet.

### Don't

- Don't put the accent on an inactive state, a section background or a card fill.
- **Don't spend the accent on data.** Not on score bands, not on meter fills, not
  on funnel bars. It marks brand, primary action, focus, and current selection;
  a meter's default fill is `--line-tertiary`, and only the stage the user must
  act on takes the accent.
- Don't fill a tag with a status colour. The dot carries it.
- Don't use `--ink-tertiary` for text. It is 3.3:1 in dark and 2.98:1 in light,
  so it fails the body floor in both themes and the large-text floor in light.
  Icon strokes and disabled glyphs only; text goes to `--muted`.
- Don't set a `border-radius` on the focus ring. The outline follows the
  element's own corners; forcing one squares off every button on focus.
- Don't fade a disabled primary button with opacity — its label drops to about
  2.6:1. Desaturate the surface instead.
- Don't add a shadow to a panel. Move it up the surface ladder instead.
- Don't derive the scrim from `--ink`: `--ink` is near-white in dark mode, so it
  tints the page white instead of dimming it. Use `--scrim`.
- Don't use `#000000` as the canvas.

## Typography

One family carries headings, buttons, labels, body and data. A product UI has
more type elements than a brand page, so a display/body pairing only adds noise.

`Inter` is deliberate, not a default: the pinned source document names it as the
closest free substitute for Linear's proprietary face. A generic slop detector
will flag Inter as an overused font, and that finding is knowingly declined here
— the alternative it would push toward would be less faithful to the pinned
system, and the system was the brief.

The scale is **fixed, not fluid**. Users view at a consistent size, and a heading
that shrinks inside a panel looks worse rather than more responsive. Only the
page title steps down, once, below 1024px.

Levels differ in **weight and colour as well as size**. A first cut of this
system ran 11px to 17px with everything set in muted grey; the result had no
hierarchy at all and the page title came out the same size as a section heading.
If a level is hard to distinguish, change its weight or its ink before its size.

`font-variant-numeric: lining-nums tabular-nums` is set on `body`, so any column
of figures stays a column.

**The large figure is Inter, not mono.** `.figure` was 30px JetBrains Mono,
which made a numeral the loudest voice on the page and contradicted three
authorities at once: this system's own "Inter alone", the pinned source's mono
spec (13px/400, code and ID tokens only), and the refusal of mono-as-costume
below. Inter's tabular figures align just as well. Mono survives only where a
number is a small inline measurement being compared: the match score, the
segmented counts, the daily cap, identifiers.

## Layout

- Nav rail 248px, one surface step above the content canvas, hairline between.
- Content padding 16px, 24px from `lg`.
- Panel interior padding 16px.
- Content grids run `1.7fr 1fr` at `xl` and stack below.
- Grids holding cards of unequal content use `items-start`. Without it an empty
  state gets stretched to match its tallest sibling, which is how a 200px dead
  zone appears under a chart.

### Responsive behaviour is structural

Never a smaller font.

| Width | Change |
|---|---|
| `< md` (768px) | **The job table becomes a stacked list.** A six-column table cannot fit a phone; keeping it only clips the status column off the right edge mid-word. |
| `< lg` (1024px) | Nav rail becomes a horizontally scrolling top bar. Page title steps to 20px. |
| `< sm` (640px) | The page title takes a full row of its own above the controls. Sharing a shrinking flex line with a search field truncates it to "O…". **The funnel becomes a single-column sequence.** A 2x3 grid of label-plus-figure cells is six stat tiles, which is the pattern the funnel exists to refuse. |

**Reading order changes with width.** On the Overview the queue is ordered above
the sending chart and the follow-ups panel below `xl` (Tailwind `order-*`, reset
at `xl`). Both of those panels are commonly empty, and in source order they put
~560px of "nothing" between the funnel and the first question the user came to
answer.

Any control row that can outgrow its container (view nav, filter segments) uses
`.scroll-x`, which hides the scrollbar and applies an edge mask, so a row that
runs off the edge reads as scrollable rather than as broken.

Touch targets hold ≥36px in the mobile nav and ≥32px elsewhere.

## Elevation

| Level | Treatment | Use |
|---|---|---|
| 0 | canvas, no border | page ground |
| 1 | `surface` + 1px `line` + faint top edge | panels, cards, nav rail |
| 2 | `surface-2` | tag and control fills, drawer footer, hover |
| 3 | `surface-3` | current nav item, meter tracks |
| 4 | `surface-4` | selected segment |
| float | `surface-2` + `line-strong` + shadow | run menu, drawer, toasts |

## Motion

Product loads into a task. There is **no entrance choreography**: no page-load
sequence, no per-section reveal.

- 140–220ms, `cubic-bezier(0.16, 1, 0.3, 1)`.
- Motion conveys state only: a surface arriving, a value changing, a hover.
- Bars animate `transform: scaleX()` from `origin-left`, never `width`.
  Animating `width` triggers layout on every frame; the bar sits inside a
  rounded, `overflow: hidden` track, so scaling is visually identical.
- `prefers-reduced-motion` collapses every animation and transition to 0.01ms.

## Browser surfaces

The parts nobody draws still carry the design, and these are the cheapest signal
that a page was built rather than assembled. All are themed from the palette:
text selection, the caret, the scrollbar (both WebKit and `scrollbar-color`),
the focus ring, and the arrow on a native `<select>`.

## Components

Every interactive component ships default, hover, focus, active and disabled.
Loading is a skeleton at the real row height so the layout does not jump.

**Empty states teach the interface.** "Nothing here" only tells the reader they
cannot tell whether the product is broken. The sending chart's empty state draws
a ghost of the same shape the real chart will be — not a different one — and says
what fills it in.

### Refused here

These are the category's defaults, and this surface does not take them:

- Four identically sized stat cards above a chart. The six pipeline figures are
  survivors of one another, so they are laid out as a **funnel** with the drop
  between stages shown; that answers where the search is leaking, which the
  cards could not.
- A progress ring per table row. Sixty arcs cannot be compared to each other; a
  tabular figure column can.
- Decorative kickers or eyebrows above headings. A heading carries its own
  weight. `.label` names a field or a column and is not this.
- Truncating text by character count in JS. Fix widths in a `colgroup` and let
  CSS `text-overflow` trim at the width the browser actually has.
- A coloured `border-left` above 1px on cards, alerts and toasts.
- Mono as a costume for "technical", including a large display figure.
- A minimum-width bar for a zero value, and rendering zeros while loading.
- One glyph vocabulary meaning two different dimensions in one row.

## Iteration guide

1. Reach for an existing token before adding one. Components read `var(--…)`;
   no component hardcodes a colour, which is what makes a theme swap cheap.
2. Decide which surface step a new region lives on before styling it.
3. New status? Add it to `STATUS_TONE` in `Primitives.tsx`, not to a component.
4. Keep the accent scarce. If a new element wants it, it probably wants
   `surface-3` and `ink`.
5. Check any new text colour against 4.5:1 on the surface it sits on, in both
   themes. This system has already shipped one token that failed it.
6. After editing UI, run
   `node ~/.claude/skills/impeccable/scripts/detect.mjs --json dashboard/src`.
   The Inter finding is expected and declined; anything else is real.
