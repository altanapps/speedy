import SwiftUI

/// Design tokens for the Speedy overlay. Values mirror
/// `claude-design/Speedy Design System.html` exactly — do not invent new
/// colors, radii, or spacing here. If you need a new value, add it to the
/// design system first and then port it.
///
/// All public surface lives in three enums (`Speedy.Color`, `Speedy.Radius`,
/// `Speedy.Spacing`) plus a small `Font` helper. Feature code should never
/// hard-code a hex/radius/spacing value outside this file.
enum Speedy {

    // MARK: - Color

    /// Color tokens. Web `--token-name` maps to `Speedy.Color.tokenName`.
    enum ColorToken {
        // Brand
        static let purple        = Color(hex: 0x7C5CFF)
        static let purplePressed = Color(hex: 0x6B4DEF)
        static let purpleTint    = Color(hex: 0x7C5CFF, alpha: 0.18)
        static let purpleSubtle  = Color(hex: 0x7C5CFF, alpha: 0.10)

        // Backgrounds
        static let bgSystem    = Color(hex: 0x0B0B0E)
        static let bgElevated  = Color(hex: 0x18181C)
        static let bgElevated2 = Color(hex: 0x1F1F24)

        // Material tints — overlaid on top of `.regularMaterial` to nudge
        // the panel towards the spec's slightly darker glass.
        static let matTint      = Color(red: 28/255, green: 28/255, blue: 32/255).opacity(0.62)
        static let matTintThick = Color(red: 20/255, green: 20/255, blue: 24/255).opacity(0.78)
        static let matTintThin  = Color(red: 40/255, green: 40/255, blue: 46/255).opacity(0.42)

        // Separators
        static let separator       = Color.white.opacity(0.08)
        static let separatorStrong = Color.white.opacity(0.14)
        static let separatorOpaque = Color(hex: 0x2A2A30)

        // Labels
        static let label           = Color.white.opacity(0.96)
        static let labelSecondary  = Color.white.opacity(0.62)
        static let labelTertiary   = Color.white.opacity(0.40)
        static let labelQuaternary = Color.white.opacity(0.22)

        // Fills
        static let fill           = Color.white.opacity(0.08)
        static let fillSecondary  = Color.white.opacity(0.05)
        static let fillTertiary   = Color.white.opacity(0.03)
        static let fillQuaternary = Color.white.opacity(0.02)

        // Semantic
        static let green  = Color(hex: 0x30D158)
        static let red    = Color(hex: 0xFF453A)
        static let orange = Color(hex: 0xFF9F0A)
        static let yellow = Color(hex: 0xFFD60A)
        static let blue   = Color(hex: 0x0A84FF)

        // Market type badge backgrounds (per design system §07)
        static let badgePred  = Color(hex: 0xA88AFF)
        static let badgeStock = Color(hex: 0x7AC5FF)
        static let badgePerp  = Color(hex: 0xFFB068)
        static let badgeComm  = Color(hex: 0xE0CC7A)
    }

    // MARK: - Radius

    enum Radius {
        static let xs: CGFloat  = 4
        static let sm: CGFloat  = 6
        static let md: CGFloat  = 10
        static let lg: CGFloat  = 14
        static let xl: CGFloat  = 18
        static let xxl: CGFloat = 22
    }

    // MARK: - Spacing — 4pt grid

    enum Spacing {
        static let s1: CGFloat  = 4
        static let s2: CGFloat  = 8
        static let s3: CGFloat  = 12
        static let s4: CGFloat  = 16
        static let s5: CGFloat  = 20
        static let s6: CGFloat  = 24
        static let s7: CGFloat  = 32
    }

    // MARK: - Motion

    enum Motion {
        // Web: cubic-bezier(0.2, 0, 0, 1)
        static func ease(_ duration: Double) -> Animation {
            .timingCurve(0.2, 0, 0, 1, duration: duration)
        }
        static let fast = ease(0.080)
        static let base = ease(0.120)
        static let slow = ease(0.180)
    }

    // MARK: - Font

    /// Custom-font wrapper. Falls back to SF Pro / SF Mono if the bundled
    /// TTF didn't register (SwiftUI's `.custom(_:size:)` already does the
    /// fallback silently — this helper just makes call sites readable).
    enum Font {
        /// Inter, the body / UI font.
        static func inter(_ size: CGFloat, weight: Inter = .regular) -> SwiftUI.Font {
            .custom(weight.fontName, size: size)
        }
        /// JetBrains Mono, used for all numerics. `monospacedDigit()` is
        /// applied at the call site so digits don't jitter on live updates.
        static func mono(_ size: CGFloat, weight: Mono = .regular) -> SwiftUI.Font {
            .custom(weight.fontName, size: size).monospacedDigit()
        }

        enum Inter {
            case regular, medium, semibold
            var fontName: String {
                switch self {
                case .regular:  return "Inter-Regular"
                case .medium:   return "Inter-Medium"
                case .semibold: return "Inter-SemiBold"
                }
            }
        }
        enum Mono {
            case regular, medium, semibold
            var fontName: String {
                switch self {
                case .regular:  return "JetBrainsMono-Regular"
                case .medium:   return "JetBrainsMono-Medium"
                case .semibold: return "JetBrainsMono-SemiBold"
                }
            }
        }
    }
}

// MARK: - Color hex helper

extension Color {
    /// `Color(hex: 0x7C5CFF)` — convenience for tokens-from-design-system.
    init(hex: UInt32, alpha: Double = 1.0) {
        let r = Double((hex >> 16) & 0xFF) / 255.0
        let g = Double((hex >>  8) & 0xFF) / 255.0
        let b = Double( hex        & 0xFF) / 255.0
        self.init(.sRGB, red: r, green: g, blue: b, opacity: alpha)
    }
}
