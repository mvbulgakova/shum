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
            DESC = "друзфцщДЦЩУЗфy"
            out = (y + h < bl - (2.6 if g["ch"].isupper() or g["ch"] in "бдвфйё" else 2.0) * ref) or (y > bl + (1.9 if g["ch"] in DESC else 1.0) * ref)
            hi = (y + h < bl - 1.15 * ref) and ar < 0.35 * big and not keepdia and not g["ch"].isupper() and g["ch"] not in "бвдфйё"
            lo = (y > bl + 0.15 * ref) and ar < 0.35 * big and g["ch"] not in ",;" + DESC
            # обрывки соседних букв у краёв разреза и мелкие кляксы
            x, w = st[i, cv2.CC_STAT_LEFT], st[i, cv2.CC_STAT_WIDTH]
            cyr = g["ch"].islower() and "а" <= g["ch"] <= "я" and g["ch"] not in "ыйюжк"
            edge = cyr and (x <= 1 or x + w >= a.shape[1] - 1) and ar < 0.3 * big
            speck = ar < (0.04 if (keepdia or not cyr) else 0.12) * big
            # отдельный кусок далеко над/под основной частью буквы — чужой штрих
            bi = 1 + int(np.argmax(areas)); by, bh = st[bi, cv2.CC_STAT_TOP], st[bi, cv2.CC_STAT_HEIGHT]
            gap = max(y - (by + bh), by - (y + h))
            far = gap > 0.35 * ref and ar < 0.3 * big and not keepdia and g["ch"] not in "йЙёЁ"
            if out or hi or lo or edge or speck or far: a[lab == i] = 0
    # тонкие «хвосты» на краях разреза (кусок связки соседней буквы): срезаем, если штрих
    # у самого края уходит выше или ниже основной полосы строчной буквы
    if g["ch"].isalpha() and a.shape[1] > 6:
        bl = g["bl"]; top = bl - 1.25 * ref; bot = bl + 0.25 * ref
        if g["ch"] not in "бвдйруфцщзЁёБВДЙРУФЦЩЗbdfhklpqyt" and g["ch"].islower():
            for side in (range(0, min(4, a.shape[1])), range(a.shape[1] - 1, max(a.shape[1] - 5, -1), -1)):
                for xx in side:
                    ys = np.nonzero(a[:, xx] > 60)[0]
                    if len(ys) == 0: continue
                    bad = (ys < top) | (ys > bot)
                    a[ys[bad], xx] = 0
    # пустые поля слева/справа (бывают у перевырезанных букв) — убираем, иначе разрыв в слове
    if g["ch"].isalpha():
        cols = np.nonzero((a > 60).any(0))[0]
        if len(cols): a = a[:, cols[0]:cols[-1] + 1]
    big = cv2.resize(a, (a.shape[1] * UP, a.shape[0] * UP), interpolation=cv2.INTER_CUBIC)
    big = cv2.GaussianBlur(big, (0, 0), UP * 0.35)
    m = big > 90
    # выравниваем толщину линии (сканы разных лекций темнее/светлее)
    # толщину меряем по самой маске (у фото и сканов разная «мягкость» краёв)
    dtm = cv2.distanceTransform(m.astype(np.uint8), cv2.DIST_L2, 5)
    from skimage.morphology import skeletonize
    sk = skeletonize(m)
    swm = 2 * float(np.median(dtm[sk])) if sk.any() else g["sw"] * UP
    r = (0.088 * ref * UP - swm) / 2
    r = float(np.clip(r, -0.4 * swm, 1.2 * UP))
    if r < -0.5:
        # утоньшаем, но тонкие штрихи (петли «д», «у», «з», соединения) не теряем:
        # оставляем вокруг скелета линию не тоньше целевой
        tr = 0.4 * 0.088 * ref * UP
        near_sk = cv2.distanceTransform((~sk).astype(np.uint8), cv2.DIST_L2, 5) <= tr
        m = (dtm > -r) | (near_sk & m)
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

# ---------- соединения между буквами
RS = 0.25                                  # масштаб растра для поиска входа/выхода штриха
YT, YB = 1150, 500                         # растр по высоте: от YT до -YB единиц шрифта
NB = 6                                     # число корзин по высоте входа
BTARGET = [XH * (0.06 + 0.17 * b) for b in range(NB)]

class _Flat(RecordingPen):
    pass

