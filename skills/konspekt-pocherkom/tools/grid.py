# python3 grid.py PAGE x0 y0 x1 y1 [zoom] -> grid.png: вырезка страницы с координатной сеткой (метки — координаты страницы)
import sys, numpy as np, os
from PIL import Image, ImageDraw, ImageFont
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
def load(page):
    for d in ("ink2", "ink_n"):
        p = f"{d}/{page}.npy"
        if os.path.exists(p): return np.load(p)
page = sys.argv[1]; x0, y0, x1, y1 = map(int, sys.argv[2:6]); Z = float(sys.argv[6]) if len(sys.argv) > 6 else 3
a = load(page); sub = a[y0:y1, x0:x1]
im = Image.fromarray(255 - sub).convert("RGB").resize((int(sub.shape[1] * Z), int(sub.shape[0] * Z)))
P = 30
cv = Image.new("RGB", (im.width + P, im.height + P), "white"); cv.paste(im, (P, P)); d = ImageDraw.Draw(cv)
step = 10
for x in range((x0 // step + 1) * step, x1, step):
    X = P + (x - x0) * Z; major = x % 50 == 0
    d.line([(X, P), (X, cv.height)], fill=(255, 150, 150) if major else (255, 225, 225))
    if major: d.text((X - 10, 2 + (x // 50 % 2) * 12), str(x), fill=(200, 0, 0), font=F)
for y in range((y0 // step + 1) * step, y1, step):
    Y = P + (y - y0) * Z; major = y % 50 == 0
    d.line([(P, Y), (cv.width, Y)], fill=(150, 150, 255) if major else (225, 225, 255))
    if major: d.text((0, Y - 6), str(y), fill=(0, 0, 200), font=F)
cv.save("grid.png"); print(cv.size)
