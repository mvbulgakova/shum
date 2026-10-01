# Математические и прочие знаки, нарисованные её же штрихами:
# прямые — из её тире «–»/«-», дуги — из её «с», «о», «(», точки — из её точек.
# Каждый знак в нескольких вариантах (разные штрихи + небольшой разброс углов и длин).
import math
import numpy as np
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.misc.transform import Transform

SLANT = 0.15        # её наклон вправо
NVAR = 6            # вариантов каждого знака

# класс в формулах: 0 ord, 1 op, 2 bin, 3 rel, 4 open, 5 close, 6 punct
MATHCLASS = {
    "∨": 2, "∧": 2, "&": 2, "+": 2, "−": 2, "×": 2, "∖": 2, "∪": 2, "∩": 2, "·": 2, "⋅": 2, "∘": 2,
    "¬": 0, "∅": 0, "∀": 0, "∃": 0, "⊤": 0, "⊥": 0, "Γ": 0, "Δ": 0, "′": 0, "|": 0, "/": 0, "…": 0, "⋯": 0,
    "?": 0, "!": 0, "*": 2, "0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0,
    "⊃": 3, "⊂": 3, "⊇": 3, "⊆": 3, "∈": 3, "∉": 3, "⊢": 3, "⊨": 3, "→": 3, "←": 3, "↔": 3, "⇒": 3,
    "⇐": 3, "⇔": 3, "=": 3, "≡": 3, "≠": 3, "<": 3, ">": 3, "≤": 3, "≥": 3, "⇋": 3, ":": 3,
    **{c: 0 for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"},
    "(": 4, "[": 4, "{": 4, ")": 5, "]": 5, "}": 5, ",": 6, ";": 6, ".": 0,
    "⊬": 3, "⊭": 3, "∼": 3, "⇌": 3, "↦": 3, "⟷": 3, "⟺": 3, "⟨": 4, "⟩": 5, "⋮": 0, "∗": 2, "•": 2,
    "α": 0, "β": 0, "θ": 0, "ϑ": 0, "ν": 0, "σ": 0, "ρ": 0, "λ": 0, "π": 0, "τ": 0, "μ": 0, "ε": 0, "φ": 0,
    "ℕ": 0, "ℝ": 0, "′": 0, "■": 0, "#": 0, "%": 0, "≤": 3, "≥": 3,
}


def bounds(rp):
    bp = BoundsPen(None); rp.replay(bp)
    return bp.bounds or (0, 0, 1, 1)


def put(rp, out, t):
    rp.replay(TransformPen(out, tuple(t)))


class Kit:
    def __init__(self, shapes, variants, gname, XH, seed=0):
        self.S, self.V, self.g, self.m = shapes, variants, gname, XH
        self.rs = np.random.RandomState(1234 + seed)

    def pen(self, ch, k):
        ids = self.clean(ch)
        return self.S[self.g(ch, ids[k % len(ids)])][0]

    def clean(self, ch):
        """номера вариантов без хвостов соседних букв: у дуг (с, о) берём самые «круглые»"""
        if not hasattr(self, "_cl"): self._cl = {}
        if ch not in self._cl:
            n = len(self.V[ch]); ks = list(range(n))
            if ch in "со":
                def score(k):
                    rp = self.S[self.g(ch, k)][0]
                    pts = np.array([pt for op, args in rp.value for pt in args], float)
                    x0, y0 = pts.min(0); x1, y1 = pts.max(0); w, h = x1 - x0, max(1, y1 - y0)
                    left = pts[pts[:, 0] < x0 + 0.15 * w]           # самая левая часть дуги
                    mid = abs((left[:, 1].mean() - y0) / h - 0.5)   # у чистой «с» она посередине высоты
                    asp = abs(w / h - (0.8 if ch == "с" else 0.95))
                    low = max(0, (y0 + 0.08 * h) * -1) / h          # хвост ниже строки
                    return mid + 0.5 * asp + low
                ks = sorted(ks, key=score)[:max(3, n // 6)]
            self._cl[ch] = ks
        return self._cl[ch]

    def stroke(self, out, k, p0, p1, src=None, jit=True):
        """прямой штрих её тире от p0 до p1 (координаты в долях x-высоты)"""
        m = self.m
        x0, y0 = p0[0] * m, p0[1] * m; x1, y1 = p1[0] * m, p1[1] * m
        if jit:
            a = self.rs.normal(0, 0.025) * m
            x0 += self.rs.normal(0, 0.02) * m; y0 += self.rs.normal(0, 0.02) * m
            x1 += self.rs.normal(0, 0.02) * m + a * 0; y1 += self.rs.normal(0, 0.02) * m
        L = math.hypot(x1 - x0, y1 - y0)
        if src is None: src = "–" if L > 0.55 * m and "–" in self.V else "-"
        rp = self.pen(src, k * 3 + int(L) % 5)
        bx0, by0, bx1, by1 = bounds(rp)
        yc = (by0 + by1) / 2; Ld = max(1, bx1 - bx0)
        sy = min(1.0, max(0.55, 0.9 * L / Ld)) if L < 0.4 * m else 1.0   # короткий штрих — тоньше изгиб
        th = math.atan2(y1 - y0, x1 - x0)
        t = Transform().translate(x0, y0).rotate(th).scale(L / Ld, sy).translate(-bx0, -yc)
        put(rp, out, t)

    def arc(self, out, k, c, rx, ry, a0, a1, src="–"):
        """её штрих, изогнутый по дуге эллипса: центр c, радиусы rx, ry, углы a0→a1 в градусах"""
        m = self.m
        rp = self.pen(src, k * 3 + 1)
        bx0, by0, bx1, by1 = bounds(rp); yc = (by0 + by1) / 2; Ld = max(1, bx1 - bx0)
        j = 1 + self.rs.normal(0, 0.04)
        a0 = math.radians(a0 + self.rs.normal(0, 4)); a1 = math.radians(a1 + self.rs.normal(0, 4))
        def W(p):
            t = (p[0] - bx0) / Ld; th = a0 + t * (a1 - a0); d = p[1] - yc
            return (c[0] * m + (rx * m * j + d) * math.cos(th), c[1] * m + (ry * m * j + d) * math.sin(th))
        cur = None
        for op, args in rp.value:
            if op == "moveTo": cur = args[0]; out.moveTo(W(cur))
            elif op == "lineTo":
                p0 = cur; p1 = args[0]
                for t in np.linspace(0, 1, 9)[1:]: out.lineTo(W((p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t)))
                cur = p1
            elif op == "curveTo":
                p0 = cur; a, b, e = args
                for t in np.linspace(0, 1, 10)[1:]:
                    x = (1-t)**3*p0[0]+3*(1-t)**2*t*a[0]+3*(1-t)*t*t*b[0]+t**3*e[0]
                    y = (1-t)**3*p0[1]+3*(1-t)**2*t*a[1]+3*(1-t)*t*t*b[1]+t**3*e[1]
                    out.lineTo(W((x, y)))
                cur = e
            elif op == "closePath": out.closePath()

    def fit(self, out, ch, k, box, mirror=False, rot=0):
        """её букву/знак ch вписать в прямоугольник box=(x0,y0,x1,y1) в долях x-высоты"""
        m = self.m
        rp = self.pen(ch, k)
        bx0, by0, bx1, by1 = bounds(rp)
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        w, h = bx1 - bx0, by1 - by0
        if rot % 180: w, h = h, w
        X0, Y0, X1, Y1 = [v * m for v in box]
        sx, sy = (X1 - X0) / max(1, w), (Y1 - Y0) / max(1, h)
        t = Transform().translate((X0 + X1) / 2, (Y0 + Y1) / 2).scale(-sx if mirror else sx, sy)
        t = t.rotate(math.radians(rot)).translate(-cx, -cy)
        put(rp, out, t)

    def dot(self, out, k, x, y, s=1.0):
        rp = self.pen(".", k)
        bx0, by0, bx1, by1 = bounds(rp)
        put(rp, out, Transform().translate(x * self.m, y * self.m).scale(s).translate(-(bx0 + bx1) / 2, -(by0 + by1) / 2))


def finish(rp, m, sb=0.1):
    """наклон как у неё + поля слева/справа; -> (pen, advance)"""
    sl = RecordingPen(); rp.replay(TransformPen(sl, (1, 0, SLANT, 1, 0, 0)))
    x0, _, x1, _ = bounds(sl)
    out = RecordingPen(); sl.replay(TransformPen(out, (1, 0, 0, 1, sb * m - x0, 0)))
    return out, (x1 - x0) + 2 * sb * m


def recipes(K):
    """знак -> функция(out, k), рисующая k-й вариант"""
    S = K.stroke
    def lines(*segs):
        return lambda o, k: [S(o, k + i, a, b) for i, (a, b) in enumerate(segs)]
    R = {}
    R["∨"] = lines(((0, 1.0), (0.42, 0)), ((0.42, 0), (0.85, 1.0)))
    R["∧"] = lines(((0, 0), (0.42, 1.0)), ((0.42, 1.0), (0.85, 0)))
    R["¬"] = lines(((0, 0.62), (0.75, 0.62)), ((0.75, 0.62), (0.73, 0.25)))
    R["⊢"] = lines(((0, 0), (0, 1.3)), ((0, 0.62), (0.75, 0.62)))
    R["⊨"] = lines(((0, 0), (0, 1.3)), ((0, 0.42), (0.75, 0.42)), ((0, 0.85), (0.75, 0.85)))
    R["→"] = lines(((0, 0.5), (1.1, 0.5)), ((1.1, 0.5), (0.85, 0.75)), ((1.1, 0.5), (0.85, 0.25)))
    R["←"] = lines(((0, 0.5), (1.1, 0.5)), ((0, 0.5), (0.25, 0.75)), ((0, 0.5), (0.25, 0.25)))
    R["↔"] = lines(((0, 0.5), (1.3, 0.5)), ((1.3, 0.5), (1.05, 0.75)), ((1.3, 0.5), (1.05, 0.25)),
                   ((0, 0.5), (0.25, 0.75)), ((0, 0.5), (0.25, 0.25)))
    R["⇒"] = lines(((0, 0.33), (1.0, 0.33)), ((0, 0.67), (1.0, 0.67)), ((1.2, 0.5), (0.9, 0.9)), ((1.2, 0.5), (0.9, 0.1)))
    R["⇐"] = lines(((0.2, 0.33), (1.2, 0.33)), ((0.2, 0.67), (1.2, 0.67)), ((0, 0.5), (0.3, 0.9)), ((0, 0.5), (0.3, 0.1)))
    R["⇔"] = lines(((0.2, 0.33), (1.2, 0.33)), ((0.2, 0.67), (1.2, 0.67)), ((1.4, 0.5), (1.1, 0.9)), ((1.4, 0.5), (1.1, 0.1)),
                   ((0, 0.5), (0.3, 0.9)), ((0, 0.5), (0.3, 0.1)))
    R["="] = lines(((0, 0.3), (0.8, 0.3)), ((0, 0.72), (0.8, 0.72)))
    R["≡"] = lines(((0, 0.12), (0.8, 0.12)), ((0, 0.5), (0.8, 0.5)), ((0, 0.88), (0.8, 0.88)))
    R["≠"] = lines(((0, 0.3), (0.8, 0.3)), ((0, 0.72), (0.8, 0.72)), ((0.15, -0.1), (0.65, 1.1)))
    R["+"] = lines(((0, 0.5), (0.8, 0.5)), ((0.4, 0.1), (0.4, 0.9)))
    R["−"] = lines(((0, 0.5), (0.8, 0.5)))
    R["×"] = lines(((0.05, 0.15), (0.65, 0.85)), ((0.05, 0.85), (0.65, 0.15)))
    R["<"] = lines(((0.7, 0.95), (0, 0.5)), ((0, 0.5), (0.7, 0.05)))
    R[">"] = lines(((0, 0.95), (0.7, 0.5)), ((0.7, 0.5), (0, 0.05)))
    R["≤"] = lines(((0.7, 1.05), (0, 0.65)), ((0, 0.65), (0.7, 0.25)), ((0, -0.05), (0.7, -0.05)))
    R["≥"] = lines(((0, 1.05), (0.7, 0.65)), ((0.7, 0.65), (0, 0.25)), ((0, -0.05), (0.7, -0.05)))
    R["|"] = lines(((0, -0.3), (0, 1.4)))
    R["/"] = lines(((0, -0.3), (0.5, 1.4)))
    R["∖"] = lines(((0, 1.2), (0.5, -0.1)))
    R["\\"] = R["∖"]
    R["["] = lines(((0, -0.3), (0, 1.4)), ((0, 1.4), (0.3, 1.4)), ((0, -0.3), (0.3, -0.3)))
    R["]"] = lines(((0.3, -0.3), (0.3, 1.4)), ((0, 1.4), (0.3, 1.4)), ((0, -0.3), (0.3, -0.3)))
    R["∀"] = lines(((0, 1.3), (0.42, 0)), ((0.42, 0), (0.85, 1.3)), ((0.17, 0.62), (0.68, 0.62)))
    R["∃"] = lines(((0.65, 0), (0.65, 1.3)), ((0, 1.3), (0.65, 1.3)), ((0.05, 0.65), (0.65, 0.65)), ((0, 0), (0.65, 0)))
    R["⊤"] = lines(((0, 1.3), (0.9, 1.3)), ((0.45, 1.3), (0.45, 0)))
    R["⊥"] = lines(((0, 0), (0.9, 0)), ((0.45, 0), (0.45, 1.3)))
    R["Γ"] = lines(((0, 0), (0, 1.35)), ((0, 1.35), (0.7, 1.35)))
    R["Δ"] = lines(((0, 0), (0.45, 1.35)), ((0.45, 1.35), (0.9, 0)), ((0.9, 0), (0, 0)))
    R["′"] = lines(((0.0, 0.95), (0.18, 1.45)))

    A = K.arc
    def arcs(*specs, extra=()):
        def f(o, k):
            for i, sp in enumerate(specs): A(o, k + i, *sp)
            for i, (a, b) in enumerate(extra): S(o, k + i + 5, a, b)
        return f
    # дуги — её штрих «–», изогнутый по эллипсу (у её «с» почти всегда есть хвост от соседней буквы)
    R["⊂"] = arcs(((0.45, 0.5), 0.42, 0.45, 80, 280))
    R["⊃"] = arcs(((0.3, 0.5), 0.42, 0.45, 100, -100))
    R["⊆"] = arcs(((0.45, 0.72), 0.42, 0.42, 80, 280), extra=(((0.05, -0.05), (0.8, -0.05)),))
    R["⊇"] = arcs(((0.3, 0.72), 0.42, 0.42, 100, -100), extra=(((0, -0.05), (0.75, -0.05)),))
    R["∈"] = arcs(((0.42, 0.5), 0.4, 0.45, 80, 280), extra=(((0.04, 0.5), (0.7, 0.5)),))
    R["∉"] = arcs(((0.42, 0.5), 0.4, 0.45, 80, 280), extra=(((0.04, 0.5), (0.7, 0.5)), ((0.15, -0.15), (0.6, 1.15))))
    R["∪"] = arcs(((0.42, 0.55), 0.4, 0.5, 190, 350))
    R["∩"] = arcs(((0.42, 0.4), 0.4, 0.5, 170, 10))
    R["∅"] = arcs(((0.42, 0.5), 0.36, 0.52, 100, 450), extra=(((-0.05, -0.2), (0.9, 1.2)),))
    R["∘"] = arcs(((0.25, 0.5), 0.18, 0.2, 90, 440), )

    def braces(left):
        # фигурная скобка: четыре дуги (сверху вниз), носик посередине
        def f(o, k):
            x = 0.3; rx, ry = 0.15, 0.42
            segs = [((x + rx, 0.97), 90, 180), ((x - rx, 0.97), 0, -90), ((x - rx, 0.13), 90, 0), ((x + rx, 0.13), 180, 270)]
            for i, ((cx, cy), a0, a1) in enumerate(segs):
                if not left: cx, a0, a1 = 2 * x - cx, 180 - a0, 180 - a1
                A(o, k + i, (cx, cy), rx, ry, a0, a1)
        return f
    R["{"] = braces(True); R["}"] = braces(False)

    F_ = K.fit
    def comb(*parts):
        """parts: ("fit", ch, box) | ("line", p0, p1) | ("arc", c, rx, ry, a0, a1) | ("dot", x, y, s)"""
        def f(o, k):
            for i, pt in enumerate(parts):
                if pt[0] == "fit": F_(o, pt[1], k + i, pt[2])
                elif pt[0] == "line": S(o, k + i, pt[1], pt[2])
                elif pt[0] == "arc": A(o, k + i, *pt[1:])
                elif pt[0] == "dot": K.dot(o, k + i, pt[1], pt[2], pt[3])
        return f
    L_ = lambda a, b: ("line", a, b)
    # латинские буквы, которых нет в её записях
    R["I"] = lines(((0.1, 0), (0.1, 1.6)))
    R["L"] = lines(((0.1, 0), (0.1, 1.6)), ((0.1, 0), (0.8, 0)))
    R["J"] = comb(L_((0.6, 1.6), (0.6, 0.35)), ("arc", (0.35, 0.35), 0.25, 0.35, 0, -170))
    R["V"] = lines(((0, 1.6), (0.5, 0)), ((0.5, 0), (1.0, 1.6)))
    R["Y"] = lines(((0, 1.6), (0.45, 0.8)), ((0.45, 0.8), (0.9, 1.6)), ((0.45, 0.8), (0.45, 0)))
    R["G"] = comb(("fit", "С", (0, 0, 1.15, 1.75)), L_((0.65, 0.7), (1.1, 0.7)), L_((1.05, 0.7), (1.0, 0.1)))
    R["Q"] = comb(("fit", "О", (0, 0, 1.15, 1.75)), L_((0.65, 0.35), (1.2, -0.15)))
    R["v"] = comb(("fit", "∨", (0, 0, 0.8, 1.0)))
    R["b"] = comb(("fit", "l", (0, 0, 0.45, 1.7)), ("fit", "о", (0.25, 0, 0.85, 1.0)))
    R["d"] = comb(("fit", "о", (0, 0, 0.62, 1.0)), ("fit", "l", (0.42, 0, 0.88, 1.7)))
    R["j"] = comb(L_((0.4, 1.0), (0.2, -0.6)), ("dot", 0.47, 1.45, 1.0))
    # греческие
    R["σ"] = comb(("fit", "о", (0, 0, 0.75, 1.0)), L_((0.45, 1.0), (1.05, 1.02)))
    R["θ"] = comb(("fit", "0", (0, 0, 0.75, 1.6)), L_((0.08, 0.8), (0.68, 0.8)))
    R["ϑ"] = R["θ"]
    R["ν"] = comb(("fit", "∨", (0, 0, 0.75, 1.0)))
    R["λ"] = lines(((0.1, 1.6), (0.75, 0)), ((0.42, 0.85), (0, 0)))
    R["π"] = lines(((0, 1.0), (0.95, 1.0)), ((0.25, 1.0), (0.2, 0)), ((0.7, 1.0), (0.75, 0)))
    R["τ"] = lines(((0, 1.0), (0.85, 1.0)), ((0.42, 1.0), (0.4, 0)))
    # прочие знаки
    R["•"] = comb(("dot", 0.2, 0.5, 2.2))
    R["∗"] = lines(((0.3, 0.55), (0.3, 1.25)), ((0.0, 0.72), (0.6, 1.08)), ((0.0, 1.08), (0.6, 0.72)))
    R["*"] = R["∗"]
    R["#"] = lines(((0.2, 0), (0.4, 1.3)), ((0.55, 0), (0.75, 1.3)), ((0, 0.4), (0.9, 0.4)), ((0.05, 0.9), (0.95, 0.9)))
    R["%"] = comb(("fit", "о", (0, 0.9, 0.35, 1.4)), L_((0.05, 0), (0.85, 1.4)), ("fit", "о", (0.55, 0, 0.9, 0.5)))
    R["∼"] = comb(("arc", (0.2, 0.5), 0.2, 0.14, 180, 0), ("arc", (0.6, 0.5), 0.2, 0.14, 180, 360))
    R["~"] = R["∼"]
    R["⇌"] = lines(((0, 0.68), (1.2, 0.68)), ((1.2, 0.68), (0.95, 0.95)), ((0, 0.32), (1.2, 0.32)), ((0, 0.32), (0.25, 0.05)))
    R["⇋"] = lines(((0, 0.68), (1.2, 0.68)), ((0, 0.68), (0.25, 0.95)), ((0, 0.32), (1.2, 0.32)), ((1.2, 0.32), (0.95, 0.05)))
    R["⊬"] = comb(("fit", "⊢", (0, 0, 0.85, 1.3)), L_((0.15, -0.1), (0.7, 1.35)))
    R["⊭"] = comb(("fit", "⊨", (0, 0, 0.85, 1.3)), L_((0.15, -0.1), (0.7, 1.35)))
    R["⟨"] = lines(((0.4, 1.45), (0, 0.55)), ((0, 0.55), (0.4, -0.35)))
    R["⟩"] = lines(((0, 1.45), (0.4, 0.55)), ((0.4, 0.55), (0, -0.35)))
    R["⋮"] = comb(("dot", 0.1, 0.05, 1.0), ("dot", 0.1, 0.5, 1.0), ("dot", 0.1, 0.95, 1.0))
    R["ℕ"] = comb(("fit", "N", (0.1, 0, 1.1, 1.65)), L_((0.25, 0.05), (0.32, 1.6)))
    R["ℝ"] = comb(("fit", "R", (0.1, 0, 1.1, 1.65)), L_((0.25, 0.05), (0.3, 1.6)))
    R["⟷"] = lines(((0, 0.5), (1.8, 0.5)), ((1.8, 0.5), (1.55, 0.75)), ((1.8, 0.5), (1.55, 0.25)), ((0, 0.5), (0.25, 0.75)), ((0, 0.5), (0.25, 0.25)))
    R["⟺"] = lines(((0.2, 0.33), (1.8, 0.33)), ((0.2, 0.67), (1.8, 0.67)), ((2.0, 0.5), (1.7, 0.9)), ((2.0, 0.5), (1.7, 0.1)), ((0, 0.5), (0.3, 0.9)), ((0, 0.5), (0.3, 0.1)))
    R["↦"] = lines(((0, 0.25), (0, 0.75)), ((0, 0.5), (1.1, 0.5)), ((1.1, 0.5), (0.85, 0.75)), ((1.1, 0.5), (0.85, 0.25)))
    R["√"] = lines(((0, 0.55), (0.15, 0.65)), ((0.15, 0.65), (0.35, -0.1)), ((0.35, -0.1), (0.7, 1.5)), ((0.7, 1.5), (1.4, 1.5)))
    R["§"] = comb(("fit", "s", (0, 0.65, 0.55, 1.55)), ("fit", "s", (0, -0.25, 0.55, 0.65)))
    R["_"] = lines(((0, -0.12), (0.8, -0.12)))
    R["∶"] = lambda o, k: [K.dot(o, k, 0.05, 0.15), K.dot(o, k + 1, 0.1, 0.75)]

    def dots(y, n=3, gap=0.32):
        return lambda o, k: [K.dot(o, k + i, i * gap, y) for i in range(n)]
    R["…"] = dots(0.02); R["⋯"] = dots(0.45)
    R["·"] = dots(0.45, 1); R["⋅"] = R["·"]
    R[":"] = lambda o, k: [K.dot(o, k, 0.05, 0.05), K.dot(o, k + 1, 0.12, 0.7)]
    R[";"] = lambda o, k: [K.fit(o, ",", k, (0, -0.35, 0.18, 0.15)), K.dot(o, k + 1, 0.15, 0.7)]
    return R


def build(shapes, variants, base, meta, gname, XH, seed=0):
    """дорисовывает знаки; у знаков, что уже есть из лекций, добавляет нарисованные варианты"""
    need = {"–", "-", ".", "с", "о", "(", ")", ","}
    if not need <= set(variants): return []
    # настоящие скобки из лекций — к одной высоте (в лекциях встречаются и мелкие, и огромные)
    for ch in "()":
        for k in range(len(variants.get(ch, []))):
            n = gname(ch, k); rp, adv = shapes[n]
            x0, y0, x1, y1 = bounds(rp)
            sc = float(np.clip(1.7 * XH / max(1, y1 - y0), 0.4, 2.6))
            out = RecordingPen(); rp.replay(TransformPen(out, (sc, 0, 0, sc, 0, -0.3 * XH - y0 * sc)))
            shapes[n] = (out, adv * sc)
    # знаки из лекций — к одной высоте и положению (в формулах они пляшут: в индексах, в таблицах)
    POS = {  # знак: (высота, макс. ширина в x-высотах, центр по вертикали или None = стоит на строке)
        "=": (0.5, 1.0, 0.55), "≡": (0.75, 1.0, 0.6), "⇔": (0.55, 1.7, 0.6), "⇒": (0.55, 1.3, 0.6),
        "→": (0.5, 1.3, 0.6), "¬": (0.95, 1.15, 1.1), "∨": (1.35, 1.1, None), "&": (1.55, 1.2, None),
        "⊃": (1.1, 0.9, None), "-": (0.12, 0.6, 0.55), "–": (0.12, 1.3, 0.55),
        ",": (0.55, 0.3, -0.05), "■": (0.75, 0.9, 0.42), "•": (0.32, 0.35, 0.5), ".": (0.14, 0.2, 0.07),
    }
    for ch, (th, mw, cy) in POS.items():
        for k in range(len(variants.get(ch, []))):
            n = gname(ch, k); rp, adv = shapes[n]
            x0, y0, x1, y1 = bounds(rp)
            sc = float(np.clip(th * XH / max(1, y1 - y0), 0.4, 2.2))
            if ch in "-–.": sc = min(sc, mw * XH / max(1, x1 - x0)) if (y1 - y0) * sc > th * XH * 1.6 else min(1.0, mw * XH / max(1, x1 - x0))
            sc = min(sc, mw * XH / max(1, x1 - x0))
            ty = (cy * XH - sc * (y0 + y1) / 2) if cy is not None else -sc * y0
            out = RecordingPen(); rp.replay(TransformPen(out, (sc, 0, 0, sc, -sc * x0 + 0.08 * XH, ty)))
            shapes[n] = (out, sc * (x1 - x0) + 0.16 * XH)
    # заглавные (кириллица и латиница): стоят на строке, высота около двух строчных
    for ch in list(variants):
        if not ((ch.isalpha() and ch.isupper()) or ch.isdigit()) or ch in "ДЦЩУФЗ": continue
        for k in range(len(variants[ch])):
            n = gname(ch, k); rp, adv = shapes[n]
            x0, y0, x1, y1 = bounds(rp); h = max(1, y1 - y0)
            sc = float(np.clip((1.6 if ch.isdigit() else 1.9) * XH / h, 0.6, 1.5))
            out = RecordingPen(); rp.replay(TransformPen(out, (sc, 0, 0, sc, 0, -sc * y0)))
            shapes[n] = (out, adv * sc)
    K = Kit(shapes, variants, gname, XH, seed)
    R = recipes(K)
    made = []
    for ch, f in R.items():
        have = len(variants.get(ch, []))
        if have >= NVAR: continue
        start = have
        if ch not in variants: variants[ch] = []; base[ch] = 0
        try:
            out = RecordingPen(); f(out, 0)
        except (KeyError, IndexError, ZeroDivisionError):
            continue
        for k in range(NVAR - have):
            out = RecordingPen(); f(out, k * 2 + seed)
            pen, adv = finish(out, XH)
            n = gname(ch, start + k)
            shapes[n] = (pen, adv); meta[n] = ("^", "$")
            variants[ch].append(start + k)
        made.append(ch)
    return made