def raster(rp, adv):
    """контуры -> маска (even-odd) в масштабе RS; x от -50 единиц"""
    from fontTools.pens.basePen import BasePen
    polys = []
    class P(BasePen):
        def __init__(s): super().__init__(None); s.cur = []
        def _moveTo(s, p): s.cur = [p]
        def _lineTo(s, p): s.cur.append(p)
        def _curveToOne(s, a, b, c):
            p0 = np.array(s.cur[-1], float)
            for t in np.linspace(0, 1, 6)[1:]:
                s.cur.append(tuple((1-t)**3*p0 + 3*(1-t)**2*t*np.array(a) + 3*(1-t)*t*t*np.array(b) + t**3*np.array(c)))
        def _closePath(s):
            if len(s.cur) > 2: polys.append(s.cur)
            s.cur = []
        _endPath = _closePath
    pen = P(); rp.replay(pen)
    W = int((adv + 200) * RS) + 2; H = int((YT + YB) * RS) + 2
    m = np.zeros((H, W), np.uint8)
    for q in polys:
        t = np.zeros_like(m)
        cv2.fillPoly(t, [np.array([[(x + 50) * RS, (YT - y) * RS] for x, y in q], np.int32)], 1)
        m ^= t
    return m

def _orient(rp):
    """знак площади самого большого контура (чтобы связка шла в ту же сторону и не дырявила букву)"""
    best, sg = 0, 1; cur = []
    for op, args in rp.value:
        if op == "moveTo": cur = [args[0]]
        elif op in ("lineTo", "curveTo", "qCurveTo"): cur.append(args[-1])
        elif op in ("closePath", "endPath") and len(cur) > 2:
            a = np.array(cur); ar = 0.5 * np.sum(a[:, 0] * np.roll(a[:, 1], -1) - np.roll(a[:, 0], -1) * a[:, 1])
            if abs(ar) > best: best, sg = abs(ar), np.sign(ar)
    return sg

def stroke_poly(p0, p1, c1, c2, w, rnd, sg):
    """штрих её толщины по кривой Безье: многоугольник, концы скруглены сужением"""
    ts = np.linspace(0, 1, 14)
    P0, P1, C1, C2 = map(lambda v: np.array(v, float), (p0, p1, c1, c2))
    pts = np.array([(1-t)**3*P0 + 3*(1-t)**2*t*C1 + 3*(1-t)*t*t*C2 + t**3*P1 for t in ts])
    d = np.gradient(pts, axis=0); d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    wob = 1 + 0.08 * np.sin(ts * np.pi * rnd.uniform(1, 3) + rnd.uniform(0, 6))
    hw = 0.5 * w * wob * (0.75 + 0.25 * np.sin(np.pi * np.clip(ts * 1.15, 0, 1)) ** 0.5)
    left = pts + nrm * hw[:, None]; right = pts - nrm * hw[:, None]
    poly = np.vstack([left, right[::-1]])
    a = 0.5 * np.sum(poly[:, 0] * np.roll(poly[:, 1], -1) - np.roll(poly[:, 0], -1) * poly[:, 1])
    if np.sign(a) != sg: poly = poly[::-1]
    return poly

