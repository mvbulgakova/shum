import cv2, numpy as np, glob, os, json
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
from PIL import Image, ImageDraw, ImageFont
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
def seam(cost, y_lo, y_hi):
    """min-cost left->right path within rows [y_lo,y_hi), moves -1/0/+1"""
    c = cost[y_lo:y_hi].astype(np.float64)
    H, W = c.shape
    mid = (H - 1) / 2
    c = c + 0.002 * (np.arange(H)[:, None] - mid) ** 2
    acc = c.copy(); back = np.zeros((H, W), np.int8)
    for x in range(1, W):
        prev = acc[:, x - 1]
        up = np.r_[np.inf, prev[:-1]]; dn = np.r_[prev[1:], np.inf]
        st = np.vstack([up, prev, dn]); k = st.argmin(0)
        acc[:, x] += st[k, np.arange(H)] + 0.05 * (k != 1); back[:, x] = k - 1
    y = np.zeros(W, int); y[-1] = acc[:, -1].argmin()
    for x in range(W - 1, 0, -1): y[x - 1] = y[x] + back[y[x], x]
    return y + y_lo
def page_lines(a, small):
    m = (a > 80)
    prof = gaussian_filter1d(m.sum(1).astype(float), 4 if small else 7)
    dist = 22 if small else 38
    pk, _ = find_peaks(prof, distance=dist, prominence=prof.max() * 0.06)
    cost = (a.astype(np.float32) / 255.0) * 10
    seams = [np.zeros(a.shape[1], int)]
    for p, q in zip(pk[:-1], pk[1:]):
        seams.append(seam(cost, p + (q - p) // 5, q - (q - p) // 5 + 1))
    seams.append(np.full(a.shape[1], a.shape[0]))
    return pk, seams
def split_words(lm, gap):
    col = (lm > 80).sum(0) > 0
    xs = np.nonzero(col)[0]
    if len(xs) == 0: return []
    ws, s, prev = [], xs[0], xs[0]
    for x in xs[1:]:
        if x - prev > gap: ws.append((s, prev + 1)); s = x
        prev = x
    ws.append((s, prev + 1))
    return [w for w in ws if (lm[:, w[0]:w[1]] > 80).sum() > 20]
import sys
INK, OUT = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("ink", ".")
if __name__ == "__main__":
    os.makedirs(OUT + "/strips", exist_ok=True); os.makedirs(OUT + "/lines", exist_ok=True)
    for f in glob.glob(OUT + "/strips/*"): os.remove(f)
    layout = {}
    for p in sorted(glob.glob(INK + "/*.npy")):
        name = os.path.basename(p)[:-4]; a = np.load(p); small = name.startswith("l4")
        pk, seams = page_lines(a, small)
        H, W = a.shape; yy = np.arange(H)[:, None]
        L = []; rows = []
        for i, c in enumerate(pk):
            top, bot = seams[i], seams[i + 1]
            mask = (yy >= top[None, :]) & (yy < bot[None, :])
            lm = np.where(mask, a, 0)
            ys = np.nonzero((lm > 80).any(1))[0]
            if len(ys) == 0: continue
            y0, y1 = ys[0], ys[-1] + 1
            crop = lm[y0:y1]
            ws = split_words(crop, 9 if small else 14)
            if not ws: continue
            np.save(f"{OUT}/lines/{name}_{len(L):02d}.npy", crop)
            np.save(f"{OUT}/lines/{name}_{len(L):02d}_seam.npy", np.vstack([top, bot]))
            L.append(dict(id=f"{name}_{len(L):02d}", y0=int(y0), y1=int(y1), base=int(c), words=[[int(s), int(e)] for s, e in ws]))
            S = 1.6 if small else 1.1
            im = Image.fromarray(255 - crop).convert("RGB")
            im = im.resize((int(im.width * S), int(im.height * S)))
            cv = Image.new("RGB", (im.width + 70, im.height + 12), "white"); cv.paste(im, (70, 0))
            d = ImageDraw.Draw(cv)
            for k, (s, e) in enumerate(ws):
                d.rectangle([70 + s * S, im.height + 3, 70 + e * S, im.height + 9], fill=[(230, 60, 60), (40, 160, 40)][k % 2])
            d.text((2, im.height // 2 - 10), f"{len(L)-1}", fill=(200, 0, 0), font=FONT)
            d.text((2, im.height // 2 + 10), f"[{len(ws)}]", fill=(0, 0, 200), font=FONT)
            rows.append(cv)
        layout[name] = L
        sheets, cur, hh = [], [], 0
        for r in rows:
            if hh + r.height > 1500 and cur: sheets.append(cur); cur, hh = [], 0
            cur.append(r); hh += r.height + 4
        if cur: sheets.append(cur)
        for si, sh in enumerate(sheets):
            Wd = max(r.width for r in sh); Hh = sum(r.height + 4 for r in sh)
            img = Image.new("RGB", (Wd, Hh), (200, 200, 200)); y = 0
            for r in sh: img.paste(r, (0, y)); y += r.height + 4
            img.save(f"{OUT}/strips/{name}_{si}.png")
        print(name, len(L), "lines", len(sheets), "sheets")
    json.dump(layout, open(OUT + "/layout.json", "w"), ensure_ascii=False)
