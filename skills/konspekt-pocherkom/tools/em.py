import json, numpy as np, pickle, cv2
from cand import prep, candidates
from seg import prior
C = json.load(open("cand.json")); widths0 = json.load(open("seg.json"))["widths"]
FW, FH = 16, 24
def feat(w, a, b, bl, xh):
    y0 = int(bl - 2.2 * xh); y1 = int(bl + 1.2 * xh)
    sl = w[:, a:b].astype(np.float32) / 255
    pad_top = max(0, -y0); pad_bot = max(0, y1 - w.shape[0])
    sl = np.pad(sl, ((pad_top, pad_bot), (0, 0)))[max(0, y0) + 0:max(0, y0) + (y1 - y0)]
    if sl.shape[1] < 1: sl = np.zeros((y1 - y0, 1), np.float32)
    sl = cv2.dilate(sl, np.ones((2, 2), np.uint8))
    f = cv2.resize(sl, (FW, FH), interpolation=cv2.INTER_AREA)
    f = cv2.GaussianBlur(f, (3, 3), 0.8).ravel()
    n = np.linalg.norm(f); f = f / n if n > 0 else f
    return np.r_[f, 0.6 * np.log((b - a) / xh + 0.05)]
WORDS = []
for o in C:
    w, x0, y0, xt, bl, sw = prep((o["lid"], o["x0"] + 2, o["x0"] + o["w"] - 2, o["t"]))
    cands, cost = candidates(w, xt, bl, sw)
    WORDS.append(dict(o=o, w=w, bl=bl, xh=max(6, bl - xt), cands=cands, cost=cost))
def align(W_, protos, widths, use_t):
    o = W_["o"]; t = o["t"]; w = W_["w"]; Wd = w.shape[1]; xh = W_["xh"]; bl = W_["bl"]
    P = [0] + W_["cands"] + [Wd]; m = len(P); n = len(t)
    if n == 1: return [0, Wd], 0.0
    if m - 1 < n: return None, None
    E = np.array([widths.get(ch, prior(ch)) for ch in t]) * xh; E *= Wd / E.sum(); sig = 0.45 * E + 2
    INF = 1e18
    dp = np.full((n + 1, m), INF); bk = np.zeros((n + 1, m), int); dp[0, 0] = 0
    fc = {}
    for i in range(1, n + 1):
        ch = t[i - 1]
        for j in range(i, m - (n - i)):
            if i == n and j != m - 1: continue
            best, arg = INF, 0
            for k in range(i - 1, j):
                if dp[i - 1, k] >= INF: continue
                wd = P[j] - P[k]
                if wd > 3.5 * E[i - 1] + 3 * xh: continue
                v = dp[i - 1, k] + ((wd - E[i - 1]) / sig[i - 1]) ** 2 + (W_["cost"][P[j]] * 2 if i < n else 0)
                if use_t and ch in protos:
                    key = (k, j)
                    if key not in fc: fc[key] = feat(w, P[k], P[j], bl, xh)
                    d = np.min(np.linalg.norm(protos[ch] - fc[key], axis=1))
                    v += 12 * d * d
                if v < best: best, arg = v, k
            dp[i, j] = best; bk[i, j] = arg
    if dp[n, m - 1] >= INF: return None, None
    j = m - 1; cuts = [Wd]
    for i in range(n, 0, -1): j = bk[i, j]; cuts.append(P[j])
    return cuts[::-1], dp[n, m - 1] / n
def run():
    widths = dict(widths0); protos = {}
    for it in range(4):
        inst = {}; tot = []
        for W_ in WORDS:
            cuts, sc = align(W_, protos, widths, it > 0)
            W_["cuts"] = cuts; W_["score"] = sc
            if cuts is None: continue
            tot.append(sc)
            for k, ch in enumerate(W_["o"]["t"]):
                a, b = cuts[k], cuts[k + 1]
                if b - a < 2: continue
                inst.setdefault(ch, []).append((feat(W_["w"], a, b, W_["bl"], W_["xh"]), (b - a) / W_["xh"]))
        protos = {}; widths = {}
        for ch, L in inst.items():
            F = np.array([f for f, _ in L]); ws = np.array([x for _, x in L])
            if len(L) >= 3:
                D = np.linalg.norm(F[:, None] - F[None], axis=2)
                k = max(2, len(L) // 5)
                dens = np.sort(D, axis=1)[:, 1:k + 1].mean(1)
                core = np.argsort(dens)[:max(3, len(L) // 3)]
                # k-medoids-lite: pick up to 4 diverse prototypes among core
                pr = [core[0]]
                for _ in range(min(4, len(core)) - 1):
                    dd = np.min(D[np.ix_(core, pr)], axis=1); pr.append(core[int(np.argmax(dd))])
                protos[ch] = F[pr]; widths[ch] = float(np.median(ws[core]))
        print("iter", it, "words", len(tot), "mean", np.mean(tot))
    return widths
if __name__ == "__main__":
    widths = run()
    out = [dict(i=i, cuts=None if W_["cuts"] is None else [int(c) for c in W_["cuts"]]) for i, W_ in enumerate(WORDS)]
    json.dump(dict(cuts=out, widths=widths), open("em.json", "w"))
