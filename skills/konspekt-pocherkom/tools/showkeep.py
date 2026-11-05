import pickle, json, sys, numpy as np, cv2
pkl, kp, chars = sys.argv[1], sys.argv[2], sys.argv[3]; per = int(sys.argv[4]) if len(sys.argv) > 4 else 40
D = pickle.load(open(pkl, "rb")); G = D["glyphs"]; K = json.load(open(kp)); rows = []
for ch in chars:
    ids = K.get(ch, [])[:per]; tiles = []
    for i in ids:
        g = G[i]; a = 255 - g["img"]; xh = max(int(g["lxh"]), 8); bl = int(g["bl"])
        H = int(3.4 * xh); top = bl - int(2.0 * xh)
        c = np.full((H, a.shape[1] + 6), 255, np.uint8)
        for y in range(H):
            sy = top + y
            if 0 <= sy < a.shape[0]: c[y, 3:3 + a.shape[1]] = a[sy]
        c[int(2.0 * xh), :] = np.minimum(c[int(2.0 * xh), :], 200)
        c = cv2.resize(c, None, fx=24 / xh, fy=24 / xh, interpolation=cv2.INTER_AREA)
        tiles.append(cv2.copyMakeBorder(c, 0, 0, 0, 3, cv2.BORDER_CONSTANT, value=180))
    if not tiles: continue
    h = max(t.shape[0] for t in tiles); tiles = [cv2.copyMakeBorder(t, 0, h - t.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=255) for t in tiles]
    rows.append(np.hstack(tiles))
W = max(r.shape[1] for r in rows)
cv2.imwrite("keep.png", np.vstack([cv2.copyMakeBorder(r, 0, 6, 0, W - r.shape[1], cv2.BORDER_CONSTANT, value=255) for r in rows]))
