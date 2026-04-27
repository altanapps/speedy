# docs

User-facing documentation assets.

## Files

- `demo.gif` — the hero animation embedded at the top of the
  top-level README. ~12 seconds of the full flow: highlight a sentence
  in an article → ⌃⌃ → matched market with prices → click Yes → ⌘↵ →
  "Order placed."

## Re-recording

If the overlay design or flow changes, re-record:

1. Use macOS screen capture (⇧⌘5 → Record Selected Portion). Pick a
   tight rectangle around the cursor's path + the overlay area.
2. Trim to 8–12 seconds in QuickTime (Edit → Trim, ⌘T).
3. Save the trimmed `.mp4` somewhere outside `docs/` — `*.mp4` is
   gitignored to keep raw recordings local.
4. Convert to GIF with [gifski](https://gif.ski):

   ```bash
   brew install gifski ffmpeg
   ffmpeg -i your-recording.mp4 \
     -vf "fps=15,scale=900:-1:flags=lanczos" \
     -f yuv4mpegpipe - 2>/dev/null \
     | gifski --fps 15 --quality 70 -o docs/demo.gif -
   ```

   Aim for under 5MB so it loads cleanly in the README on mobile and
   inside Twitter previews.
