# Выпрямление страницы: поворот + поперечный «сдвиг» (shear), чтобы строки стали горизонтальными
import numpy as np, cv2, sys, glob, os
def score(m, ang, sh):
    H, W = m.shape
    M = cv2.getRotationMatrix2D((W / 2, H / 2), ang, 1.0)
    r = cv2.warpAffine(m, M, (W, H))
    if sh:
        S = np.float32([[1, 0, 0], [sh, 1, -sh * W / 2]]); r = cv2.warpAffine(r, S, (W, H))
    p = r.sum(1).astype(float)
    return (np.diff(p) ** 2).sum()
for p in sorted(glob.glob(sys.argv[1] + "/*.npy")):
    a = np.load(p); m = (a > 80).astype(np.float32)
    small = cv2.resize(m, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    best = max(((score(small, ang, 0), ang) for ang in np.arange(-6, 6.01, 0.25)))
    ang = best[1]
    # плавный изгиб: по полосам слева/справа ищем свой угол, разницу компенсируем shear-ом по x
    H, W = a.shape
    M = cv2.getRotationMatrix2D((W / 2, H / 2), ang, 1.0)
    r = cv2.warpAffine(a, M, (W, H))
    np.save(sys.argv[2] + "/" + os.path.basename(p), r)
    cv2.imwrite(sys.argv[2] + "/" + os.path.basename(p)[:-4] + ".png", 255 - r)
    print(os.path.basename(p), "angle", ang)
