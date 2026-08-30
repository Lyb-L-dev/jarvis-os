---
name: Jarvis OS
description: 墨·琥珀 — 石墨底、象牙文字、单一琥珀点缀的精装仪器风，为本地优先的个人 AI 操作系统而设。
colors:
  canvas: "#0b0c0e"
  canvas-deep: "#08090b"
  surface: "#131418"
  surface-raised: "#1a1b20"
  field: "#17181c"
  text-primary: "#ecebe6"
  text-secondary: "#a09e96"
  workspace-secondary: "#8b8a83"
  energy: "#d9a13b"
  energy-hot: "#ecc97e"
  energy-deep: "#8a6420"
  action-fill: "#e6e2d8"
  violet: "#8a80d8"
  blue: "#6f93c4"
  success: "#9ec6a6"
  warning: "#d9c37f"
  danger: "#d98a8a"
typography:
  display:
    fontFamily: "Geist, Noto Sans SC, Microsoft YaHei, sans-serif"
    fontSize: "clamp(2.5rem, 5vw, 3.5rem)"
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Geist, Noto Sans SC, Microsoft YaHei, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 520
    lineHeight: 1.2
    letterSpacing: "-0.03em"
  title:
    fontFamily: "Geist, Noto Sans SC, Microsoft YaHei, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.2
  body:
    fontFamily: "Geist, Noto Sans SC, Microsoft YaHei, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Geist, Noto Sans SC, Microsoft YaHei, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.35
  measurement:
    fontFamily: "Geist Mono, Cascadia Code, Consolas, monospace"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1
rounded:
  compact: "7px"
  control: "9px"
  panel: "14px"
  card: "20px"
  input: "12px"
  shell: "26px"
  pill: "999px"
spacing:
  xxs: "4px"
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "22px"
  xl: "30px"
components:
  button-primary:
    backgroundColor: "{colors.action-fill}"
    textColor: "{colors.canvas-deep}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "39px"
  button-ghost:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-secondary}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "39px"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.panel}"
    padding: "22px"
  input:
    backgroundColor: "{colors.field}"
    textColor: "{colors.text-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.input}"
    padding: "12px"
  nav-item:
    textColor: "{colors.text-secondary}"
    typography: "{typography.label}"
    rounded: "{rounded.input}"
    padding: "0 12px"
    height: "39px"
---

# Design System: Jarvis OS

## Overview

**Creative North Star: "The Quiet Evidence Console"**

Jarvis OS feels like a private systems console that happens to be conversational: dark enough for sustained desktop use, restrained enough that real evidence remains the visual focus, and precise enough that state, provenance, and permission boundaries are immediately legible. Cyan marks system energy and interaction, while green, amber, red, violet, and blue carry specific operational meaning rather than decorative variety.

The interface is dense but not cryptic. Thin boundaries, tonal surface changes, compact controls, real lists, and measured motion communicate hierarchy without turning every datum into a card. The shared shell remains recognizable across full pages and temporary workspaces; route-specific compositions such as the `/chat` twin wings stay in their surface brief instead of becoming universal page templates.

**Key Characteristics:**

- Near-black canvases with quiet, stepped surfaces.
- Evidence-first lists and inspectors rather than summary decoration.
- Cyan for system energy and primary interaction, with semantic status colors kept literal.
- Workhorse sans typography for reading and mono only for measurements, identifiers, and machine state.
- Fine borders and tonal layering before ambient shadow.
- Responsive task continuity: desktop density collapses into rails, drawers, and focused mobile surfaces.

## Colors

The palette is restrained: a near-black neutral field, one cyan interaction voice, and a small semantic status family.

### Primary

- **Jarvis Energy:** Signals primary actions, active navigation, focus rings, live system details, and the product's core identity.
- **Energy Hot:** Provides high-contrast cyan text and highlights on the darkest surfaces.
- **Energy Deep:** Supports subdued cyan states without making every control luminous.

### Secondary

- **Operational Violet:** Distinguishes memory and specialist context where cyan would imply a primary action.
- **Evidence Blue:** Separates knowledge and reference material from live system energy.

### Tertiary

- **Verified Green:** Ready, healthy, completed, and safe states only.
- **Review Amber:** Pending review, degraded operation, or explicit attention.
- **Boundary Red:** Errors, rejection, prohibition, and destructive risk.

### Neutral

- **Private Canvas:** The persistent application background.
- **Deep Canvas:** The lowest, least interactive layer.
- **Quiet Surface:** Panels, cards, and stable control backgrounds.
- **Raised Surface:** Menus, popovers, and temporary layers.
- **Primary Text:** Headings and high-value content.
- **Secondary Text:** Supporting copy and labels.
- **Workspace Secondary:** Compact panel descriptions and status copy where the older global tertiary text is too faint.

### Named Rules

**The Cyan Has a Job Rule.** Cyan identifies system energy, focus, or a meaningful action; it is not a general decoration color.

**The Status Is Literal Rule.** Green means ready or complete, amber means pending or degraded, and red means error or blocked. Never swap them for visual variety.

## Typography

- **Display Font:** Geist with Noto Sans SC and Microsoft YaHei fallbacks
- **Body Font:** Geist with Noto Sans SC and Microsoft YaHei fallbacks
- **Label/Mono Font:** Geist Mono with Cascadia Code and Consolas fallbacks

**Character:** The sans stack is neutral, compact, and bilingual, letting operational content lead. Mono is a functional instrument for time, token counts, model labels, fingerprints, and identifiers—not a costume for ordinary prose.

