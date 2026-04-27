#!/usr/bin/env bash
# Render each marketing HTML file to PNG via headless Chrome.
# Usage: ./render.sh
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

render() {
  local name="$1" w="$2" h="$3"
  local html="$DIR/$name.html"
  local out="$DIR/$name.png"
  echo "→ $name (${w}x${h})"
  "$CHROME" \
    --headless=new \
    --disable-gpu \
    --hide-scrollbars \
    --default-background-color=00000000 \
    --force-device-scale-factor=2 \
    --window-size="${w},${h}" \
    --screenshot="$out" \
    "file://$html" >/dev/null 2>&1
}

render icon     1024 1024
render wordmark 1600  600
render og-card  1200  630
render overlay  1400  900
render hero     1600 1100

echo
echo "Done. Output:"
ls -lh "$DIR"/*.png