def connections(shapes, variants):
    """для букв: версии .cN с дописанной связкой к входу на высоте BTARGET[N].
    Возвращает {N: (исходные глифы, новые глифы, глифы-следующие с входом в корзине N)}"""
    CYR = lambda c: ("а" <= c.lower() <= "я" or c in "ёЁ")
    src = [c for c in variants if c.isalpha() and CYR(c)]
    dstl = [c for c in variants if c.isalpha() and CYR(c) and c.islower()]
    ent, ext = {}, {}
    for c in set(src) | set(dstl):
        for k in range(len(variants[c])):
            n = gname(c, k); rp, adv = shapes[n]; m = raster(rp, adv)
            ys, xs = np.nonzero(m)
            if len(xs) == 0: continue
            yv = YT - ys / RS; xv = xs / RS - 50
            band = (yv > -0.15 * XH) & (yv < 1.15 * XH)
            if not band.any(): continue
            xb, yb = xv[band], yv[band]
            # вход: самые левые точки в полосе строчных
            L = xb <= xb.min() + 30
            ent[n] = (float(xb.min()), float(np.median(yb[L])))
            # выход: самые правые точки
            R = xb >= xb.max() - 30
            ext[n] = (float(xb.max()), float(np.median(yb[R])), adv)
    bucket = lambda y: int(np.clip(np.argmin([abs(y - t) for t in BTARGET]), 0, NB - 1))
    nxt = defaultdict(list)
    for n, (x, y) in ent.items():
        if n.startswith(tuple(gname(c) for c in dstl)) and x < 60: nxt[bucket(y)].append(n)
    rnd = np.random.RandomState(11)
    W = 0.085 * XH
    out = {b: ([], [], nxt[b]) for b in range(NB)}
    for c in src:
        for k in range(len(variants[c])):
            n = gname(c, k)
            if n not in ext: continue
            ex, ey, adv = ext[n]
            if ex < adv - 120: continue                 # буква кончается далеко от края — не тянем
            rp = shapes[n][0]; sg = _orient(rp)
            for b in range(NB):
                ty = BTARGET[b]
                if abs(ty - ey) < 0.07 * XH and ex > adv - 15: continue   # и так сходятся
                x0, y0 = ex - 0.6 * W, ey
                x1 = adv + 0.55 * W; y1 = ty
                dx = max(x1 - x0, 30)
                poly = stroke_poly((x0, y0), (x1, y1), (x0 + 0.45 * dx, y0 + 0.15 * (y1 - y0)),
                                   (x1 - 0.4 * dx, y1 - 0.05 * (y1 - y0)), W, rnd, sg)
                r2 = RecordingPen(); rp.replay(r2)
                r2.moveTo(tuple(poly[0]))
                for p in poly[1:]: r2.lineTo(tuple(p))
                r2.closePath()
                nn = f"{n}.c{b}"; shapes[nn] = (r2, adv)
                out[b][0].append(n); out[b][1].append(nn)
    print("связки:", sum(len(v[1]) for v in out.values()))
    return out

