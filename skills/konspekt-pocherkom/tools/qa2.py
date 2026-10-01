import pickle, numpy as np, sys, json, cv2, os
from PIL import Image, ImageDraw, ImageFont
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
D = pickle.load(open("glyphs.pkl", "rb")); G = D["glyphs"]
def feat(g):
    w = g["img"]; bl, xh = g["bl"], g["xh"]
    y0 = int(bl - 2.2 * xh); y1 = int(bl + 1.2 * xh)
    sl = w.astype(np.float32) / 255
    sl = np.pad(sl, ((max(0, -y0), max(0, y1 - w.shape[0])), (0, 0)))[max(0, y0):max(0, y0) + y1 - y0]
    f = cv2.GaussianBlur(cv2.resize(sl, (16, 24), interpolation=cv2.INTER_AREA), (3, 3), 0.8).ravel()
    f /= (np.linalg.norm(f) + 1e-6)
    return np.r_[f, 0.6 * np.log(w.shape[1] / xh + 0.05)]
def order(ids):
    if len(ids) < 4: return ids
    Fm = np.array([feat(G[i]) for i in ids]); Dm = np.linalg.norm(Fm[:, None] - Fm[None], axis=2)
    k = max(2, len(ids) // 6); dens = np.sort(Dm, 1)[:, 1:k + 1].mean(1)
    return [ids[j] for j in np.argsort(dens)]
if __name__ == "__main__":
    chars = sys.argv[1]; XH = int(sys.argv[2]) if len(sys.argv) > 2 else 26
    ids = order([i for i, g in enumerate(G) if g["ch"] in chars])
    json.dump(ids, open("qa_ids.json", "w"))
    tiles = []
    for n, gi in enumerate(ids):
        g = G[gi]; s = XH / g["xh"]
        im = Image.fromarray(255 - g["img"]).resize((max(1, int(g["img"].shape[1] * s)), max(1, int(g["img"].shape[0] * s))))
        cv = Image.new("L", (max(im.width, 26) + 4, int(3.4 * XH) + 16), 255); yb = int(2.2 * XH)
        cv.paste(im, (2, yb - int(g["bl"] * s)))
        d = ImageDraw.Draw(cv); d.line([(0, yb), (cv.width, yb)], fill=210)
        d.rectangle([0, cv.height - 15, cv.width, cv.height], fill=235)
        d.text((2, cv.height - 15), str(n), fill=0, font=F)
        tiles.append(cv)
    W = 1900; x = y = rowh = 0; pos = []
    for t in tiles:
        if x + t.width > W and x: x = 0; y += rowh + 3; rowh = 0
        pos.append((x, y)); x += t.width + 3; rowh = max(rowh, t.height)
    sh = Image.new("L", (W, y + rowh), 150)
    for t, p in zip(tiles, pos): sh.paste(t, p)
    sh.save("qa.png"); print(len(tiles), sh.size)
