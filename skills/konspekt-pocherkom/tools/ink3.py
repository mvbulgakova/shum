import cv2, numpy as np, sys, glob, os
def darkness(img):
    f = img.astype(np.float32)
    bg = cv2.medianBlur(img, 41).astype(np.float32)
    bg = cv2.GaussianBlur(bg, (0, 0), 6)
    ratio = np.clip(f / (bg + 1), 0, 1.2)
    return 1 - (ratio[..., 2] * 0.5 + ratio[..., 1] * 0.5)
def grid_mask(d, thr):
    m = (d > thr).astype(np.uint8)
    h = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (45, 1)))
    v = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 45)))
    g = cv2.dilate(h | v, np.ones((3, 3), np.uint8))
    return g.astype(bool)
def ink_alpha(img, force_grid=None):
    d = darkness(img)
    g = grid_mask(d, 0.08)
    hl = cv2.morphologyEx((d > 0.08).astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (45, 1)))
    rows = (hl.mean(axis=1) > 0.4).sum()
    if (force_grid is False) or (force_grid is None and rows < 15): g[:] = False                                   # plain paper, no grid
    gd = np.percentile(d[g], 75) if g.any() else 0.12          # how dark grid lines are on this page
    lo = 0.24
    a = np.clip((d - lo) / 0.25, 0, 1)
    ag = np.clip((d - min(gd + 0.12, 0.5)) / 0.2, 0, 1)                # stricter on grid lines
    a = np.where(g, ag, a)
    raw = img.astype(np.int32)
    black = (raw.max(axis=2) < 80) & ((raw[..., 0] - (raw[..., 1] + raw[..., 2]) / 2) < 20)
    col = black[:, :250].mean(axis=0)
    idx = np.nonzero(col > 0.10)[0]
    if len(idx): a[:, :idx.max() + 6] = 0                       # spiral binding
    # drop specks
    m = (a > 0.3).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    W_ = a.shape[1]
    sq = st[:, cv2.CC_STAT_WIDTH], st[:, cv2.CC_STAT_HEIGHT]
    # точки сетки: маленькие круглые пятна
    dotty = (st[:, cv2.CC_STAT_AREA] < 70) & (np.maximum(*sq) < 13) & (np.abs(sq[0] - sq[1]) <= 4)
    ndots = dotty.sum()
    bad = st[:, cv2.CC_STAT_AREA] < 12
    if ndots > 300: bad |= dotty                     # лист в точку
    # кольца блокнота: крупные тёмные пятна у края
    raw = img.astype(np.int32); blue = (raw[..., 0] - (raw[..., 1] + raw[..., 2]) / 2)
    for i in range(1, n):
        x, y, w, h, ar = st[i]
        if (x < 0.14 * W_ or x + w > 0.9 * W_) and ar > 120 and h < 0.1 * a.shape[0]:
            if blue[lab == i].mean() < 22: bad[i] = True
    small = np.isin(lab, np.nonzero(bad)[0])
    a[small] = 0
    a[cv2.dilate(m, np.ones((3,3),np.uint8)) == 0] = 0
    # остатки клетки: длинные ровные тонкие линии
    mm = (a > 0.25).astype(np.uint8)
    hl = cv2.morphologyEx(mm, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (70, 1)))
    vl = cv2.morphologyEx(mm, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 70)))
    gl = cv2.dilate(hl | vl, np.ones((3, 3), np.uint8)).astype(bool)
    a[gl & (d < gd + 0.25)] = 0         # faint halo only near strokes
    return a, gd
if __name__ == "__main__":
    os.makedirs(sys.argv[2], exist_ok=True)
    for p in sorted(glob.glob(sys.argv[1] + "/*.jpg")):
        img = cv2.imread(p); a, gd = ink_alpha(img, force_grid=None)
        print(p, round(float(gd), 3))
        np.save(sys.argv[2] + "/" + os.path.basename(p).replace(".jpg", ".npy"), (a * 255).astype(np.uint8))
        cv2.imwrite(sys.argv[2] + "/" + os.path.basename(p).replace(".jpg", ".png"), (255 - a * 255).astype(np.uint8))
