# лист глифов из готового шрифта по классам: python3 review.py "абв" -> review.png
import sys, json
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from PIL import Image, ImageDraw, ImageFont
import numpy as np, cv2
FNT = sys.argv[2] if len(sys.argv) > 2 else "out/MariaHand.otf"
f = TTFont(FNT); gs = f.getGlyphSet(); order = f.getGlyphOrder()
L = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
LB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
SC = float(__import__("os").environ.get("SC", 0.11))
def render(name):
    from fontTools.pens.basePen import BasePen
    pts = []
    class P(BasePen):
        def __init__(s): super().__init__(gs); s.polys = []; s.cur = []
        def _moveTo(s, p): s.cur = [p]
        def _lineTo(s, p): s.cur.append(p)
        def _curveToOne(s, a, b, c):
            p0 = s.cur[-1]
            for t in np.linspace(0, 1, 8)[1:]:
                x = (1-t)**3*p0[0]+3*(1-t)**2*t*a[0]+3*(1-t)*t*t*b[0]+t**3*c[0]
                y = (1-t)**3*p0[1]+3*(1-t)**2*t*a[1]+3*(1-t)*t*t*b[1]+t**3*c[1]
                s.cur.append((x, y))
        def _closePath(s): s.polys.append(s.cur); s.cur = []
    p = P(); gs[name].draw(p)
    W = int(max(gs[name].width, 200) * SC) + 6; H = int(1500 * SC)
    im = np.zeros((H, W), np.uint8)
    polys = [np.array([[3 + x * SC, H - (y + 450) * SC] for x, y in pl], np.int32) for pl in p.polys if len(pl) > 2]
    if polys: cv2.fillPoly(im, polys, 255)   # even-odd-ish via fillPoly (holes ok for review)
    out = Image.fromarray(255 - im)
    d = ImageDraw.Draw(out); yb = H - int(450 * SC); d.line([(0, yb), (W, yb)], fill=200); d.line([(0, yb - int(380 * SC)), (W, yb - int(380 * SC))], fill=225)
    return out
chars = sys.argv[1]
rows = []
for ch in chars:
    base = f"uni{ord(ch):04X}"
    names = [n for n in order if n.startswith(base + ".v") and ".c" not in n]
    names.sort(key=lambda n: int(n.split(".v")[1]))
    tiles = [Image.new("L", (36, int(1500 * SC) + 15), 200)]
    ImageDraw.Draw(tiles[0]).text((6, 20), ch, font=LB, fill=0)
    for n in names:
        t = render(n); c = Image.new("L", (t.width, t.height + 15), 235); c.paste(t, (0, 0))
        ImageDraw.Draw(c).text((2, t.height), n.split(".v")[1], font=L, fill=0); tiles.append(c)
    Wd = 1900; x = y = rh = 0; pos = []
    for t in tiles:
        if x + t.width > Wd and x: x = 0; y += rh + 2; rh = 0
        pos.append((x, y)); x += t.width + 2; rh = max(rh, t.height)
    b = Image.new("L", (Wd, y + rh + 6), 110)
    for t, p_ in zip(tiles, pos): b.paste(t, p_)
    rows.append(b)
sh = Image.new("L", (1900, sum(r.height for r in rows))); y = 0
for r in rows: sh.paste(r, (0, y)); y += r.height
sh.save("review.png"); print(sh.size)
