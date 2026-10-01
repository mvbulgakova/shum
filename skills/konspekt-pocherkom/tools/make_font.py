# Собирает MariaHand.otf из размеченных экземпляров букв (glyphs.pkl + keep.json).
import pickle, gzip, json, os, numpy as np, cv2, potrace, re, sys
from collections import defaultdict, Counter
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
FALLBACK = os.path.join(HERE, "BadScript-Regular.ttf")
XH = 380          # высота строчной буквы в единицах шрифта
UP = 4            # во сколько раз увеличиваем скан перед обводкой
# glyphs.pkl — все вырезанные из лекций экземпляры (картинка, базовая линия, соседи);
# keep.json — какие из них проверены глазами и годятся (номера в glyphs.pkl по буквам)
_gp = "glyphs.pkl" if os.path.exists("glyphs.pkl") else os.path.join(DATA, "glyphs.pkl.gz")
D = pickle.load(gzip.open(_gp, "rb") if _gp.endswith(".gz") else open(_gp, "rb")); G = D["glyphs"]
K = json.load(open("keep.json" if os.path.exists("keep.json") else os.path.join(DATA, "keep.json")))

def gname(ch, k=None):
    b = f"uni{ord(ch):04X}"
    return b if k is None else f"{b}.v{k}"

_TC = {}
def trace(g):
    if id(g) in _TC: return _TC[id(g)]
    r = _trace(g); _TC[id(g)] = r; return r
def _trace(g):
    """контуры экземпляра в единицах шрифта -> RecordingPen, ширина"""
    a = g["img"].astype(np.float32)
    rows = np.nonzero((a > 60).any(1))[0]
    ref = g["xh"] if (g["lower_word"] or not g["ch"].isalpha()) else g["lxh"]
    if g["ch"].isupper() and g["lower_word"]: ref = g["lxh"] if g["lxh"] > 0 else g["xh"]
    ref = (0.5 * ref + 0.5 * g["lxh"]) if g["lower_word"] else g["lxh"]   # гасим ошибки оценки высоты
    S = XH / ref
    # убираем обрывки соседних строк и чужие надстрочные штрихи
    m0 = (a > 60).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m0, 8)
    if n > 2:
        bl = g["bl"]; areas = st[1:, cv2.CC_STAT_AREA]; big = areas.max()
        keepdia = g["ch"] in "йЙёЁ!?:;i" or not g["ch"].isalnum()
        for i in range(1, n):
            y, h, ar = st[i, cv2.CC_STAT_TOP], st[i, cv2.CC_STAT_HEIGHT], st[i, cv2.CC_STAT_AREA]
            if ar == big: continue
            out = (y + h < bl - 2.4 * ref) or (y > bl + 1.3 * ref)
            hi = (y + h < bl - 1.15 * ref) and ar < 0.35 * big and not keepdia
            lo = (y > bl + 0.15 * ref) and ar < 0.35 * big and g["ch"] not in ",;"
            if out or hi or lo: a[lab == i] = 0
    big = cv2.resize(a, (a.shape[1] * UP, a.shape[0] * UP), interpolation=cv2.INTER_CUBIC)
    big = cv2.GaussianBlur(big, (0, 0), UP * 0.35)
    m = big > 105
    # выравниваем толщину линии (сканы разных лекций темнее/светлее)
    r = (0.088 * ref - g["sw"]) * UP / 2
    r = float(np.clip(r, -0.35 * g["sw"] * UP, 1.2 * UP))
    if r < -0.5:
        m = cv2.distanceTransform(m.astype(np.uint8), cv2.DIST_L2, 5) > -r
    elif r > 0.5:
        m = cv2.distanceTransform((~m).astype(np.uint8), cv2.DIST_L2, 5) <= r
    m = np.pad(m, 2)
    pl = potrace.Bitmap(~m[::-1]).trace(turdsize=UP * UP * 4, alphamax=1.0, opticurve=True, opttolerance=0.25)
    H = m.shape[0]
    blp = (g["bl"]) * UP + 2                       # базовая линия в увеличенных пикселях (сверху)
    def P(p): return ((p.x - 2) / UP * S, (p.y - (H - blp)) / UP * S)
    rp = RecordingPen()
    for c in pl:
        rp.moveTo(P(c.start_point))
        for sgm in c.segments:
            if sgm.is_corner: rp.lineTo(P(sgm.c)); rp.lineTo(P(sgm.end_point))
            else: rp.curveTo(P(sgm.c1), P(sgm.c2), P(sgm.end_point))
        rp.closePath()
    w = a.shape[1] * S
    return rp, w, S