### Hierarchy

- **Display:** Reserved for rare overview statements and major empty-state moments.
- **Headline:** Page and inspector titles; moderate weight preserves a calm operating tone.
- **Title:** Section and major panel headings.
- **Body:** Default reading copy, kept around 65–75 characters per line where long prose appears.
- **Label:** Buttons, compact navigation, panel metadata, and secondary interface copy.
- **Measurement:** Numeric values, timestamps, machine state, model tags, and identifiers.

### Named Rules

**The Readable Before Compact Rule.** Functional labels and explanatory text remain readable at the real breakpoint; density is created through spacing and hierarchy, not sub-legible type.

**The Mono Means Machine Rule.** Use mono only when the content is measured, coded, timed, versioned, or machine-generated.

## Layout

The shared desktop shell uses a persistent left navigation and a 52px status header. Content pages use bounded grids, usually 12–22px gaps and 16–30px page padding, with asymmetric columns when one side is an inspector or action surface. Lists and workspaces favor `minmax(0, 1fr)` so real titles can truncate or wrap without breaking the grid.

At narrower desktop widths the shell reduces its left offset; task workspaces progressively replace a secondary region with a compact rail. At 1100px the conversation workspace removes the global sidebar, and at 760px it becomes a full-height mobile surface with side drawers and a bottom switcher. At 480px nonessential labels collapse before primary content or controls do. Every responsive transition preserves the current task and real data state.

**The Center Owns Continuity Rule.** When a surface has a primary working object—conversation, inspector, document, or timeline—it retains readable width before supporting regions do.

## Elevation & Depth

The system is flat by default. Depth comes first from darker and lighter tonal layers, then from one-pixel borders. Wide ambient shadows are reserved for the floating global sidebar, menus, and genuinely raised inspectors; active controls may use a restrained cyan-tinted offset shadow. Workspace panels remain predominantly border-and-tone surfaces.

**The Tonal Before Shadow Rule.** Add a new surface level with color and a fine boundary before adding a shadow. A shadow must describe real elevation or interaction state.

## Shapes

Controls use compact 7–12px corners; regular panels sit near 14px; prominent cards and bounded page regions use 18–21px; the floating application shell reaches 26px. Pills are reserved for statuses, modes, and compact selectors. One-pixel borders define structure, while circular forms are limited to state dots, avatars, and orbit indicators.

**The Radius Follows Scale Rule.** Small controls stay compact, panels stay gently rounded, and shell-level surfaces receive the largest radius. Do not apply one universal radius everywhere.

## Components

### Buttons

- **Shape:** Compact rounded controls with a stable minimum height.
- **Primary:** Bright cyan action fill with dark text; reserved for the page's meaningful next action.
- **Hover / Focus:** Increase contrast or border clarity, then use the shared cyan focus ring. Disabled controls reduce opacity without removing their label.
- **Ghost:** Quiet surface, secondary text, and a fine neutral boundary for reversible or supporting actions.

### Chips

- **Style:** Pills or compact rounded tags with tonal backgrounds and one-pixel borders.
- **State:** Selected chips borrow the relevant semantic color; unselected chips remain neutral. Chips summarize state or mode and do not replace buttons for consequential actions.

### Cards / Containers

- **Corner Style:** Panels are moderately rounded; shell-level cards are more generous.
- **Background:** Near-black tonal steps with primary text and secondary metadata.
- **Shadow Strategy:** Flat at rest; ambient shadow only when genuinely raised.
- **Border:** One-pixel neutral or semantic-tinted boundary.
- **Internal Padding:** Compact panels use the small rhythm; full page cards use the medium-to-large rhythm.

### Inputs / Fields

- **Style:** Dark raised field, fine boundary, readable placeholder, and compact rounded corners.
- **Focus:** Cyan focus ring or border shift with no layout jump.
- **Error / Disabled:** Error copy stays adjacent and names recovery; disabled state remains readable and visibly inactive.

### Navigation

Navigation is quiet by default and gains a tonal active surface, brighter text, and a cyan icon or indicator. Desktop navigation lives in the floating left shell; task-specific navigation may collapse to a rail. Mobile switches to bottom or drawer navigation only when the working content needs the full width.

### Context Panel Stack

Temporary context panels use a full front card plus shallow visible back cards. Their header always exposes identity, pin state, and close. Opening, reordering, and dismissing a card changes workspace context; it never becomes a new business fact source.

## Do's and Don'ts

### Do:

- **Do** make data provenance, readiness, selection, and approval boundaries visible beside the content they affect.
- **Do** use real lists, previews, empty states, and recovery actions instead of decorative metrics.
- **Do** preserve keyboard focus, readable labels, and task state when a desktop region becomes a rail or mobile drawer.
- **Do** let a single semantic tone identify a temporary panel while the global cyan voice remains reserved for system interaction.
- **Do** keep meaningful actions synchronized with the user's current task and keep low-level filtering local.

### Don't:

- **Don't** use cyan, green, amber, or red interchangeably for visual variety.
- **Don't** promote every piece of content into a same-size card; use lists, inspectors, and open working space.
- **Don't** use mono for ordinary prose or decorative “technical” styling.
- **Don't** let temporary UI state masquerade as persisted domain truth or bypass approval boundaries.
- **Don't** inherit legacy sub-10px functional labels or eyebrow/kicker patterns as new system primitives; they are existing debt, not the quality bar.
