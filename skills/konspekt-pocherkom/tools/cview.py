# python3 cview.py SHEETNAME page:line[:x0-x1] ... -> cv_SHEET.png + cv_SHEET.json (номера связных кусков)
import sys, json, numpy as np, cv2, os
from PIL import Image, ImageDraw, ImageFont
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
L1 = json.load(open("layout.json")); L2 = json.load(open("new/layout.json"))
def load(page):
    for d in ("ink2", "ink_n"):
        p = f"{d}/{page}.npy"
        if os.path.exists(p): return np.load(p)
name = sys.argv[1]; Z = float(os.environ.get("Z", 3)); W = 1900
rows = []; comps = {}; nid = 0
for spec in sys.argv[2:]:
    parts = spec.split(":"); page, li = parts[0], int(parts[1])
    L = (L1.get(page) or L2.get(page))[li]
    a = load(page); y0, y1 = max(0, L["y0"] - 4), min(a.shape[0], L["y1"] + 4)
    if len(parts) > 2: x0, x1 = map(int, parts[2].split("-"))
    else:
        xs = np.nonzero((a[y0:y1] > 60).any(0))[0]; x0, x1 = max(0, xs.min() - 3), xs.max() + 4
    sub = a[y0:y1, x0:x1]
    n, lab, st, cen = cv2.connectedComponentsWithStats((sub > 60).astype(np.uint8), 8)
    zz = min(Z, (W - 10) / sub.shape[1])
    im = Image.fromarray(255 - sub).convert("RGB").resize((int(sub.shape[1] * zz), int(sub.shape[0] * zz)))
    cvs = Image.new("RGB", (W, im.height + 34), "white"); cvs.paste(im, (5, 17)); d = ImageDraw.Draw(cvs)
    d.text((W - 120, 0), f"{page}:{li}", fill=(120, 120, 120), font=F)
    cols = [(220, 0, 0), (0, 140, 0), (0, 0, 230), (190, 0, 190), (0, 130, 150)]
    for i in range(1, n):
        x, y, w, h, ar = st[i]
        if ar < 6: continue
        c = cols[nid % 5]
        d.rectangle([5 + x * zz, 17 + y * zz, 5 + (x + w) * zz, 17 + (y + h) * zz], outline=c)
        ty = 2 if nid % 2 == 0 else 17 + im.height + 2
        d.text((5 + x * zz, ty), str(nid), fill=c, font=F)
        comps[nid] = dict(page=page, x=int(x + x0), y=int(y + y0), w=int(w), h=int(h), lab=int(i), ox=int(x0), oy=int(y0), oy1=int(y1), ox1=int(x1), bl=int(L["base"]), li=li)
        nid += 1
    rows.append(cvs)
H = sum(r.height + 4 for r in rows); sh = Image.new("RGB", (W, H), (170, 170, 170)); y = 0
for r in rows: sh.paste(r, (0, y)); y += r.height + 4
sh.save(f"cv_{name}.png"); json.dump(comps, open(f"cv_{name}.json", "w")); print(sh.size, nid)
