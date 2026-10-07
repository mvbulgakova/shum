# Перевырезать буквы со страницы целиком: вернуть хвосты/верхушки, обрезанные границей строки
import pickle, gzip, json, numpy as np, cv2, os, sys
S = os.path.dirname(os.path.abspath(__file__))
D = '/home/user/shum/skills/konspekt-pocherkom/data/'
A = pickle.load(gzip.open(D + 'glyphs.pkl.gz', 'rb')); G = A['glyphs']
K = json.load(open(D + 'keep.json'))
RUNS = [  # (префиксы src, папка с cand.json, папка чернил, layout)
    (('l2', 'l3', 'l4'), S, S + '/ink2', S + '/layout.json'),
    (('n1', 'n2', 'n3'), S + '/newrun', S + '/ink_n', S + '/new/layout.json'),
    (('z1', 'z2'), S + '/runz', S + '/ink_zd', S + '/newz/layout.json'),
    (('z3b', 'z4b'), S + '/run34', S + '/ink_z34', S + '/newz34/layout.json')]
cache = {}
def run_of(src):
    if src.endswith('_pick'): return None
    for i, (pf, *_ ) in enumerate(RUNS):
        if src.startswith(pf) and not (src.startswith('z3_') or src.startswith('z4_')): return i
    return None
def get(i):
    if i in cache: return cache[i]
    pf, d, ink, lay = RUNS[i]
    C = json.load(open(d + '/cand.json')); L = json.load(open(lay))
    LY = {l['id']: l for pg in L.values() for l in pg}
    WD = {}
    for w in A['words']:
        if w['lid'].replace('z3b_', 'z3_').replace('z4b_', 'z4_').startswith(tuple(p.replace('b', '') for p in pf)) or w['lid'].startswith(pf):
            WD.setdefault(w['lid'], {})[w['i']] = w
    cache[i] = (C, LY, ink); return cache[i]
pages = {}
def page(ink, pg):
    k = ink + pg
    if k not in pages: pages[k] = np.load(f'{ink}/{pg}.npy')
    return pages[k]
kept = {i for v in K.values() for i in v}
fixed = skipped = 0
for gi in sorted(kept):
    g = G[gi]
    if g.get('recropped'): continue
    ri = run_of(g['src'])
    if ri is None: skipped += 1; continue
    C, LY, ink = get(ri)
    lid = g['src'].replace('z3b_', 'z3_').replace('z4b_', 'z4_')
    o = C[g['word']]
    if o['lid'] != lid: skipped += 1; continue
    L = LY[lid]; pgname = lid.rsplit('_', 1)[0]
    P = page(ink, pgname)
    img = g['img']; h, w = img.shape
    # где стоит буква на странице: строка L.y0 + wy0, по x ищем совпадение внутри слова
    Y0 = L['y0'] + g['wy0']
    best = None
    for X0 in range(o['x0'] - 3, o['x0'] + o['w'] + 3 - w + 1):
        if X0 < 0 or X0 + w > P.shape[1]: continue
        win = P[Y0:Y0 + h, X0:X0 + w]
        if win.shape != img.shape: continue
        sc = np.abs(win.astype(int) * (img > 0) - img.astype(int)).sum()
        if best is None or sc < best[0]: best = (sc, X0)
    if best is None or best[0] > 0.15 * img.sum(): skipped += 1; continue
    X0 = best[1]
    xh = g['xh']; up = int(1.6 * xh); dn = int(1.8 * xh)
    T = max(0, Y0 - up); Bm = min(P.shape[0], Y0 + h + dn)
    big = P[T:Bm, X0:X0 + w]
    n, lab, st, _ = cv2.connectedComponentsWithStats((big > 60).astype(np.uint8), 8)
    seed = np.zeros(big.shape, bool); seed[Y0 - T:Y0 - T + h] = img > 60
    ids = set()
    inrows = np.zeros(big.shape, bool); inrows[Y0 - T:Y0 - T + h] = True
    for c in np.unique(lab[seed & (lab > 0)]):
        comp = lab == c; tot = comp.sum(); inside = (comp & inrows).sum()
        if inside >= 0.35 * tot or tot < 0.15 * (img > 60).sum(): ids.add(c)
    new = np.where(np.isin(lab, list(ids)), big, 0)
    ys = np.nonzero((new > 60).any(1))[0]
    if len(ys) == 0: skipped += 1; continue
    top = T + ys[0]; new = new[ys[0]:ys[-1] + 1]
    g['bl'] = int(g['bl'] + (Y0 - top)); g['wy0'] = int(g['wy0'] - (Y0 - top))
    g['img'] = new.astype(np.uint8); g['recropped'] = True
    fixed += 1
pickle.dump(A, gzip.open(D + 'glyphs.pkl.gz', 'wb'))
print('перевырезано', fixed, 'пропущено', skipped)
