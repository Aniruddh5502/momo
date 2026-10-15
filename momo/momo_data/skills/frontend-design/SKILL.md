---
name: frontend-design
description: Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks to build web components, pages, artifacts, posters, or applications (examples include websites, landing pages, dashboards, React components, HTML/CSS layouts, or when styling/beautifying any web UI). Generates creative, polished code and UI design that avoids generic AI aesthetics.
license: Complete terms in LICENSE.txt
---
---
name: frontend-design
description: >
  Create distinctive, production-grade frontend interfaces with high design quality.
  Use this skill when the user asks to build web components, pages, artifacts, posters,
  or applications — websites, landing pages, dashboards, React components, HTML/CSS layouts,
  or anything involving UI styling or visual design. Generates creative, polished code that
  avoids generic AI aesthetics. Trigger even for vague requests like "make it look good" or
  "clean this up" — if there's a UI involved, this skill applies.
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


    'font.family': 'serif',       # Critical — never leave as default sans-serif
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
✗  NEVER  —  Converge on the same font pairing, palette, or layout across generations
✗  NEVER  —  Timid, uncommitted aesthetic choices
```

---

## ⑤ Complexity Must Match Vision

Maximalist designs demand elaborate code — extensive animations, layered effects, rich detail.
Minimalist designs demand restraint — precision in spacing, typography, and the subtlest details.

Elegance is **executing the vision completely**, not choosing the easiest path to "done."

---


<scripts_use>
# From a URL
python render_website.py --url https://mysite.com

# From a local file (great for iteration)
python render_website.py --file index.html --full-page

# From an inline HTML string (agent generates HTML, immediately renders it)
python render_website.py --html "<h1>Draft 3</h1>" --out draft3.png
</scripts_use>