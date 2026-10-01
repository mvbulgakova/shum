# python3 ctiles.py SHEET "line1,line2" -> ct.png: каждый связный кусок отдельно, по порядку слева направо
import sys, json, numpy as np, cv2, os
from PIL import Image, ImageDraw, ImageFont
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
CJ = json.load(open(f"cv_{sys.argv[1]}.json")); lines = sys.argv[2].split(",")
def load(page):
    for d in ("ink2", "ink_n"):
        p = f"{d}/{page}.npy"
        if os.path.exists(p): return np.load(p)
rows = []
for ln in lines:
    page, li = ln.split(":"); li = int(li)
    cs = sorted([(k, c) for k, c in CJ.items() if c["page"] == page and c["li"] == li and c["w"] * c["h"] > 30], key=lambda t: t[1]["x"])
    a = load(page); tiles = []
    for k, c in cs:
        sub = a[c["oy"]:c["oy1"], c["ox"]:c["ox1"]]
        n, lab, st, _ = cv2.connectedComponentsWithStats((sub > 60).astype(np.uint8), 8)
        m = lab == c["lab"]; img = np.where(m, sub, 0)[c["y"] - c["oy"]:c["y"] - c["oy"] + c["h"], c["x"] - c["ox"]:c["x"] - c["ox"] + c["w"]]
        im = Image.fromarray(255 - img).convert("RGB"); s = 1.6
        im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))))
        t = Image.new("RGB", (max(im.width, 26) + 4, 110), "white"); t.paste(im, (2, max(0, 92 - im.height)))
        ImageDraw.Draw(t).text((1, 95), k, fill=(200, 0, 0), font=F); tiles.append(t)
    W = 1900; x = y = rh = 0; pos = []
    for t in tiles:
        if x + t.width > W: x = 0; y += rh + 2; rh = 0
        pos.append((x, y)); x += t.width + 2; rh = max(rh, t.height)
    r = Image.new("RGB", (W, y + rh + 6), (150, 150, 150))
    for t, p in zip(tiles, pos): r.paste(t, p)
    ImageDraw.Draw(r).text((W - 80, y + rh - 10), ln, fill=(0, 0, 0), font=F); rows.append(r)
H = sum(r.height for r in rows); sh = Image.new("RGB", (1900, H)); y = 0
for r in rows: sh.paste(r, (0, y)); y += r.height
sh.save("ct.png"); print(sh.size)
