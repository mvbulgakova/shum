# Ручной выбор символов по рамке: строки в picks.txt
#   СИМВОЛ PAGE x0 y0 x1 y1 [bl]      (координаты страницы; bl — базовая линия, по умолчанию низ рамки)
# Берутся только связные куски, у которых центр внутри рамки. -> picks.pkl (как glyphs.pkl) + picks.png
import sys, os, pickle, numpy as np, cv2, gzip, json
from PIL import Image, ImageDraw, ImageFont
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
def load(page):
    for d in ("ink2", "ink_n"):
        p = f"{d}/{page}.npy"
        if os.path.exists(p): return np.load(p)
    raise SystemExit("нет страницы " + page)
G = pickle.load(gzip.open("/home/user/shum/skills/konspekt-pocherkom/data/glyphs.pkl.gz", "rb"))["glyphs"]
def page_xh(page):
    if page.startswith("n1"): return 24.0
    v = [g["xh"] for g in G if g["src"].startswith(page + "_") and g["lower_word"] and g["ch"] in "аеиноспт"]
    if not v: v = [g["xh"] for g in G if g["src"][:2] == page[:2] and g["lower_word"]]
    return float(np.median(v))
def tile(g, ch, k):
    img, xh, bl = g["img"], g["lxh"], g["bl"]; top = 0
    S = 60 / xh
    t = Image.fromarray(255 - img[max(0, bl - int(2.6 * xh)):bl + int(1.4 * xh)]).convert("RGB")
    t = t.resize((max(1, int(t.width * S)), max(1, int(t.height * S))))
    c = Image.new("RGB", (max(t.width, 50) + 6, t.height + 20), "white"); c.paste(t, (3, 0))
    dd = ImageDraw.Draw(c); yb = int(min(2.6 * xh, bl) * S); dd.line([(0, yb), (c.width, yb)], fill=(120, 200, 120))
    dd.text((2, t.height + 2), f"{k}:{ch}", fill=(200, 0, 0), font=F); return c

out = []; tiles = []
cache = {}
for ln in open(sys.argv[1] if len(sys.argv) > 1 else "picks.txt", encoding="utf-8"):
    ln = ln.split("#!")[0].strip()
    if not ln: continue
    p = ln.split()
    if p[1].startswith("@"):
        sheet, ids = p[1][1:].split(":"); CJ = json.load(open(f"cv_{sheet}.json"))
        cs = [CJ[i] for i in ids.split("+")]
        page = cs[0]["page"]; ch = p[0]
        if page not in cache: cache[page] = load(page)
        a = cache[page]
        X0 = min(c["x"] for c in cs) - 2; X1 = max(c["x"] + c["w"] for c in cs) + 2
        Y0 = min(c["y"] for c in cs) - 2; Y1 = max(c["y"] + c["h"] for c in cs) + 2
        lid = f"{page}_{cs[0]['li']:02d}"
        LY = {l["id"]: l["y0"] for f in ("layout.json", "new/layout.json") for pg in json.load(open(f)).values() for l in pg}
        bls = [LY[lid] + g["wy0"] + g["bl"] for g in G if g["src"] == lid and g["lower_word"]]
        bl = int(p[2]) if len(p) > 2 else (int(np.median(bls)) if bls else Y1)
        sub = a[cs[0]["oy"]:cs[0]["oy1"], cs[0]["ox"]:cs[0]["ox1"]]
        n, lab, st, cen = cv2.connectedComponentsWithStats((sub > 60).astype(np.uint8), 8)
        keep = np.isin(lab, [c["lab"] for c in cs])
        full = np.zeros(a.shape, np.uint8); full[cs[0]["oy"]:cs[0]["oy1"], cs[0]["ox"]:cs[0]["ox1"]] = np.where(keep, sub, 0)
        top = min(Y0, bl - 60); bot = max(Y1, bl + 30)
        img = full[max(0, top):bot, X0:X1]; top = max(0, top)
        xs = np.nonzero((img > 60).any(0))[0]; img = img[:, xs.min():xs.max() + 1]
        m = (img > 90).astype(np.uint8); dt = cv2.distanceTransform(m, cv2.DIST_L2, 3)
        sw = max(1.5, 2 * float(np.median(dt[dt > 0])))
        xh = page_xh(page)
        g = dict(ch=ch, prev="^", next="$", img=img.copy(), bl=int(bl - top), xh=int(round(xh)), lxh=xh, sw=sw,
                 word=-1, pos=0, ein=None, eout=None, src=f"{page}_pick", plain=False, lower_word=False, wy0=top, manual=True)
        out.append(g); tiles.append(tile(g, ch, len(out) - 1)); continue
    ch, page = p[0], p[1]; x0, y0, x1, y1 = map(int, p[2:6]); bl = int(p[6]) if len(p) > 6 else y1
    raw = len(ch) > 1 and ch.endswith("!"); ch = ch[:-1] if raw else ch
    if page not in cache: cache[page] = load(page)
    a = cache[page]
    X0, Y0, X1, Y1 = max(0, x0 - 40), max(0, y0 - 40), min(a.shape[1], x1 + 40), min(a.shape[0], y1 + 40)
    big = a[Y0:Y1, X0:X1]
    n, lab, st, cen = cv2.connectedComponentsWithStats((big > 60).astype(np.uint8), 8)
    keep = np.zeros(big.shape, bool)
    for i in range(1, n):
        cx, cy = cen[i]; cx += X0; cy += Y0
        ar_, w_, h_ = st[i, cv2.CC_STAT_AREA], st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT]
        dotty = page.startswith(("n2", "n3")) and ar_ < 80 and max(w_, h_) < 14 and ch not in ".:;!?ij…ё"
        if x0 <= cx <= x1 and y0 <= cy <= y1 and ar_ >= 4 and not dotty: keep |= lab == i
    if raw:
        keep = np.zeros(big.shape, bool); keep[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0] = True
        # отбрасываем мелкие обрывки, которые остались от соседей после обрезки рамкой
        kb = (np.where(keep, big, 0) > 60).astype(np.uint8)
        n2_, lab2, st2, _ = cv2.connectedComponentsWithStats(kb, 8)
        for i in range(1, n2_):
            if st2[i, cv2.CC_STAT_AREA] < 15: keep[lab2 == i] = False
    img = np.where(keep, big, 0)
    ys, xs = np.nonzero(img > 60)
    if len(xs) == 0: print("пусто:", ln); continue
    img = img[:, xs.min():xs.max() + 1]
    top = Y0
    m = (img > 90).astype(np.uint8); dt = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    sw = max(1.5, 2 * float(np.median(dt[dt > 0]))) if m.any() else 2.0
    xh = page_xh(page)
    g = dict(ch=ch, prev="^", next="$", img=img.copy(), bl=int(bl - top), xh=int(round(xh)), lxh=xh, sw=sw,
             word=-1, pos=0, ein=None, eout=None, src=f"{page}_pick", plain=False, lower_word=False, wy0=top, manual=True)
    out.append(g); tiles.append(tile(g, ch, len(out) - 1))
W = 1900; x = y = rh = 0; pos = []
for t in tiles:
    if x + t.width > W and x: x = 0; y += rh + 4; rh = 0
    pos.append((x, y)); x += t.width + 4; rh = max(rh, t.height)
sh = Image.new("RGB", (W, max(1, y + rh)), (190, 190, 190))
for t, q in zip(tiles, pos): sh.paste(t, q)
sh.save("picks.png"); pickle.dump(out, open("picks.pkl", "wb"))
from collections import Counter
print(len(out), dict(Counter(g["ch"] for g in out)))
