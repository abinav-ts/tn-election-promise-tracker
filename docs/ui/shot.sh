#!/bin/zsh
# usage: docs/ui/shot.sh <page.html> <width> <outfile> [theme]
# Needs: python3 -m http.server 8765 -d site/public. Pages are captured in 7000px slices and stitched
# (one tall window hangs headless Chrome). Phone widths use an iframe because headless Chrome enforces a minimum window width.
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PAGE=$1; W=$2; OUT=$3; THEME=${4:-light}; SL=7000
D=${TMPDIR:-/tmp}/ept_shot_$$; mkdir -p $D
for i in 0 1 2 3; do
  echo "<body style='margin:0;background:#777;overflow:hidden'><iframe src='http://localhost:${PORT:-8765}/$PAGE?theme=$THEME&palette=${PAL:-purple}' width=$W height=30000 style='border:0;display:block;margin-top:-$((i*SL))px'></iframe>" > $D/w.html
  "$CH" --headless=new --hide-scrollbars --virtual-time-budget=8000 --window-size=$((W>520?W:520)),$SL --screenshot="$D/s$i.png" "file://$D/w.html" >/dev/null 2>&1
done
python3 - "$D" "$OUT" "$W" <<'P'
import sys, glob
from PIL import Image
d, out, w = sys.argv[1], sys.argv[2], int(sys.argv[3])
parts = [Image.open(f"{d}/s{i}.png").convert("RGB").crop((0, 0, w, 7000)) for i in range(4) if __import__("os").path.exists(f"{d}/s{i}.png")]
im = Image.new("RGB", (w, 7000 * len(parts)))
for i, p in enumerate(parts): im.paste(p, (0, 7000 * i))
bg = im.getpixel((w - 1, im.height - 1)); y = im.height - 1
while y > 0 and all(im.getpixel((x, y)) == bg for x in range(0, w, 7)): y -= 1
im.crop((0, 0, w, min(im.height, y + 24))).save(out)
P
rm -rf $D
