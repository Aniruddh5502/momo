# Subagent Color Guide

Subagents are colored in the terminal so you can tell at a glance who is speaking. Set the color in the subagent's frontmatter:

```markdown
---
name: reviewer
color: bright_magenta
---
```

If `color:` is missing, Momo picks a stable color from a fallback palette based on the subagent's name, so the same subagent always gets the same color.

## Supported formats

### 1. Named ANSI colors (16)

These follow your terminal theme, so the exact shade varies between terminals.

| Normal | Bright |
| :--- | :--- |
| `black` | `bright_black` |
| `red` | `bright_red` |
| `green` | `bright_green` |
| `yellow` | `bright_yellow` |
| `blue` | `bright_blue` |
| `magenta` | `bright_magenta` |
| `cyan` | `bright_cyan` |
| `white` | `bright_white` |

`bright_black` is usually dark gray and can be hard to read on dark backgrounds.

### 2. 256-color palette

Written as `color(N)` where N is 0 to 255, for example `color(208)` for orange. These colors are fixed and do not change with the theme. Most modern terminals support them.

### 3. Hex truecolor

Written as `#rrggbb`, for example `#e3725e`. Only terminals with 24-bit color show the exact shade. On other terminals Rich approximates it.

## Modifiers

Modifiers go in front of the color, separated by spaces:

- `bold`, `dim`, `italic`, `underline`, `strike`, `reverse`, `blink`

Examples: `bold bright_cyan`, `dim magenta`, `italic #e3725e`.

Dim depends on the terminal. Most modern terminals show dim as a faded version of the color. A few ignore it entirely. Dim on a dark theme color can be hard to read, so prefer a normal or bright color for subagent text.

## Exact strings for the `color:` field

Copy any of these exactly into the frontmatter. They are case-sensitive and must match this list.

**Named ANSI colors** (no quotes needed):

```markdown
color: black
color: red
color: green
color: yellow
color: blue
color: magenta
color: cyan
color: white
color: bright_black
color: bright_red
color: bright_green
color: bright_yellow
color: bright_blue
color: bright_magenta
color: bright_cyan
color: bright_white
```

**256-color palette** (`color(0)` through `color(255)`):

```markdown
color: color(208)
color: color(114)
color: color(141)
```

**Hex truecolor** (`#` followed by six hex digits):

```markdown
color: #e3725e
color: #7aa2f7
color: #9ece6a
```

**With a modifier** (put the modifier first, separated by a space):

```markdown
color: bold bright_magenta
color: dim cyan
color: italic #e3725e
```

Valid modifiers are `bold`, `dim`, `italic`, `underline`, `strike`, `reverse`, and `blink`. You can combine more than one, for example `bold italic bright_cyan`.

**Do not use**: spaces inside the color name (`bright magenta`), uppercase (`Bright_Magenta`), hyphens (`bright-magenta`), or names such as `purple` or `orange`, which Rich does not recognize. Use `magenta` or `color(208)` instead.

## Recommended colors

These read well on both dark and light terminals:

| Color | Suggested use |
| :--- | :--- |
| `bright_magenta` | Reviewers, critics |
| `bright_cyan` | Researchers, search and lookup |
| `bright_green` | Builders, coders |
| `bright_yellow` | Planners, coordinators |
| `bright_blue` | Writers, documentation |
| `#e3725e` | Your original spinner color, a good accent |

Avoid `bright_black` and `black` for text, since they disappear on dark or light backgrounds respectively. Avoid `white` on light terminals.

## How each part is styled

- **Tag and bullet** (`[reviewer] ⬤`): bold in the subagent's color. This is the most important part for recognizing who is speaking.
- **Message body**: the subagent's color as the base style. Markdown elements such as code blocks and headings may keep their own styles.
- **Tool calls** (`✽ read(...)`): the tool name is bold in the subagent's color.
- **Tool results** (`└─ ...`): dim in the subagent's color.
- **Errors**: always red, regardless of subagent color, so failures stand out.
- **Main agent**: no color override; uses the terminal default.

## Checking a color

Preview colors in your own terminal before committing to one:

```python
from rich.console import Console

c = Console()
for name in ["bright_magenta", "bright_cyan", "#e3725e", "color(208)"]:
    c.print(f"[bold {name}]bold sample[/]  {name}")
    c.print(f"[dim {name}]dim sample[/]")
```

## Invalid colors

If `color:` contains an unknown name, Rich raises an error when rendering. Check the spelling against the tables above. Stick to the names in this guide to avoid surprises.