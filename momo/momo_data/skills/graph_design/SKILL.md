---
name: graph_design
description: Create publication-quality matplotlib figures adhering to academic and technical standards. Use this skill whenever the user asks to plot data, visualize results, create a figure or chart, or produce any graph — even if they don't say "publication" or "matplotlib" explicitly. Also trigger for Momobot-specific plots such as token usage over time, memory compaction events, loop iteration metrics, or any agent performance visualization. When in doubt, use this skill.
---

# Graph Design Skill

Produces publication-quality matplotlib figures using an iterative render-critique loop.
Output goes to `/mnt/user-data/outputs/` as both PNG (1000 DPI) and SVG.

---

## 🔄 The Optimization Loop (Required Workflow)

Never submit a plot without running this loop. Do not skip the critique step.

1. **Draft** — Implement the plot using the configurations below.
2. **Render** — Generate the image file.
3. **Critique** — Use the `view` tool to visually inspect the output against the Quality Checklist.
   - Ask: *"Is the font serif? Are top/right spines removed? Do markers have white edges? Is the aspect ratio correct?"*
4. **Refine** — Fix any discrepancies found in the critique.
5. **Verify** — Re-render and re-critique until all checklist items pass.

---

## When NOT to Use This Skill

- Quick throwaway/exploratory plots with no quality requirements
- Plotly, Seaborn, Bokeh, or any non-matplotlib backend
- Purely statistical output (tables, descriptive stats) with no figure needed

---

## Figure Dimensions

| Layout | Width (in) | Height (in) | Typical Use |
|---|---|---|---|
| Single column | 3.3 – 3.5 | proportional | Nature, Science |
| Double column | 5.0 – 7.0 | proportional | IEEE full page |
| Multi-panel (2×1) | 6.0 – 9.0 | proportional | Side-by-side |

**Project defaults** (override per request if needed):

| Type | Width | Height |
|---|---|---|
| Single | 6.0" | 4.6" |
| Double | 7.25" | 5.0" |
| Multi-panel (2×1) | 9.0" | 4.0" |

---

## Configuration Reference

### Typography
```python
plt.rcParams.update({
    'font.family': 'serif',       # Critical — never leave as default sans-serif
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
})
```

### Color Palette (Paul Tol — colorblind-safe)
```python
COLORS = {
    'primary':     '#88CCEE',
    'secondary':   '#CC6677',
    'tertiary':    '#DDCC77',
    'quaternary':  '#6699CC',
    'quinary':     '#888888',
    'accent':      '#EE7733',
    'grid':        '#CCCCCC',
}
```
For sequential data use: `viridis`, `plasma`, `magma`, or `inferno`.

### Marker Specifications
| Property | Value |
|---|---|
| Size | 10 |
| Edge color | `#FFFFFF` (white) |
| Edge width | 1.5 |

### Z-Order Hierarchy
| Z | Layer | Elements |
|---|---|---|
| 0 | Background | Region fills, shading |
| 1–2 | Reference | Grid lines, reference lines |
| 3 | Data | Curves, markers |
| 4+ | Annotations | Labels, callouts, arrows |

### Export Settings
```python
OUTPUT_DIR = '/mnt/user-data/outputs/'   # Always use this path

def save_fig(fig, name):
    fig.savefig(f'{OUTPUT_DIR}{name}.png', dpi=1000, bbox_inches='tight', facecolor='white')
    fig.savefig(f'{OUTPUT_DIR}{name}.svg', dpi=72,   bbox_inches='tight', facecolor='white')
```

---

## Clean Aesthetics (L-Frame Pattern)

Always remove top and right spines. Always render grid behind data.

```python
fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.grid(True, which='major', linestyle='-', alpha=0.5, zorder=1)
```

---

## Complete Starter Template

Copy and adapt this for every new plot:

```python
import os
import numpy as np
import matplotlib.pyplot as plt

# --- Output ---
OUTPUT_DIR = '/mnt/user-data/outputs/'
os.makedirs(OUTPUT_DIR, exist_ok=True)

def save_fig(fig, name):
    fig.savefig(f'{OUTPUT_DIR}{name}.png', dpi=1000, bbox_inches='tight', facecolor='white')
    fig.savefig(f'{OUTPUT_DIR}{name}.svg', dpi=72,   bbox_inches='tight', facecolor='white')
    print(f"Saved: {name}.png + {name}.svg → {OUTPUT_DIR}")

# --- Config ---
FIG_WIDTH, ASPECT_RATIO = 6.0, 1.3
FIG_HEIGHT = FIG_WIDTH / ASPECT_RATIO

COLORS = {
    'primary': '#88CCEE', 'secondary': '#CC6677', 'tertiary': '#DDCC77',
    'quaternary': '#6699CC', 'quinary': '#888888', 'accent': '#EE7733', 'grid': '#CCCCCC',
}

plt.rcParams.update({
    'font.family': 'serif', 'font.size': 10,
    'axes.labelsize': 11, 'axes.titlesize': 12,
    'xtick.labelsize': 9, 'ytick.labelsize': 9,
})

# --- Data ---
x = np.logspace(1, 6, 100)
y = 1 / x + 0.01

# --- Plot ---
fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
ax.set_xscale('log')
ax.set_yscale('log')

ax.plot(x, y, color=COLORS['primary'], linewidth=2, zorder=3)
ax.scatter(x[::10], y[::10],
           color=COLORS['secondary'], s=10**2,
           edgecolors='#FFFFFF', linewidths=1.5, zorder=3)

ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.grid(True, which='major', linestyle='-', alpha=0.5, zorder=1)

ax.set_xlabel('Frequency (Hz)')
ax.set_ylabel('Amplitude')
ax.set_title('Result', fontweight='bold')

plt.tight_layout()
save_fig(fig, 'final_plot')
```

---

## ✅ Quality Checklist

Run through this during the **Critique** step. Do not skip.

- [ ] **Font**: Is `font.family` explicitly set to `'serif'`? (Check rcParams, not just appearance)
- [ ] **Spines**: Top and right spines removed?
- [ ] **Grid**: Grid lines behind data (zorder ≤ 2)?
- [ ] **Colors**: From Paul Tol palette or a perceptually uniform sequential map?
- [ ] **Markers**: White edge (`#FFFFFF`), edge width 1.5, size 10?
- [ ] **Aspect ratio**: Does the figure match the intended column width?
- [ ] **Labels**: All axes labelled, font size ≥ 9pt, legible at output size?
- [ ] **Export**: Both PNG (1000 DPI) and SVG saved to `/mnt/user-data/outputs/`?