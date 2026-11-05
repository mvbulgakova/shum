# Автоотбор экземпляров букв: цельные, не обрезанные соседями, с нормальными пропорциями.
import pickle, json, sys, numpy as np, cv2
def ok(g):
    ch = g["ch"]
    if not (ch.isalpha() and "а" <= ch.lower() <= "я" or ch in "ёЁ"): return False
    a = g["img"]; m = (a > 90).astype(np.uint8)
    if m.sum() < 40: return False
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    areas = st[1:, cv2.CC_STAT_AREA]; tot = areas.sum()
    big = int(np.argmax(areas)) + 1
    dots = ch in "йЙёЁ"
    if areas.max() / tot < (0.8 if dots else 0.9): return False
    if n - 1 > (4 if dots else 3): return False
    xh = max(g["lxh"], 8); bl = g["bl"]; h, w = m.shape
    ys, xs = np.nonzero(lab == big)
    if w < 0.25 * xh or w > 2.6 * xh: return False
    # у края не должно быть чернил вне полосы строчных (обрывки соседних букв)
    top, bot = bl - 1.3 * xh, bl + 0.35 * xh
    desc = ch in "друзфцщДЦЩУЗфбвй" or ch.isupper()
    for x in (0, 1, w - 2, w - 1):
        col = np.nonzero(m[:, x])[0]
        if len(col) == 0: continue
        bad = ((col < top) | (col > bot)) if not desc else ((col < bl - 2.4 * xh) | (col > bl + 1.4 * xh))
        if bad.sum() > 1: return False
    # высота: строчная не должна быть крошечной или гигантской
    ext = ys.max() - ys.min() + 1
    if ch.islower() and ext < 0.45 * xh and ch not in "ъь": return False
    if ext > 4.2 * xh: return False
    # плотность: не клякса
    if m.sum() > 0.62 * w * h: return False
    return True
SAFE = "оеасилявчкгмпхыьэюзбшС"      # буквы, которые режутся надёжно; беглые н, р, т, у, д — только вручную
def run(pkl, out):
    D = pickle.load(open(pkl, "rb")); K = {}
    for i, g in enumerate(D["glyphs"]):
        if g["ch"] in SAFE and ok(g): K.setdefault(g["ch"], []).append(i)
    for ch, ids in list(K.items()):
        ws = np.array([D["glyphs"][i]["img"].shape[1] / max(D["glyphs"][i]["lxh"], 8) for i in ids]); med = np.median(ws)
        K[ch] = [i for i, w in zip(ids, ws) if 0.7 * med <= w <= 1.4 * med]
    json.dump(K, open(out, "w"), ensure_ascii=False)
    print(sum(len(v) for v in K.values()), "из", len(D["glyphs"]), {c: len(v) for c, v in sorted(K.items(), key=lambda t: -len(t[1]))[:14]})
if __name__ == "__main__": run(sys.argv[1], sys.argv[2])
