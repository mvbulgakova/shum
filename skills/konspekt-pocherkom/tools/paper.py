# Кладёт рукописные страницы на «сфотографированный» лист в клетку (как у неё в PDF со сканами):
# python3 paper.py вход.pdf выход.pdf   (вход собран БЕЗ клетки)
import sys, subprocess, tempfile, glob, os, numpy as np, cv2, img2pdf
DPI = 150; CELL = 5 / 25.4 * DPI          # клетка 5 мм
def sheet(h, w, rs):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    # бумага: неровный свет, лёгкий шум, чуть сероватая
    light = cv2.resize(rs.uniform(-9, 9, (4, 3)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    base = 216 + light + 4 * (1 - y / h) + rs.normal(0, 1.6, (h, w)).astype(np.float32)
    # клетка: чуть повёрнута и неровно напечатана
    a = np.deg2rad(rs.uniform(-0.4, 0.4)); ox, oy = rs.uniform(0, CELL, 2)
    u = x * np.cos(a) + y * np.sin(a) + ox; v = -x * np.sin(a) + y * np.cos(a) + oy
    du = np.abs(((u + CELL / 2) % CELL) - CELL / 2); dv = np.abs(((v + CELL / 2) % CELL) - CELL / 2)
    line = np.maximum(np.exp(-(du / 0.9) ** 2), np.exp(-(dv / 0.9) ** 2))
    page = np.dstack([base - 30 * line, base - 27 * line, base - 22 * line])   # BGR: линии серо-голубые
    return page
def main(src, dst):
    td = tempfile.mkdtemp()
    subprocess.run(["pdftoppm", "-r", str(DPI), "-png", src, f"{td}/p"], check=True)
    rs = np.random.RandomState(3); outs = []
    for f in sorted(glob.glob(f"{td}/p-*.png")):
        ink = cv2.imread(f).astype(np.float32)
        h, w = ink.shape[:2]
        ink = cv2.GaussianBlur(ink, (0, 0), 0.6)                     # чернила чуть впитались
        pg = sheet(h, w, rs) * (ink / 255.0)                          # умножение: чернила поверх клетки
        pg = np.clip(pg, 0, 255).astype(np.uint8)
        fn = f[:-4] + ".jpg"; cv2.imwrite(fn, pg, [cv2.IMWRITE_JPEG_QUALITY, 82]); outs.append(fn)
    open(dst, "wb").write(img2pdf.convert(outs, layout_fun=img2pdf.get_fixed_dpi_layout_fun((DPI, DPI))))
if __name__ == "__main__": main(sys.argv[1], sys.argv[2])
