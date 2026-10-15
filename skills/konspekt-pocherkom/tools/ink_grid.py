# Чернила с фото листа в клетку: тёмность относительно фона, клетка убирается как длинные прямые линии
import cv2, numpy as np, sys, glob, os
def ink_alpha(img):
    f = img.astype(np.float32)
    bg = cv2.GaussianBlur(cv2.medianBlur(img, 51).astype(np.float32), (0, 0), 8)
    ratio = np.clip(f / (bg + 1), 0, 1.2)
    d = 1 - (ratio[..., 2] * 0.6 + ratio[..., 1] * 0.4)
    blue = (f[..., 0] - f[..., 2]) / (f.max(axis=2) + 1); bgb = (bg[..., 0] - bg[..., 2]) / (bg.max(axis=2) + 1)
    score = d + 0.8 * np.clip(blue - bgb, 0, 1)
    m = (score > 0.2).astype(np.uint8)
    L = 41
    hl = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (L, 1)))
    vl = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, L)))
    G = cv2.dilate(hl | vl, np.ones((3, 3), np.uint8))
    ink = m & (1 - G)
    # где штрих пересекает линию клетки — сшиваем: пиксель линии оставляем, если чернила есть с обеих сторон
    up = cv2.dilate(ink, np.ones((7, 1), np.uint8)); lr = cv2.dilate(ink, np.ones((1, 7), np.uint8))
    ink = ink | (G & ((vl == 0) & (up > 0) | (hl == 0) & (lr > 0)).astype(np.uint8) & m)
    n, lab, st, _ = cv2.connectedComponentsWithStats(ink, 8)
    small = np.isin(lab, np.nonzero(st[:, cv2.CC_STAT_AREA] < 25)[0]); ink[small] = 0
    # кружки колец блокнота и тени: сплошные толстые пятна
    for i in range(1, n):
        x, y, w, h, ar = st[i]
        if ar > 250 and ar > 0.45 * w * h and min(w, h) > 14: ink[lab == i] = 0
    a = np.clip((score - 0.16) / 0.22, 0, 1) * ink
    return a
if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]; os.makedirs(dst, exist_ok=True)
    for p in sorted(glob.glob(src + "/*.jpg")):
        a = ink_alpha(cv2.imread(p)); b = os.path.basename(p)[:-4]
        np.save(f"{dst}/{b}.npy", (a * 255).astype(np.uint8)); cv2.imwrite(f"{dst}/{b}.png", (255 - a * 255).astype(np.uint8))
