# Design — SwiftUI Implementation Guide

The canonical design system is [`claude-design/Speedy Design System.html`](./claude-design/Speedy%20Design%20System.html). Open it in a browser. Everything in this file is translation guidance for the native macOS implementation — token-for-token mapping from web to SwiftUI, with the deltas where native deviates.

The interactive prototype is [`claude-design/Trading Cursor.html`](./claude-design/Trading%20Cursor.html) (loads `app.jsx`, `tweaks-panel.jsx`, `macos-window.jsx` via Babel).

---

## 1. Fonts

**Web:** Inter (UI) + JetBrains Mono (numerals).
**SwiftUI:** Bundle both as custom fonts. Do not substitute SF Pro / SF Mono — the design system was authored against Inter's specific metrics and the visual identity is part of the brand.

```swift
// Info.plist additions
UIAppFonts:
  - Inter-Regular.ttf
  - Inter-Medium.ttf
  - Inter-SemiBold.ttf
  - JetBrainsMono-Regular.ttf
  - JetBrainsMono-Medium.ttf
  - JetBrainsMono-SemiBold.ttf

// Usage
.font(.custom("Inter-Regular", size: 14))
.font(.custom("JetBrainsMono-SemiBold", size: 14)).monospacedDigit()
```

All numerics (prices, sizes, percentages, ticker symbols) use JetBrains Mono with `.monospacedDigit()` so digits don't jitter on live ticks.

## 2. Color tokens → SwiftUI

Define once in `Tokens.swift`:

```swift
extension Color {
    // Brand
    static let speedyPurple        = Color(hex: 0x7C5CFF)
    static let speedyPurplePressed = Color(hex: 0x6B4DEF)
    static let speedyPurpleTint    = Color.speedyPurple.opacity(0.18)
    static let speedyPurpleSubtle  = Color.speedyPurple.opacity(0.10)

    // Backgrounds
    static let bgSystem    = Color(hex: 0x0B0B0E)
    static let bgElevated  = Color(hex: 0x18181C)
    static let bgElevated2 = Color(hex: 0x1F1F24)

    // Material tints (for translucent panels backed by .regularMaterial)
    static let matTint       = Color(red: 28/255, green: 28/255, blue: 32/255).opacity(0.62)
    static let matTintThick  = Color(red: 20/255, green: 20/255, blue: 24/255).opacity(0.78)
    static let matTintThin   = Color(red: 40/255, green: 40/255, blue: 46/255).opacity(0.42)

    // Separators
    static let separator        = Color.white.opacity(0.08)
    static let separatorStrong  = Color.white.opacity(0.14)
    static let separatorOpaque  = Color(hex: 0x2A2A30)

    // Labels
    static let label           = Color.white.opacity(0.96)
    static let labelSecondary  = Color.white.opacity(0.62)
    static let labelTertiary   = Color.white.opacity(0.40)
    static let labelQuaternary = Color.white.opacity(0.22)

    // Fills
    static let fill            = Color.white.opacity(0.08)
    static let fillSecondary   = Color.white.opacity(0.05)
    static let fillTertiary    = Color.white.opacity(0.03)
    static let fillQuaternary  = Color.white.opacity(0.02)

    // Semantic (system colors, dark variants)
    static let semGreen  = Color(hex: 0x30D158)
    static let semRed    = Color(hex: 0xFF453A)
    static let semOrange = Color(hex: 0xFF9F0A)
    static let semYellow = Color(hex: 0xFFD60A)
    static let semBlue   = Color(hex: 0x0A84FF)
}
```

## 3. Materials

Web uses `backdrop-filter: blur(40px) saturate(180%)`. SwiftUI maps to:

| Web class | SwiftUI |
|---|---|
| `.mat-thick` (60px blur) | `.background(.thickMaterial)` |
| `.mat-regular` (40px blur) | `.background(.regularMaterial)` |
| `.mat-thin` (20px blur) | `.background(.thinMaterial)` |

For the trade overlay specifically: `.regularMaterial`, with `Color.matTint` overlaid at 62% opacity to match the web tint exactly.

Reduce Transparency fallback: replace material with `Color.bgElevated` solid.

## 4. Radii

```swift
enum Radius {
    static let xs: CGFloat  = 4
    static let sm: CGFloat  = 6
    static let md: CGFloat  = 10
    static let lg: CGFloat  = 14
    static let xl: CGFloat  = 18
    static let xxl: CGFloat = 22
}
```

