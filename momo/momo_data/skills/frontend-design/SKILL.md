---
name: frontend-design
description: Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks to build web components, pages, artifacts, posters, or applications (examples include websites, landing pages, dashboards, React components, HTML/CSS layouts, or when styling/beautifying any web UI). Generates creative, polished code and UI design that avoids generic AI aesthetics.
license: Complete terms in LICENSE.txt
---
# Frontend Design Skill

> *Production-grade interfaces. Unforgettable aesthetics. Zero generic slop.*

This skill guides the creation of distinctive frontend work. Real working code. Exceptional
attention to detail. An aesthetic point-of-view that's earned, not accidental.

The user brings requirements — a component, page, app, or interface. They may include context
about purpose, audience, or constraints. Your job is to bring vision.

---

## ① Think Before You Touch the Editor

Commit to a bold aesthetic direction **before writing a single line of code.**

| Question | What to ask yourself |
|---|---|
| **Purpose** | What problem does this solve? Who lives inside it daily? |
| **Tone** | Pick an extreme and own it — see the palette below |
| **Constraints** | Framework? Performance budget? Accessibility requirements? |
| **Signature** | What's the *one thing* someone will remember about this? |

### Tone Palette — pick one, push it far

```
brutally minimal     maximalist chaos     retro-futuristic
organic / natural    luxury / refined     playful / toy-like
editorial / magazine brutalist / raw      art deco / geometric
soft / pastel        industrial / utilitarian    cinematic / noir
```

These are starting points, not boxes. The best designs are *true to the context*, not true
to a label. Find what the project demands and execute it with surgical precision.

**Rule:** Bold maximalism and refined minimalism both succeed. Timid middle-ground always fails.

---

## ② Implementation Requirements

The output must be:

- ✦ **Production-grade and functional** — not a mockup, a real working thing
- ✦ **Visually striking and memorable** — someone should pause when they see it
- ✦ **Cohesive** — every detail serves the same aesthetic point-of-view
- ✦ **Meticulously refined** — spacing, rhythm, and weight all deliberate
- ✦ **Verified** — renders cleanly at desktop and mobile widths (see ⑥)

Supported stacks: HTML/CSS/JS · React · Vue · anything the user specifies.

---

## ③ Aesthetic Directives

### Typography

Choose fonts that are **beautiful, unexpected, and characterful.** The font is the first
impression — make it count.

- Pair a distinctive **display font** with a refined **body font**
- Avoid: `Arial`, `Roboto`, `Inter`, `system-ui`, `Space Grotesk`
- Aim for: fonts that feel *designed for this specific thing*, not grabbed off a default list
- Vary across projects — **never converge on the same pairing twice**


<preferences>
### Typography


    'font.family': 'Anthropic Serif Web Text', 'Anthropic Mono Variable'      # Critical — never leave as default sans-serif
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,



### Color Palette (Paul Tol — colorblind-safe)

COLORS = {
    'primary':     '#88CCEE',
    'secondary':   '#CC6677',
    'tertiary':    '#DDCC77',
    'quaternary':  '#6699CC',
    'quinary':     '#888888',
    'accent':      '#EE7733',
    'grid':        '#CCCCCC',
    'background':  '#fcfcfc'
}

### Elements shaping
- Momobot uses rounded edge for elements
- Ex: in CSS -> border-radius: 8px;
- Momobot can apply it anywhere: `px`, `%`, `rem`, or even `border-radius: 50%` for a perfect circle. A few quick patterns:
```CSS
/* Subtle card rounding */
.card { border-radius: 12px; }

/* Pill-shaped button */
.btn { border-radius: 9999px; }

/* Only top corners */
.header { border-radius: 12px 12px 0 0; }

/* CSS variable for consistency across a design system */
:root { --radius: 10px; }
.card { border-radius: var(--radius); }
```
</preferences>
- Never use '#88CCEE' for Titles colors. Title should be in dark themes white color, and for white themes Black color rgb(0,0,0).
- Use CSS variables for full-system consistency
- Avoid: purple gradients on white, generic "tech blue", muted grays with no conviction
- Alternate freely between light and dark themes — no default preference

### Motion & Animation

Motion earns its place. Prioritize **high-impact moments** over scattered micro-interactions.

- One well-orchestrated **page load** with staggered reveals beats twenty hover states
- CSS-only for HTML; Motion library for React when available
- Hover states that *surprise* — not just opacity fades
- Scroll-triggered reveals when the content calls for it

### Spatial Composition

Break the grid occasionally. Use space *intentionally* — either generous negative space
or controlled density. Never the mush in between.

- Asymmetry · Overlap · Diagonal flow · Grid-breaking elements
- Layouts that feel designed, not templated

### Backgrounds & Visual Atmosphere

Solid colors are a last resort. Create depth.

Techniques to reach for:
```
gradient meshes         noise / grain textures      geometric patterns
layered transparencies  dramatic shadows            decorative borders
custom cursors          scanline overlays           glassmorphism (when earned)
```

Every background should *belong* to its design. No orphaned effects.

---

## ④ Hard Rules

```
✗  NEVER  —  Inter, Roboto, Arial, system fonts as a primary choice
✗  NEVER  —  Purple gradients on white as a color story
✗  NEVER  —  Predictable layouts that look like every other SaaS dashboard
✗  NEVER  —  Vertical border anchors (e.g., border-left on headers) for decorative purposes
✗  NEVER  —  Blueish colors for titles or any text (Readability failure)
✗  NEVER  —  Font sizes smaller than 14px for any readable text
✗  NEVER  —  Converge on the same font pairing, palette, or layout across generations
✗  NEVER  —  Timid, uncommitted aesthetic choices
✗  NEVER  —  Declare a page done without running the checks in ⑥
✗  NEVER  —  Use color hex codes that are not explicitly listed in this SKILL.md
```

