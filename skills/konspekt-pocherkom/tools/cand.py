import numpy as np, json, os, sys
from seg import line_img, core_band, cut_costs, stroke_width, prior, load_items
from PIL import Image, ImageDraw, ImageFont
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
FL = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
def candidates(w, xt, bl, sw):
    h = bl - xt
    band = w.copy(); band[:max(0, int(xt - 0.25 * h))] = 0; band[int(bl + 0.25 * h) + 1:] = 0
    cost = cut_costs(band, xt, bl, sw)
    W = len(cost); c = []
    ok = cost <= 2.6
    x = 0
    while x < W:
        if ok[x]:
            y = x
            while y + 1 < W and ok[y + 1]: y += 1
            if x > 0 and y < W - 1:
                seg = cost[x:y + 1]
                step = max(5, int(0.45 * h))
                if y - x > step:   # long connector: several candidates
                    c += list(range(x + step // 2, y, step))
                else:
                    c.append(x + int(np.argmin(seg + 0.01 * np.abs(np.arange(len(seg)) - len(seg) / 2))))
            x = y + 1
        else: x += 1
    return sorted(set(c)), cost
def dp_pick(cands, cost, text, W, xh, widths):
    n = len(text)
    E = np.array([widths.get(ch, prior(ch)) for ch in text]) * xh
    E = E * (W / E.sum())
    sig = 0.45 * E + 2
    P = [0] + cands + [W]; m = len(P)
    INF = 1e18
    dp = np.full((n + 1, m), INF); bk = np.zeros((n + 1, m), int); dp[0, 0] = 0
    for i in range(1, n + 1):
        for j in range(1, m):
            if i == n and j != m - 1: continue
            if i < n and j == m - 1: continue
            best, arg = INF, 0
            for k in range(j):
                if dp[i - 1, k] >= INF: continue
                v = dp[i - 1, k] + ((P[j] - P[k] - E[i - 1]) / sig[i - 1]) ** 2 + (cost[P[j]] * 2 if i < n else 0)
                if v < best: best, arg = v, k
            dp[i, j] = best; bk[i, j] = arg
    if dp[n, m - 1] >= INF: return None
    j = m - 1; picks = []
    for i in range(n, 0, -1):
        picks.append(j); j = bk[i, j]
    picks = picks[::-1][:-1]           # candidate indices (1-based in P) excluding end
    return [p for p in picks]          # indices into P, i.e. 1..len(cands)
def prep(item):
    lid, s, e, t = item
    li = line_img(lid)
    w = li[:, max(0, s - 2):e + 2]
    ys = np.nonzero((w > 60).any(1))[0]; y0 = ys[0]; w = w[ys[0]:ys[-1] + 1]
    xs = np.nonzero((w > 60).any(0))[0]; x0 = max(0, s - 2) + xs[0]; w = w[:, xs[0]:xs[-1] + 1]
    xt, bl = core_band(w); sw = stroke_width(w)
    return w, int(x0), int(y0), xt, bl, sw
if __name__ == "__main__":
    items = load_items()
    widths = json.load(open("seg.json"))["widths"]
    out = []
    for it in items:
        lid, s, e, t = it
        w, x0, y0, xt, bl, sw = prep(it)
        cands, cost = candidates(w, xt, bl, sw)
        xh = max(6, bl - xt)
        if len(t) == 1: picks = []
        else:
            picks = dp_pick(cands, cost, t, w.shape[1], xh, widths) if len(cands) >= len(t) - 1 else None
        out.append(dict(lid=lid, x0=x0, y0=y0, w=int(w.shape[1]), h=int(w.shape[0]), t=t, cands=[int(c) for c in cands], picks=None if picks is None else [int(p) for p in picks], xt=int(xt), bl=int(bl), sw=float(sw)))
    json.dump(out, open("cand.json", "w"), ensure_ascii=False)
    print(len(out), "words;", sum(o["picks"] is None for o in out), "infeasible")