Trade overlay uses `Radius.lg` (14pt). Buttons use `Radius.sm` (6pt). Chips use `Radius.xs` (4pt).

## 5. Spacing — 4pt grid

```swift
enum Spacing {
    static let s1: CGFloat  = 4
    static let s2: CGFloat  = 8
    static let s3: CGFloat  = 12
    static let s4: CGFloat  = 16
    static let s5: CGFloat  = 20
    static let s6: CGFloat  = 24
    static let s7: CGFloat  = 32
    static let s8: CGFloat  = 40
    static let s9: CGFloat  = 56
    static let s10: CGFloat = 72
}
```

## 6. Motion

```swift
enum Motion {
    static let fast: Double = 0.080  // 80ms
    static let base: Double = 0.120  // 120ms
    static let slow: Double = 0.180  // 180ms

    // Web: cubic-bezier(0.2, 0, 0, 1)
    // SwiftUI nearest equivalent — easeOut with duration override
    static func ease(_ duration: Double) -> Animation {
        .timingCurve(0.2, 0, 0, 1, duration: duration)
    }
}
```

Respect `accessibilityReduceMotion`: replace transforms with crossfades.

## 7. Shadow

```swift
extension View {
    func shadowOverlay() -> some View {
        self
            .shadow(color: .black.opacity(0.45), radius: 60, y: 24)
            .shadow(color: .black.opacity(0.25), radius: 20, y: 8)
            .overlay(
                RoundedRectangle(cornerRadius: Radius.lg)
                    .strokeBorder(Color.separatorStrong, lineWidth: 0.5)
            )
    }
    func shadowPop() -> some View {
        self
            .shadow(color: .black.opacity(0.35), radius: 32, y: 12)
    }
    func shadowChip() -> some View {
        self
            .shadow(color: .black.opacity(0.40), radius: 18, y: 6)
    }
}
```

## 8. Trade overlay — anatomy

Width: 320pt fixed. Height auto, ~140–180pt depending on content. Reference implementation in `claude-design/app.jsx`.

Sections, top to bottom:

1. **Source row.** Brand pill ("SPEEDY"), market type badge ("PREDICTION"), venue tag ("POLYMARKET"), match excerpt.
2. **Question row.** The Polymarket question text (multi-line allowed, 2-line max with truncation).
3. **Side row.** Two-segment Yes/No selector, semantic green/red, equal width.
4. **Size row.** Field with `$` prefix, JetBrains Mono input. Optional preset chips below ($20, $100, $500).
5. **Action row.** Cancel (ghost) + Confirm (primary). Confirm shows the calculated payout inline.

Padding: 11pt vertical × 14pt horizontal per row, separated by 0.5pt `separator` hairlines.

## 9. App icon (Speedy mark)

Linear gradient 160°: `#8E72FF → #7C5CFF (50%) → #5E3FE0`. White lightning-bolt cutout, drop-shadow `0 1px 0 rgba(0,0,0,0.18)`. Inner shadows top (white 32%) and bottom (black 18%). Outer glow purple at 30%, plus 0.5pt black separator at 40%.

Sizes for app icon set: 16, 32, 64, 128, 256, 512, 1024. Corner radius scales with the standard macOS app icon mask.

## 10. Tagline & voice

Tagline: **"Trade where you read."**

Voice (per design system §11):
- Direct, sentence case, no exclamation marks
- Numbers always show the unit (`$500`, `62¢`, `+3.4%`)
- Empty states are honest, not cute ("No tradeable market found." not "Hmm, nothing here yet!")

## 11. Things SwiftUI doesn't get for free

- **Custom hotkey overlay.** Use `NSPanel` with `.nonactivatingPanel`, `.canJoinAllSpaces`, `.fullScreenAuxiliary`. SwiftUI body inside via `NSHostingView`.
- **Backdrop blur.** SwiftUI's `.regularMaterial` is the right primitive but doesn't match web blur radius exactly — accept the drift, don't try to match it pixel-perfect.
- **Tabular numerals on live ticks.** SwiftUI's `.monospacedDigit()` works on system fonts. For custom Inter/JetBrains Mono, ensure the bundled font files include `tnum` and `lnum` OpenType features.

## 12. Open visual decisions deferred

- Light mode parity (claude-design is dark-only). Spec light tokens before public launch.
- Marketing site language (likely diverges from app density).
- Onboarding illustrations.
