import numpy as np, json, cv2, os, pickle, sys
from scipy.ndimage import gaussian_filter1d
layout = json.load(open("layout.json"))
LINES = {l["id"]: l for page in layout.values() for l in page}
SIGK, CW = float(os.environ.get("SIGK", 0.5)), float(os.environ.get("CW", 3))
NARROW = dict(zip("есьгзэёо", [0.8, 0.8, 0.8, 0.8, 0.9, 0.9, 0.8, 0.9]))
WIDE = dict(zip("мшщжюытфыц", [1.4, 1.6, 1.7, 1.6, 1.5, 1.4, 1.4, 1.4, 1.4, 1.2]))
def prior(ch):
    if ch in NARROW: return NARROW[ch]
    if ch in WIDE: return WIDE[ch]
    if ch in ".,:;'!": return 0.35
    if ch in "-": return 0.6
    if ch in "–—": return 1.0
    if ch in "()[]{}|/": return 0.5
    if ch == " ": return 0.9
    if ch.isdigit(): return 0.8
    if ch.isupper(): return 1.4
    if ch in "&∨⊃¬→⇋≒": return 1.0
    return 1.0
def line_img(lid):
    page = lid.rsplit("_", 1)[0]
    a = np.load(f"ink2/{page}.npy")
    top, bot = np.load(f"lines/{lid}_seam.npy")
    H = a.shape[0]; yy = np.arange(H)[:, None]
    m = (yy >= top[None, :]) & (yy < bot[None, :])
    L = LINES[lid]
    return np.where(m, a, 0)[L["y0"]:L["y1"]]
def core_band(w):
    m = (w > 90).astype(float)
    p = gaussian_filter1d(m.sum(1), 2)
    if p.max() == 0: return 0, w.shape[0]
    k = int(np.argmax(p)); t = 0.40 * p[k]
    a = k
    while a > 0 and p[a - 1] >= t: a -= 1
    b = k
    while b < len(p) - 1 and p[b + 1] >= t: b += 1
    return a, b + 1
def cut_costs(w, xt, bl, sw):
    m = w > 90
    H, W = m.shape
    cost = np.full(W, 6.0)
    for x in range(W):
        col = m[:, x]
        if not col.any(): cost[x] = 0.0; continue
        d = np.diff(np.r_[0, col.astype(int), 0]); s = np.nonzero(d == 1)[0]; e = np.nonzero(d == -1)[0]
        if len(s) == 1:
            ln = e[0] - s[0]; c = (s[0] + e[0]) / 2
            if ln <= 1.8 * sw:
                inside = (xt - 0.15 * (bl - xt)) <= c <= bl + 0.15 * (bl - xt)
                cost[x] = 0.6 if inside else 2.5
                # prefer the lower half of the core (connectors)
                if inside: cost[x] += 0.6 * abs(c - (bl - 0.25 * (bl - xt))) / max(1, bl - xt)
            else: cost[x] = 3.5
        elif len(s) == 2: cost[x] = 4.5
    return cost
def stroke_width(w):
    m = (w > 90).astype(np.uint8)
    if m.sum() == 0: return 2
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    sk = dt[dt > 0]
    return max(1.5, 2 * float(np.median(sk)))
def segment(w, text, widths, xh):
    """returns cut x positions (len(text)+1)"""
    H, W = w.shape
    xt, bl = core_band(w)
    sw = stroke_width(w)
    cost = cut_costs(w, xt, bl, sw)
    n = len(text)
    E = np.array([widths.get(c, prior(c)) for c in text]) * xh
    E = E * (W / E.sum()) * 0.5 + E * 0.5        # pull toward the observed word width
    E = E * (W / E.sum())
    sig = SIGK * E + 2
    INF = 1e18
    MINW = np.maximum(2, np.where([c in ".,:;'" for c in text], 0.15, 0.4) * E)
    # dp[i][x] = best cost with i-th cut at x
    dp = np.full((n + 1, W + 1), INF); bk = np.zeros((n + 1, W + 1), int)
    dp[0, 0] = 0
    cc = np.r_[cost, 0.0]
    xs = np.arange(W + 1)
    for i in range(1, n + 1):
        lo = 0
        for x in range(1, W + 1):
            if i == n and x != W: continue
            prev = dp[i - 1, :x]
            wd = x - xs[:x]
            tot = prev + ((wd - E[i - 1]) / sig[i - 1]) ** 2 + (cc[x] * CW if i < n else 0)
            tot = np.where(wd < MINW[i - 1], INF, tot)
            j = int(np.argmin(tot)); dp[i, x] = tot[j]; bk[i, x] = j
    cuts = [W]
    for i in range(n, 0, -1): cuts.append(bk[i, cuts[-1]])
    return cuts[::-1], (xt, bl, sw), dp[n, W]
def load_items():
    items = []
    for ln in open("trans.txt", encoding="utf-8"):
        ln = ln.rstrip("\n")
        if not ln.strip(): continue
        parts = [p.strip() for p in ln.split("|")]
        lid, words = parts[0], parts[1:]
        L = LINES.get(lid)
        if L is None: print("no line", lid); continue
        if len(words) != len(L["words"]):
            print("count mismatch", lid, len(words), len(L["words"])); continue
        for (s, e), t in zip(L["words"], words):
            if t == "#" or not t: continue
            items.append((lid, s, e, t))
    return items
if __name__ == "__main__":
    items = load_items()
    print(len(items), "words,", sum(len(t) for *_, t in items), "chars")
    cache = {}
    widths = {}
    for it in range(3):
        res = []
        obs = {}
        for lid, s, e, t in items:
            if lid not in cache: cache[lid] = line_img(lid)
            li = cache[lid]
            w = li[:, max(0, s - 2):e + 2]
            ys = np.nonzero((w > 60).any(1))[0]
            y0, y1 = ys[0], ys[-1] + 1
            w = w[y0:y1]
            xs_ = np.nonzero((w > 60).any(0))[0]
            w = w[:, xs_[0]:xs_[-1] + 1]
            s0 = max(0, s - 2) + int(xs_[0])
            xt, bl = core_band(w)
            xh = max(6, bl - xt)
            cuts, (xt, bl, sw), sc = segment(w, t, widths, xh)
            res.append(dict(lid=lid, s=s0, e=s0 + w.shape[1], t=t, y0=int(y0), cuts=[int(c) for c in cuts], xt=int(xt), bl=int(bl), sw=sw, score=float(sc / len(t))))
            for c, a, b in zip(t, cuts[:-1], cuts[1:]):
                obs.setdefault(c, []).append((b - a) / xh)
        widths = {c: float(np.median(v)) for c, v in obs.items() if len(v) >= 3}
        print("iter", it, "mean score", np.mean([r["score"] for r in res]))
    json.dump(dict(res=res, widths=widths), open("seg.json", "w"), ensure_ascii=False)