def main(out="MariaHand.otf", seed=0, name="MariaHand"):
    rs = np.random.RandomState(100 + seed)
    variants = {}                       # ch -> list of (glyph-id in G)
    for ch, ids in K.items():
        if len(ch) != 1: continue
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
    # метрики букв — по полосе строчных: хвосты вниз (у, р, д, з) и вверх могут заходить под соседей,
    # а расстояние между буквами считается по основной части (как пишется слитно)
    for n, (rp, adv) in list(shapes.items()):
        ch = chr(int(n[3:7], 16))
        if not ch.isalpha(): continue
        m = raster(rp, adv); ys, xs = np.nonzero(m)
        if len(xs) == 0: continue
        yv = YT - ys / RS; xv = xs / RS - 50
        band = (yv > -0.05 * XH) & (yv < 1.05 * XH)
        if band.sum() < 5: continue
        x0, x1 = float(xv[band].min()), float(xv[band].max())
        r2 = RecordingPen(); rp.replay(TransformPen(r2, (1, 0, 0, 1, -x0, 0)))
        shapes[n] = (r2, max(40, x1 - x0 + 0.13 * XH))
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
        if up not in variants and up not in "ГР": copy(lo, up, 1.35)
    # латиница/цифры, которых нет: похожие по форме её буквы
    # латиница, которой нет в её записях: её же буквы того же начертания (в прописи они совпадают)
    LAT = {"a": "а", "e": "е", "o": "о", "c": "с", "x": "х", "y": "у", "u": "и", "n": "п", "r": "г",
           "k": "к", "g": "д", "m": "т", "z": "з", "C": "С", "E": "Е", "O": "О", "P": "Р", "T": "Т", "K": "К",
           "M": "М", "H": "Н", "X": "Х", "B": "В", "A": "А", "D": "Д", "0": "о", "—": "–", "−": "–",
           "ℎ": "h", "φ": "ф", "ε": "з", "β": "б", "μ": "м", "S": "s", "U": "u", "W": "w", "Z": "з"}
    for dst, src in LAT.items():
        if dst not in variants and src in variants:
            copy(src, dst, 1.25 if dst in "0SUWZ" else (0.8 if dst == "ε" else 1.0))
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
    # математика и прочие знаки — её штрихами (symbols.py)
    import symbols
    symbols.build(shapes, variants, base, meta, gname, XH, seed)
    for src, dst in (("⊨", "⊧"), ("−", "−"), ("|", "∣"), ("∨", "∨")):
        if src in variants and dst not in variants: copy(src, dst)
    # комбинируемые точка и тильда над буквой (U+0307, U+0303): нулевая ширина, её точка / её волна
    for cch, src, sc, dy in (("\u0307", ".", 1.0, XH * 1.25), ("\u0303", "∼", 0.55, XH * 1.05)):
        if src not in variants or cch in variants: continue
        variants[cch] = []; base[cch] = 0
        for k in range(len(variants[src])):
            rp, a = shapes[gname(src, k)]
            r2 = RecordingPen(); rp.replay(TransformPen(r2, (sc, 0, 0, sc, -a * sc * 0.5 - XH * 0.15, dy)))
            shapes[gname(cch, k)] = (r2, 0); meta[gname(cch, k)] = ("^", "$"); variants[cch].append(k)
    # --- редкие знаки: если настоящих экземпляров меньше трёх, добавляем копии её же экземпляров
    #     с небольшим разбросом наклона, ширины и толщины (не чужой шрифт)
    rj = np.random.RandomState(500 + seed)
    for ch in list(variants):
        n = len(variants[ch])
        if n == 0 or n >= 3: continue
        for j in range(3 - n):
            rp, adv = shapes[gname(ch, j % n)]
            sx = 1 + rj.uniform(-0.08, 0.08); sl = rj.uniform(-0.07, 0.07); sy = 1 + rj.uniform(-0.06, 0.06)
            r2 = RecordingPen(); rp.replay(TransformPen(r2, (sx, 0, sl, sy, 0, 0)))
            k = n + j; shapes[gname(ch, k)] = (r2, adv * sx); meta[gname(ch, k)] = meta[gname(ch, j % n)]
            variants[ch].append(k)
    # --- соединения: «дописываем» штрих от выхода буквы к входу следующей (по высоте входа)
    conn = connections(shapes, variants)
    # --- сборка
    order = [".notdef", "space"] + sorted(shapes)
    fb = FontBuilder(1000, isTTF=False); fb.setupGlyphOrder(order)
    cmap = {32: "space", 160: "space"}
    for ch in variants: cmap[ord(ch)] = gname(ch, base[ch])
    # каждый вариант знака — ещё и на своём коде в области U+E000…, чтобы в формулах выбирать вариант случайно
    pua = {}; code = 0xE000
    for ch in sorted(symbols.MATHCLASS):
        if ch not in variants: continue
        pua[ch] = []
        for k in range(len(variants[ch])):
            cmap[code] = gname(ch, k); pua[ch].append(code); code += 1
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
    # после выбора вариантов: буква перед буквой с входом на высоте b -> её версия с дописанной связкой
    crules = []
    for b, (src, dst, nxt) in conn.items():
        if not src or not nxt: continue
        crules.append(f"sub [{' '.join(src)}]' [{' '.join(nxt)}] by [{' '.join(dst)}];")
    fea.append("lookup conn {"); fea += ["  " + r for r in crules]; fea.append("} conn;")
    fea.append("feature calt { lookup ctx; lookup conn; } calt;")
    fea_s = "\n".join(fea)
    addOpenTypeFeaturesFromString(fb.font, fea_s)
    fb.save(out)
    if seed == 0: write_math_tex(pua, os.path.join(os.path.dirname(out), "hand-math.tex"))
    cnt = {c: len(v) for c, v in variants.items()}
    print(out, "глифов:", len(order), "правил calt:", len(rules))
    return cnt

# команды формул -> знак
MATHCMD = {
    "vee": "∨", "lor": "∨", "wedge": "∧", "land": "∧", "neg": "¬", "lnot": "¬",
    "supset": "⊃", "subset": "⊂", "supseteq": "⊇", "subseteq": "⊆", "in": "∈", "notin": "∉",
    "vdash": "⊢", "models": "⊨", "vDash": "⊨", "to": "→", "rightarrow": "→", "leftarrow": "←", "gets": "←",
    "leftrightarrow": "↔", "Rightarrow": "⇒", "Leftarrow": "⇐", "Leftrightarrow": "⇔", "iff": "⇔",
    "equiv": "≡", "neq": "≠", "ne": "≠", "times": "×", "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥",
    "setminus": "∖", "emptyset": "∅", "varnothing": "∅", "forall": "∀", "exists": "∃", "top": "⊤", "bot": "⊥",
    "angle": "∠", "parallel": "∥", "triangle": "Δ", "Gamma": "Γ", "Delta": "Δ", "ldots": "…", "cdots": "⋯", "cdot": "⋅", "circ": "∘", "mid": "|", "vert": "|",
    "lbrace": "{", "rbrace": "}", "nvdash": "⊬", "nvDash": "⊭", "nmodels": "⊭", "sim": "∼",
    "langle": "⟨", "rangle": "⟩", "vdots": "⋮", "mapsto": "↦", "longleftrightarrow": "⟷",
    "Longleftrightarrow": "⟺", "ast": "∗", "bullet": "•", "alpha": "α", "beta": "β", "theta": "θ",
    "vartheta": "ϑ", "nu": "ν", "sigma": "σ", "rho": "ρ", "lambda": "λ", "pi": "π", "tau": "τ", "mu": "μ",
    "prime": "′", "blacksquare": "■", "qed": "■", "varepsilon": "ε", "epsilon": "ε", "varphi": "φ", "phi": "φ", "lt": "<", "gt": ">", "{": "{", "}": "}", "&": "&", "cup": "∪", "cap": "∩", "rightleftharpoons": "⇋",
}
# знаки, которые набираются прямо символом
MATHCHAR = "()[],.;:=+<>|/0123456789!?" + "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