def main(out="MariaHand.otf", seed=0, name="MariaHand"):
    rs = np.random.RandomState(100 + seed)
    variants = {}                       # ch -> list of (glyph-id in G)
    for ch, ids in K.items():
        if ch.strip() and ids: variants[ch] = ids
    shapes = {}                         # glyph name -> (RecordingPen, advance)
    meta = {}                           # glyph name -> (prev, next)
    for ch, ids in variants.items():
        for k, gi in enumerate(ids):
            g = G[gi]; rp, w, S = trace(g)
            ov = 0.35 * g["sw"] * S if (g["ch"].isalpha() and g["next"].isalpha()) else 0
            adv = max(40, w - ov)
            if not (g["ch"].isalpha() or g["ch"].isdigit()): adv += 25    # знаки чуть свободнее
            shapes[gname(ch, k)] = (rp, adv); meta[gname(ch, k)] = (g["prev"], g["next"])
    # базовый (cmap) глиф: лучший экземпляр в начале слова, иначе первый (самый типичный)
    base = {}
    for ch, ids in variants.items():
        starts = [k for k, gi in enumerate(ids) if G[gi]["prev"] == "^"]
        lower = ch.islower() and ch.isalpha() and ord(ch) > 0x400
        if lower and starts: k0 = starts[0] if seed == 0 else starts[rs.randint(len(starts))]
        else: k0 = 0 if seed == 0 or len(ids) < 2 else rs.randint(min(3, len(ids)))
        base[ch] = k0
    # --- производные символы, которых нет в лекциях
    def copy(src_ch, dst_ch, sx=1.0, sy=None, dy=0, extra=None):
        if src_ch not in variants: return
        sy = sx if sy is None else sy
        variants.setdefault(dst_ch, [])
        n = len(variants[src_ch])
        for k in range(n):
            rp, adv = shapes[gname(src_ch, k)]
            r2 = RecordingPen(); rp.replay(TransformPen(r2, (sx, 0, 0, sy, 0, dy)))
            if extra: extra(r2, adv * sx, k)
            shapes[gname(dst_ch, k)] = (r2, adv * sx); meta[gname(dst_ch, k)] = meta[gname(src_ch, k)]
        variants[dst_ch] = list(range(n)); base[dst_ch] = base[src_ch]
    dot = shapes.get(gname(".", 0))
    def dots(r2, adv, k):              # две точки над е -> ё
        if not dot: return
        j = (k * 37 % 11) / 11.0
        for i, dx in enumerate((0.22, 0.58)):
            dot[0].replay(TransformPen(r2, (1, 0, 0, 1, adv * (dx + 0.06 * j) - 20, XH * (1.0 + 0.12 * ((j + i * 0.5) % 1)))))
    copy("е", "ё", extra=dots)
    copy("Е", "Ё", extra=dots)
    def tick(r2, adv, k):              # хвостик ъ: короткий штрих слева сверху
        d = shapes.get(gname("-", k % max(1, len(variants.get("-", [1])))))
        if d: d[0].replay(TransformPen(r2, (0.6, 0, 0, 0.6, -60, XH * 0.55)))
    copy("ь", "ъ", extra=tick)
    # заглавные, которых нет: увеличенная строчная (в прописях у этих букв та же форма)
    for lo, up in zip("абвгдежзийклмнопрстуфхцчшщъыьэюя", "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"):
        if up not in variants: copy(lo, up, 1.35)
    # латиница/цифры, которых нет: похожие по форме её буквы
    LAT = {"D": "Д", "a": "а", "e": "е", "o": "о", "c": "с", "x": "х", "y": "у", "u": "и", "n": "п", "r": "г",
           "k": "к", "d": "д", "b": "б", "C": "С", "E": "Е", "O": "О", "P": "Р", "T": "Т", "K": "К",
           "M": "М", "H": "Н", "X": "Х", "0": "о", "—": "–", "−": "–"}
    for dst, src in LAT.items():
        if dst not in variants and src in variants: copy(src, dst, 1.0 if dst != "0" else 1.25)
    # знаки, составленные из её же штрихов
    def compose(dst, parts, n=4):
        # parts: [(src_ch, sx, dx_frac_of_prev_adv, dy)] ; dx считается от конца предыдущей части
        if dst in variants or not all(p[0] in variants for p in parts): return
        variants[dst] = list(range(n)); base[dst] = 0
        for k in range(n):
            r2 = RecordingPen(); x = 0; right = 0
            for src, sx, gap, dy in parts:
                kk = k % len(variants[src]); rp, a = shapes[gname(src, kk)]
                x0 = gap[1] if isinstance(gap, tuple) else x + gap
                rp.replay(TransformPen(r2, (sx, 0, 0, sx, x0, dy))); x = x0 + a * sx; right = max(right, x)
            shapes[gname(dst, k)] = (r2, right + 20); meta[gname(dst, k)] = ("^", "$")
    compose(";", [(",", 1, 0, 0), (".", 1, -70, XH * 0.75)])
    compose("!", [("1", 0.9, 0, XH * 0.25), (".", 1, -90, 0)])
    compose("№", [("N", 1, 0, 0), ("о", 0.6, 10, XH * 0.6)])
    compose("„", [(",", 1, 0, 0), (",", 1, -10, 0)])
    compose("“", [(",", 1, 0, XH * 1.6), (",", 1, -10, XH * 1.6)])
    compose("«", [(",", 1, 0, XH * 1.6), (",", 1, -10, XH * 1.6)])
    compose("»", [(",", 1, 0, XH * 1.6), (",", 1, -10, XH * 1.6)])
    compose("\"", [(",", 1, 0, XH * 1.6), (",", 1, -10, XH * 1.6)])
    compose("'", [(",", 1, 0, XH * 1.6)])
    compose("=", [("-", 0.8, 0, XH * 0.25), ("-", 0.8, ("abs", 15), XH * 0.6)])
    compose("+", [("-", 0.8, 0, XH * 0.45), ("1", 0.6, ("abs", 60), 0)])
    # --- всё, чего нет в лекциях вовсе, берём из Bad Script (самый похожий готовый шрифт), подогнав по высоте
    import os
    if os.path.exists(FALLBACK):
        from fontTools.ttLib import TTFont
        fb_font = TTFont(FALLBACK); fgs = fb_font.getGlyphSet(); fcm = fb_font.getBestCmap()
        k = XH / 505.0
        want = [c for c in range(0x20, 0x250)] + list(range(0x400, 0x460)) + list(range(0x2010, 0x2070)) + [0x2116, 0x2192, 0x2190, 0x2194]
        for cp in want:
            ch = chr(cp)
            if ch in variants or cp not in fcm or ch.isspace(): continue
            gn = fcm[cp]; r2 = RecordingPen()
            from fontTools.pens.recordingPen import DecomposingRecordingPen
            dr = DecomposingRecordingPen(fgs); fgs[gn].draw(dr)
            dr.replay(TransformPen(r2, (k, 0, 0.18 * k, k, 0, 0)))   # лёгкий наклон как у неё
            variants[ch] = [0]; base[ch] = 0
            shapes[gname(ch, 0)] = (r2, fgs[gn].width * k); meta[gname(ch, 0)] = ("^", "$")
    # --- сборка
    order = [".notdef", "space"] + sorted(shapes)
    fb = FontBuilder(1000, isTTF=False); fb.setupGlyphOrder(order)
    cmap = {32: "space", 160: "space"}
    for ch in variants: cmap[ord(ch)] = gname(ch, base[ch])
    fb.setupCharacterMap(cmap)
    cs, adv = {}, {}
    p = T2CharStringPen(500, None); cs[".notdef"] = p.getCharString(); adv[".notdef"] = 500
    p = T2CharStringPen(int(XH * 0.95), None); cs["space"] = p.getCharString(); adv["space"] = int(XH * 0.95)
    for n, (rp, a) in shapes.items():
        p = T2CharStringPen(round(a), None); rp.replay(p); cs[n] = p.getCharString(); adv[n] = round(a)
    fb.setupCFF(name.replace(" ", ""), {"FullName": name}, cs, {})
    fb.setupHorizontalMetrics({n: (adv[n], 0) for n in order})
    fb.setupHorizontalHeader(ascent=950, descent=-420)
    fb.setupNameTable({"familyName": name, "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=950, sTypoDescender=-420, sTypoLineGap=0, usWinAscent=1100, usWinDescent=500, sxHeight=XH, sCapHeight=int(XH * 2))
    fb.setupPost()
    # --- calt: вариант буквы зависит от соседей (прежде всего — реальная связка из лекций)
    letters = [c for c in variants if c.isalpha()]
    allv = {c: [gname(c, k) for k in range(len(variants[c]))] for c in variants}
    cls = lambda c: "@A_" + f"{ord(c):04X}"
    fea = ["languagesystem DFLT dflt;", "languagesystem cyrl dflt;", "languagesystem latn dflt;"]
    for c in variants: fea.append(f"{cls(c)} = [{' '.join(allv[c])}];")
    groups = defaultdict(list)
    for i, c in enumerate(sorted(letters)): groups[i % 3].append(c)
    rules = []
    rnd = np.random.RandomState(7 + seed)
    for c in letters:
        n = len(variants[c])
        if n < 2: continue
        ctx = [(k,) + meta[gname(c, k)] for k in range(n)]
        used = set()
        # 1) точная связка: тот же сосед слева и справа
        for k, pv, nx in ctx:
            if pv in variants and nx in variants and pv.isalpha() and nx.isalpha():
                rules.append(f"sub {cls(pv)} {gname(c, base[c])}' {cls(nx)} by {gname(c, k)};"); used.add(k)
        # 2) тот же сосед слева (связка входа) — по одному варианту на соседа, разные для разных соседей
        byprev = defaultdict(list)
        for k, pv, nx in ctx:
            if pv in variants and pv.isalpha(): byprev[pv].append(k)
        for pv, ks in byprev.items():
            rules.append(f"sub {cls(pv)} {gname(c, base[c])}' by {gname(c, ks[rnd.randint(len(ks))])};")
        # 3) тот же сосед справа (выход)
        bynext = defaultdict(list)
        for k, pv, nx in ctx:
            if nx in variants and nx.isalpha(): bynext[nx].append(k)
        for nx, ks in bynext.items():
            rules.append(f"sub {gname(c, base[c])}' {cls(nx)} by {gname(c, ks[rnd.randint(len(ks))])};")
        # 4) прочие соседи слева: варианты по кругу, чтобы одна буква не повторялась одинаково
        mids = [k for k, pv, nx in ctx if pv != "^"] or list(range(n))
        for gidx, grp in groups.items():
            rest = [x for x in grp if x not in byprev and x in variants]
            if not rest: continue
            k = mids[(gidx * 7 + ord(c) + seed * 5) % len(mids)]
            rules.append(f"sub [{' '.join(cls(x) for x in rest)}] {gname(c, base[c])}' by {gname(c, k)};")
    # вариативность знаков и цифр: чередование по левому соседу
    for c in variants:
        if c.isalpha() or len(variants[c]) < 2: continue
        n = len(variants[c])
        for gidx, grp in groups.items():
            k = (gidx + 1 + seed) % n
            rules.append(f"sub [{' '.join(cls(x) for x in grp if x in variants)}] {gname(c, base[c])}' by {gname(c, k)};")
    fea.append("lookup ctx {"); fea += ["  " + r for r in rules]; fea.append("} ctx;")
    fea.append("feature calt { lookup ctx; } calt;")
    fea_s = "\n".join(fea)
    addOpenTypeFeaturesFromString(fb.font, fea_s)
    fb.save(out)
    cnt = {c: len(v) for c, v in variants.items()}
    print(out, "глифов:", len(order), "правил calt:", len(rules))
    return cnt

if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "fonts")
    for seed, suf in enumerate("ABC"):
        cnt = main(f"{outdir}/MariaHand-{suf}.otf", seed, f"MariaHand {suf}")
    print(" ".join(f"{c}:{n}" for c, n in sorted(cnt.items())))
