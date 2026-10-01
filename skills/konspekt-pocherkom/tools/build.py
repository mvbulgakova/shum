import json, numpy as np, os, pickle
from cand import prep
from seg import segment, core_band
C = json.load(open("cand.json")); EM = json.load(open("em.json"))["cuts"]; widths = json.load(open("seg.json"))["widths"]
glyphs = []; words = []
for wi, o in enumerate(C):
    w, x0, y0, xt, bl, sw = prep((o["lid"], o["x0"] + 2, o["x0"] + o["w"] - 2, o["t"]))
    t = o["t"]; W = w.shape[1]; xh = max(6, bl - xt)
    if len(t) == 1: cuts = [0, W]
    elif EM[wi]["cuts"] is not None: cuts = EM[wi]["cuts"]
    elif o["picks"] is not None:
        P = [0] + o["cands"] + [W]; cuts = [0] + [P[p] for p in o["picks"]] + [W]
    else:
        cuts, _, sc = segment(w, t, widths, xh)
        if sc >= 1e17: continue
    words.append(dict(i=wi, lid=o["lid"], t=t, cuts=[int(c) for c in cuts], xh=int(xh), bl=int(bl)))
    m = w > 90
    for k, ch in enumerate(t):
        if ch == " ": continue
        a, b = cuts[k], cuts[k + 1]
        if b - a < 2: continue
        crop = w[:, a:b]
        def yc(col):
            ys = np.nonzero(m[:, col])[0]
            return None if len(ys) == 0 else float((ys.mean() - bl) / xh)
        glyphs.append(dict(ch=ch, prev=t[k - 1] if k > 0 else "^", next=t[k + 1] if k + 1 < len(t) else "$",
                           img=crop.copy(), bl=int(bl), xh=int(xh), sw=float(sw), word=wi, pos=k,
                           ein=yc(a) if k > 0 else None, eout=yc(b - 1) if k + 1 < len(t) else None,
                           wy0=int(y0), src=o["lid"], plain=o["lid"].startswith("l4")))
import re
lx = {}
for wd in words:
    if len(re.findall("[а-яё]", wd["t"])) >= 2: lx.setdefault(wd["lid"], []).append(wd["xh"])
allm = float(np.median([v for L in lx.values() for v in L]))
for g in glyphs:
    wt = C[g["word"]]["t"]
    g["lxh"] = float(np.median(lx[g["src"]])) if g["src"] in lx else allm
    g["lower_word"] = len(re.findall("[а-яё]", wt)) >= 2
# базовая линия строки — по словам из строчных букв; для заглавных/формул берём её
lbl = {}
for g in glyphs:
    if g["lower_word"]: lbl.setdefault(g["src"], {})[g["word"]] = g["wy0"] + g["bl"]
for g in glyphs:
    if g["lower_word"]: continue
    ys = np.nonzero((g["img"] > 60).any(1))[0]
    if g["ch"].isalnum() and g["ch"] not in "дзруфцщДЦЩУФpqyjgfΓ" and len(ys):
        g["bl"] = int(ys[-1] - 0.04 * g["xh"])
    elif g["src"] in lbl:
        g["bl"] = int(round(np.median(list(lbl[g["src"]].values())) - g["wy0"]))
    else:
        ys = np.nonzero((g["img"] > 60).any(1))[0]
        if len(ys) and g["ch"] not in "дзруфцщДЦЩУФpqy(),;Γ": g["bl"] = int(ys[-1])
pickle.dump(dict(glyphs=glyphs, words=words), open("glyphs.pkl", "wb"))
from collections import Counter
cnt = Counter(g["ch"] for g in glyphs)
print(len(glyphs), "glyphs", len(cnt), "classes")
print(" ".join(f"{c}:{n}" for c, n in sorted(cnt.items(), key=lambda x: -x[1])))
