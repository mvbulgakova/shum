import json, sys
from PIL import Image, ImageDraw, ImageFont
from qa2 import G, order
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
FB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
classes = sys.argv[1].split(","); XH = int(sys.argv[2]) if len(sys.argv) > 2 else 24
allids = {}; rows = []
W = 1900
for ch in classes:
    ids = order([i for i, g in enumerate(G) if g["ch"] == ch]); allids[ch] = ids
    tiles = []
    for n, gi in enumerate(ids):
        g = G[gi]; s = XH / g["xh"]
        im = Image.fromarray(255 - g["img"]).resize((max(1, int(g["img"].shape[1] * s)), max(1, int(g["img"].shape[0] * s))))
        cv = Image.new("L", (max(im.width, 24) + 4, int(3.4 * XH) + 16), 255); yb = int(2.2 * XH)
        cv.paste(im, (2, yb - int(g["bl"] * s)))
        d = ImageDraw.Draw(cv); d.line([(0, yb), (cv.width, yb)], fill=210)
        d.rectangle([0, cv.height - 15, cv.width, cv.height], fill=235); d.text((2, cv.height - 15), str(n), fill=0, font=F)
        tiles.append(cv)
    hdr = Image.new("L", (40, int(3.4 * XH) + 16), 200); ImageDraw.Draw(hdr).text((6, 20), ch, fill=0, font=FB)
    tiles = [hdr] + tiles
    x = y = rowh = 0; pos = []
    for t in tiles:
        if x + t.width > W and x: x = 0; y += rowh + 3; rowh = 0
        pos.append((x, y)); x += t.width + 3; rowh = max(rowh, t.height)
    blk = Image.new("L", (W, y + rowh + 8), 120)
    for t, p in zip(tiles, pos): blk.paste(t, p)
    rows.append(blk)
H = sum(r.height for r in rows); sh = Image.new("L", (W, H), 0); y = 0
for r in rows: sh.paste(r, (0, y)); y += r.height
sh.save("qa.png"); json.dump(allids, open("qa_multi.json", "w"), ensure_ascii=False); print(sh.size, {c: len(v) for c, v in allids.items()})
