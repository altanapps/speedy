# Speedy — Design Schema

A single source of truth for visual + interaction design, dense enough that a SwiftUI engineer can implement directly without follow-ups.

## 1. Stance

Three traits, in priority order:

1. **Fast.** Overlay materializes at cursor in <200ms. No layout shift, no progressive loading. Static elements never animate.
2. **Quiet.** No gradients, no decorative chrome. The matched market is the content; everything else recedes. If a pixel doesn't earn its keep, kill it.
3. **Native.** SwiftUI primitives, system materials, semantic colors, SF fonts. Looks like macOS, not like a web app pretending.

Speedy is a power-user tool. Density and speed beat friendliness.

## 2. Color tokens

Dark mode is primary. Light mode is supported and uses system semantic colors where possible.

### Dark

| Token | Hex | Usage |
|---|---|---|
| `bg.primary` | #0B0C0F | App backgrounds outside materials |
| `bg.secondary` | #14161B | Panel surface |
| `bg.tertiary` | #1B1E25 | Chips, recessed elements |
| `border` | #2A2E38 | Hairlines, panel edges |
| `text.primary` | #E7E9EE | Primary content |
| `text.secondary` | #8A91A0 | Labels, secondary content |
| `text.tertiary` | #5C6370 | Caption, disabled |
| `accent` | #7C5CFF | Speedy purple — primary action, brand |
| `accent.muted` | rgba(124, 92, 255, 0.16) | Selected pill background, glow |
| `success` | #2ECC71 | Yes / Long / Buy |
| `danger` | #FF5E5E | No / Short / Sell |
| `warning` | #FFB84D | Auth expiring, low confidence |

### Light

Use NSColor semantic tokens (`controlBackgroundColor`, `labelColor`, etc.). Accent purple, success, danger, warning stay identical to dark.

### Materials

- Overlay & popover background: `.regularMaterial` (system blur). Fallback `.thinMaterial` if vibrancy disabled.
- No solid backgrounds on floating surfaces.

## 3. Typography

All sizes in pt; line-height in pt.

| Style | Font | Size/LH | Weight | Usage |
|---|---|---|---|---|
| `display` | SF Pro Display | 28/32 | 600 | Popover header, market question |
| `title` | SF Pro Text | 18/22 | 600 | Section headers |
| `body` | SF Pro Text | 14/20 | 400 | Default content |
| `label` | SF Pro Text | 12/16 | 500 | Buttons, chips |
| `caption` | SF Pro Text | 11/14 | 400 | Metadata, venue tags |
| `mono` | SF Mono | 14/20 | 400 | Prices, percentages, ticker symbols |

**All numeric displays use `.monospacedDigit()`** so prices don't jitter when digits change during live updates.

Letter-spacing: `caption` uppercase tags get +0.08em tracking.

## 4. Surfaces

### Overlay (cursor-attached)

- Width: **320pt fixed**, height auto (140pt for ticker, 180pt for prediction with criteria)
- Background: `.regularMaterial`
- Border: 0.5pt `border` token, inside stroke
- Corner radius: **14pt**
- Shadow: `y=12 blur=40 alpha=0.30`
- Padding: 14pt inside, 12pt between sections
- Position: anchored at cursor, with 14pt offset; collision-avoid against screen edges with 12pt minimum margin
- Z-order: above all app windows; uses `NSPanel` with `.canJoinAllSpaces` and `.fullScreenAuxiliary`

### Menu-bar popover

- Width: 360pt, max height 600pt
- Same material, border, corner radius as overlay
- Header strip: 48pt with app name + status dot + settings cog
- Sections separated by 0.5pt `border` hairlines
- Padding: 12pt inside

### Settings window

- Standard `NSWindow` with title bar
- Sidebar: 200pt, segments — Account, Hotkeys, Sizing, Advanced
- Content pane: 480pt, padding 24pt

## 5. Components

### Side button (Yes/No, Buy/Sell, Long/Short)

```
height: 36pt
padding: 0 12pt
background: bg.tertiary
border: 1pt at 35% opacity of semantic token (success/danger)
text: 13pt 600, semantic token full opacity
corner radius: 10pt
hover: background → #232732
press: scale 0.98, 80ms ease-out
```

Layout: two-up grid, 8pt gap.

### Size chip

```
height: 28pt
padding: 0 10pt
corner radius: 14pt (fully pill)
inactive: bg.tertiary, text.primary, border 1pt border token
active: accent background, white text, no border
```