---

## ⑤ Complexity Must Match Vision

Maximalist designs demand elaborate code — extensive animations, layered effects, rich detail.
Minimalist designs demand restraint — precision in spacing, typography, and the subtlest details.

Elegance is **executing the vision completely**, not choosing the easiest path to "done."

---

## ⑥ Verify Before You Ship

Every page goes through a build → render → check → fix loop. Don't skip it, and don't stop at the first pass.

### 1. Render at two widths

```bash
python .momo/skills/scripts/render_website.py --file index.html --full-page --viewport 1280x800 --out desktop.png
python .momo/skills/scripts/render_website.py --file index.html --full-page --viewport 390x800 --out mobile.png
```

### 2. Run the overlap check at each width

```bash
python .momo/skills/scripts/detect_overlaps.py index.html --width 1280
python .momo/skills/scripts/detect_overlaps.py index.html --width 390
```

The script exits with code `0` when it finds no overlaps, `1` when it finds some, and `2` when the file is missing. It prints each overlap with the two text strings involved and their positions.

Treat each hit as a **candidate, not a verdict.** Hidden, clipped, or off-screen text can be flagged even though the user never sees it. Confirm each hit against the screenshot before changing code.

### 3. Look at the screenshots

The overlap check only sees text colliding with text. Check the PNGs yourself for what it can't catch:

- Labels colliding with bars, markers, lines, or images
- Chart ticks or legends that are cramped or crowded
- Low-contrast text, cut-off content, awkward crops
- Anything that looks wrong at mobile width even if the numbers pass

### 4. Fix and re-check

Fix the real issues, then rerun steps 1–3. The page is done when both overlap checks pass **and** the screenshots look right. If the check passes but the screenshot doesn't, the screenshot wins.

---

## Appendix: Script Reference

| Script | Purpose | Key options |
|---|---|---|
| `scripts/render_website.py` | Render a page to PNG | `--url`, `--file`, `--html`, `--full-page`, `--viewport`, `--out` |
| `scripts/detect_overlaps.py` | Find overlapping text on the rendered page | `<path>`, `--width` |

Paths are relative to this skill's folder.


## ⑦ Anti-Slop Protocol

Run every step before writing code and again before delivering. Slop usually comes from
defaults, not from bad intent, so each step forces a decision.

### A. Decide the story before the layout

Write one sentence in your response: **"The reader should leave knowing ___."**
Then pick the layout from that sentence.

- A finding usually needs **one hero element**, not four equal cards. Give it the most space and
  the strongest contrast, and let supporting material sit smaller.
- Equal-weight grids are allowed only when each element answers a different question the reader
  will actually ask. If two elements answer the same question, merge them.

### B. Banned defaults

Do not use these unless the user names them explicitly:

- Sidebar + card-grid dashboard shell
- Near-black background with an amber/gold accent
- Uppercase, letter-spaced monospace labels, or "//" separators in headings
- Pill badges with arrows (↓ ↑) in card headers
- Hover effects that only change border color or add a glow
- Big-number callout box with a thick colored border
- Cards inside cards with the same header / body / footer structure
- Decorative equations with no definition in the page's own text
- Unpinned CDN URLs (`-latest`); pin an exact version
- Plotly defaults left unchanged: top-center legend, spline smoothing, markers on every point

If you feel pulled toward one of these, that is the signal to ask what the content needs
instead.

### C. State your choices

Before coding, state in one line each:

- **Layout:** what it is, and why this content needs it
- **Hero element:** what it is and what finding it carries
- **Palette:** each hex value with its role (text, data series A, data series B, emphasis)
- **Font loading:** how the font reaches the page (embedded file, or a verified system font)

If you cannot give a reason for a choice, change it.

### D. Fonts must actually load

A declared font that falls back silently is a failure, not a success. Do not write a font name
into CSS as if it works unless one of these is true:

- The font file is bundled with the page or linked from a reliable host, or
- You verify it in the rendered page with `document.fonts.check('16px "Font Name"')` and report
  the result.

If neither is possible, tell the user the font was not available and which fallback is in use.

### E. Charts for research data

- **Discrete parameter values get straight segments.** Six values of λ are six points, not a
  curve. Do not use spline smoothing.
- **Show the difference that matters.** If two series differ only in the third significant
  figure, a plot will look flat. Plot the ratio or the gap, or annotate the value.
- **Annotate the finding on the chart itself** (for example, a label at the step where behavior
  changes), not in a separate card.
- **Use one chart for series that share axes and units.** Use separate charts only when the
  units or scales differ.
- **Label every axis with units**, and define any symbol the reader will see (λ, RMSE, ΔRMSE)
  in the page text.
- **Keep chart text legible.** Use the same font family as the page, at 14px or larger for
  anything the reader must read.
- **Numeric tooltips (hover labels) must use the Mono font** to ensure alignment and
  readability, with a minimum size of 14px.

### F. Slop audit before delivery

Answer each question. For any "yes" on questions 1–4, change the design or state the reason in
your response.

1. Could this page be mistaken for a generic SaaS dashboard or an AI-generated demo?
2. Does any element exist only as decorative filler without supporting the narrative?
3. Is there any "AI slop" (e.g. generic gradients, placeholder text, unmotivated shadows)?
4. Does the design use any color hex codes not listed in the SKILL.md?