def write_math_tex(pua, path):
    from symbols import MATHCLASS
    L = ["% создано make_font.py: знаки в формулах — её почерком, каждый раз случайный вариант",
         "\\ExplSyntaxOff\\makeatletter"]
    def body(ch):
        cl = MATHCLASS.get(ch, 0)
        alts = " \\or ".join(f'\\Umathchar{cl}\\hm@fam"{c:X} ' for c in pua[ch])
        return f"\\ifcase\\uniformdeviate{len(pua[ch])} {alts}\\fi"
    names = {}
    for i, ch in enumerate(sorted(pua)):
        nm = "hm@" + "abcdefghijklmnopqrstuvwxyz"[i // 26] + "abcdefghijklmnopqrstuvwxyz"[i % 26]
        names[ch] = nm
        L.append(f"\\def\\{nm}{{{body(ch)}}}% {ch}")
    L.append("\\newcommand\\handmathsetup{%")
    # семейство, в котором стоит её шрифт: его уже назначил unicode-math латинским буквам (биты 24..31)
    L.append('  \\chardef\\hm@fam=\\numexpr(\\Umathcodenum`A-"800000)/"1000000\\relax')
    for cmd, ch in MATHCMD.items():
        if ch not in names: continue
        if cmd in "{}&": L.append(f"  \\def\\{cmd}{{\\ifmmode\\{names[ch]}\\else\\char`\\{cmd}\\fi}}%")
        else: L.append(f"  \\def\\{cmd}{{\\{names[ch]}}}%")
    if "ℕ" in names and "ℝ" in names:
        L.append(f"  \\def\\mathbb##1{{\\ifx N##1\\{names['ℕ']}\\else\\ifx R##1\\{names['ℝ']}\\else##1\\fi\\fi}}%")
    if "′" in names:   # штрих: ' в формулах = её штрих в верхнем индексе
        L.append(f"  \\def\\hm@pr{{{{}}^{{\\{names['′']}}}}}\\begingroup\\lccode`\\~=`\\'\\lowercase{{\\endgroup\\def~}}{{\\hm@pr}}\\mathcode`\\'=\"8000 %")
    L.append("  \\def\\dots{\\ifmmode\\hm@dots\\else\\textellipsis\\fi}%")
    for ch in MATHCHAR:
        if ch not in names: continue
        L.append(f"  \\begingroup\\lccode`\\~=`\\{ch}\\lowercase{{\\endgroup\\def~}}{{\\{names[ch]}}}\\mathcode`\\{ch}=\"8000 %")
    if "−" in names:
        L.append(f"  \\begingroup\\lccode`\\~=`\\-\\lowercase{{\\endgroup\\def~}}{{\\{names['−']}}}\\mathcode`\\-=\"8000 %")
    L.append("}")
    if "…" in names: L.append(f"\\def\\hm@dots{{\\{names['…']}}}")
    L.append("\\AddToHook{begindocument/end}{\\handmathsetup}")
    L.append("\\makeatother")
    open(path, "w").write("\n".join(L) + "\n")

if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "fonts")
    for seed, suf in enumerate("ABC"):
        cnt = main(f"{outdir}/MariaHand-{suf}.otf", seed, f"MariaHand {suf}")
    print(" ".join(f"{c}:{n}" for c, n in sorted(cnt.items())))