Wrap in horizontal row, 6pt gap. Selected chip is single-active.

### Leverage chip (perpetuals only — post-MVP)

Same as size chip, prefixed with `×`.

### Confirm button

```
height: 36pt
full-width on its row
background: accent
text: 13pt 600 white
corner radius: 10pt
hover: background → #6A4CFF
press: scale 0.98, 80ms ease-out
```

### Cancel / ghost button

Same dimensions as confirm but: no background, text.secondary color, no border.

### Match badge (top-right of overlay)

```
height: 22pt
padding: 0 7pt
background: bg.tertiary
text: 11pt 400, text.secondary
corner radius: 6pt
content: "from \"<highlight excerpt>\"" — truncated with ellipsis at 22 chars
```

### Source tag (top-left of overlay)

```
text: 11pt 500, text.secondary, +0.08em tracking, uppercase
content: "EQUITY · POLYMARKET" or "PREDICTION · POLYMARKET"
venue name (Polymarket) is accent.muted text color (#C8B8FF)
```

### Toast

```
position: top-center, 24pt from top
shape: pill, padding 10/16
background: success #1A3A25, border #2A6240
text: 13pt 400, #B8F3CF
auto-dismiss: 1800ms
```

Error toast: same shape, danger colors (#3A1A1A bg, #FF5E5E border, #F3B8B8 text).

### Position row (popover list)

```
height: 56pt
padding: 12pt horizontal, 8pt vertical
content (left): market question (1 line, truncated) + entry price + size, all 12pt
content (right): mark price + unrealized P&L, 14pt mono, semantic color
hover: background bg.tertiary
```

## 6. Motion

All animations respect the system **Reduce Motion** preference — fall back to crossfade or instant.

| Event | Animation | Timing |
|---|---|---|
| Overlay show | opacity 0→1 + translateY 4→0 + scale 0.98→1 | 140ms ease-out |
| Overlay dismiss | reverse | 100ms ease-in |
| Side selected (step 1 → 2) | height auto-grow | 180ms ease-out |
| Toast show | opacity 0→1 + translateY -8→0 | 200ms ease-out |
| Button press | scale 1→0.98 | 80ms ease-out |
| Live price tick | text color flash (success→primary or danger→primary) | 300ms ease-out |

No bounce, no spring, no overshoot. We are not a game.

## 7. Iconography

- **App icon.** Rounded square, accent gradient (linear, top-left to bottom-right, accent → #5A3FCC), centered lightning bolt cutout (Speedy mark) in white at 60% of canvas. Standard macOS app icon corner mask.
- **Menu-bar icon.** Monochrome lightning bolt, SF Symbols-style, 16pt, follows menu-bar tint (template image).
- **Inline market type icons** (popover position list):
  - Equity: `chart.line.uptrend.xyaxis`
  - Prediction: `dice`
  - Perp: `arrow.up.arrow.down.circle`
  - All at SF Symbol weight `.medium`, 14pt

## 8. Sound

Off by default. Optional toggle in Settings.

- Confirm fill: system "Tink" via `NSSound(named: "Tink")`
- Order rejected: system "Funk"
- Overlay show / dismiss: silent

Respects system "Play user interface sound effects" preference.

## 9. Accessibility

- All overlays announce content to VoiceOver on appear
- Interactive elements have `.accessibilityLabel`, `.accessibilityValue`, `.accessibilityHint`
- Focus order: side buttons → size chips → confirm → cancel
- Reduce Motion: replace transforms with crossfade
- Reduce Transparency: swap `.regularMaterial` for `bg.secondary` solid
- Increase Contrast: bump border opacity to 1.0 and text contrast to AAA

## 10. Light mode (deferred but specified)

When implemented:

| Token | Light value |
|---|---|
| `bg.primary` | NSColor.windowBackgroundColor |
| `bg.secondary` | NSColor.controlBackgroundColor |
| `bg.tertiary` | NSColor.quaternarySystemFill |
| `border` | NSColor.separatorColor |
| `text.primary` | NSColor.labelColor |
| `text.secondary` | NSColor.secondaryLabelColor |
| `accent`, `success`, `danger`, `warning` | unchanged |

## 11. Open design questions

These need a designer pass before public launch but are not blocking MVP:

- Marketing site visual language (likely diverges from app density)
- Onboarding illustrations (wallet-link, accessibility-permission, hotkey-tutorial)
- Empty states for the popover (no positions yet, no trades yet)
- Error illustration (rejected order, connection lost)
