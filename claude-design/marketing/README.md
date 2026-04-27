# marketing — rendered assets

Marketing visuals for Speedy: app icon, wordmark, social card, and
landing-page hero. Each asset is authored as standalone HTML and
rendered to PNG via headless Chrome.

## Files

| HTML | Output | Size | Usage |
|---|---|---|---|
| `icon.html` | `icon.png` | 1024×1024 @2x | App icon (`.icns` source) |
| `wordmark.html` | `wordmark.png` | 1600×600 @2x | "Speedy" wordmark with bolt |
| `og-card.html` | `og-card.png` | 1200×630 @2x | Open Graph / Twitter card |
| `overlay.html` | `overlay.png` | 1400×900 @2x | Hero shot of the matched-state overlay |
| `hero.html` | `hero.png` | 1600×1100 @2x | Landing-page hero composition |

## Re-rendering

```bash
./render.sh
```

Requires Google Chrome installed at the standard `/Applications` path.
The script uses `--headless=new` (Chrome 112+) with `@2x` scale.

The HTML files are the source of truth — edit those, then re-render.
PNGs are committed so consumers (README, future landing page) can
reference them without needing the build step.
