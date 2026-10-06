# Чернила с фото на белой бумаге: тёмность относительно фона + синева (синяя ручка)
import cv2, numpy as np, sys, glob, os
def ink_alpha(img):
    f = img.astype(np.float32)
    bg = cv2.medianBlur(img, 51).astype(np.float32); bg = cv2.GaussianBlur(bg, (0, 0), 8)
    ratio = np.clip(f / (bg + 1), 0, 1.2)
    d = 1 - (ratio[..., 2] * 0.6 + ratio[..., 1] * 0.4)          # синие чернила: падает R и G
    blue = (f[..., 0] - f[..., 2]) / (f.max(axis=2) + 1)           # B-R
    bgb = (bg[..., 0] - bg[..., 2]) / (bg.max(axis=2) + 1)
    db = np.clip(blue - bgb, 0, 1)
    score = d + 0.8 * db
    a = np.clip((score - 0.16) / 0.22, 0, 1)
    m = (a > 0.35).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    small = np.isin(lab, np.nonzero(st[:, cv2.CC_STAT_AREA] < 14)[0]); a[small] = 0
    a[cv2.dilate(m, np.ones((3, 3), np.uint8)) == 0] = 0
    return a
if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]; os.makedirs(dst, exist_ok=True)
    for p in sorted(glob.glob(src + "/*.jpg")):
        a = ink_alpha(cv2.imread(p)); b = os.path.basename(p)[:-4]
        np.save(f"{dst}/{b}.npy", (a * 255).astype(np.uint8)); cv2.imwrite(f"{dst}/{b}.png", (255 - a * 255).astype(np.uint8))
