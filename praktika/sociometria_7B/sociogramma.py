import json, math, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch
D = json.load(open('result.json')); C = D['canon']; idx = D['idx']
resp = set(D['resp'])
people = [p for p in D['people'] if p != 'Аноним']
N = len(people)
def draw(q, title, fn):
    r = D['R'][q]; got = r['got']; avg = r['tot'] / N
    def ring(p):
        g = got.get(p, 0)
        return 0 if g >= 2 * avg else 1 if g >= avg else 2 if g > 0 else 3
    R = [1.5, 3.05, 4.7, 6.35]
    import networkx as nx
    G = nx.Graph(); G.add_nodes_from(people + ['Аноним'])
    for a, lst in r['M'].items():
        for b in lst: G.add_edge(a, b, weight=2 if [b, a] in [list(x) for x in r['mutual']] or (b in r['M'] and a in r['M'][b]) else 1)
    comms = sorted(nx.community.greedy_modularity_communities(G, weight='weight'), key=len, reverse=True)
    cid = {p: i for i, c in enumerate(comms) for p in c}
    fig, ax = plt.subplots(figsize=(11, 11)); ax.set_aspect('equal'); ax.axis('off')
    for rr, lab in zip([2.25, 3.85, 5.5, 7.1], ['«Звёзды»', '«Предпочитаемые»', '«Пренебрегаемые»', '«Изолированные»']):
        ax.add_patch(Circle((0, 0), rr, fill=False, lw=0.8, color='#999', ls='--'))
        ax.text(0.08, -rr + 0.08, lab, ha='left', va='bottom', fontsize=8.5, color='#777', rotation=0)
    ax.plot([0, 0], [-7.3, 7.3], color='#bbb', lw=0.8)
    ax.text(-4.5, 7.5, 'Мальчики', ha='center', fontsize=12, weight='bold'); ax.text(4.5, 7.5, 'Девочки', ha='center', fontsize=12, weight='bold')
    pos = {}
    nodes = people + (['Аноним'] if q in ('q11', 'q12') else [])
    for side in ('м', 'ж'):
        for k in range(4):
            grp = [p for p in nodes if (C[p][1] if C[p][1] != '?' else 'м') == side and (ring(p) if p != 'Аноним' else 3) == k]
            n = len(grp)
            for i, p in enumerate(sorted(grp, key=lambda p: (cid[p], -got.get(p, 0)))):
                a0, a1 = (98, 262) if side == 'м' else (-82, 82)
                if side == 'ж': a0, a1 = a1, a0
                ang = math.radians(a0 + (a1 - a0) * (i + 0.5) / max(n, 1))
                rad = R[k] + ((0.5 if i % 2 else -0.15) if n > 7 else 0)
                pos[p] = (rad * math.cos(ang), rad * math.sin(ang))
    M = r['M']; mutual = {tuple(x) for x in r['mutual']}
    for a, lst in M.items():
        for b in lst:
            if b not in pos or a not in pos: continue
            m = tuple(sorted((a, b))) in mutual
            if m and a > b: continue
            ax.add_patch(FancyArrowPatch(pos[a], pos[b], arrowstyle='<|-|>' if m else '-|>', mutation_scale=11,
                         lw=2.2 if m else 0.9, color='#c0392b' if m else '#2c3e80', shrinkA=13, shrinkB=13, alpha=0.9 if m else 0.6))
    for p, (x, y) in pos.items():
        g = got.get(p, 0)
        ax.add_patch(Circle((x, y), 0.33, facecolor='#e8f0ff' if C[p][1] == 'м' else '#ffe8ef' if C[p][1] == 'ж' else '#eee',
                            edgecolor='#333', lw=1.2, ls='-' if p in resp else (0, (3, 2)), zorder=5))
        lab = 'А' if p == 'Аноним' else str(idx[p])
        ax.text(x, y, lab, ha='center', va='center', fontsize=10, weight='bold', zorder=6)
        d = math.hypot(x, y) or 1
        ax.text(x, y - 0.38, f"{C[p][0]} ({g})", ha='center', va='top', fontsize=6.8, zorder=7,
                bbox=dict(boxstyle='round,pad=0.1', fc='white', ec='none', alpha=0.75))
    ax.set_xlim(-8, 8); ax.set_ylim(-8, 8)
    ax.set_title(title, fontsize=13)
    fig.savefig(fn, dpi=200, bbox_inches='tight'); plt.close(fig)
draw('q11', 'Социограмма 7-Б. Эмоциональный критерий (вопрос 11)', 'sociogramma_emocion.png')
draw('q12', 'Социограмма 7-Б. Деловой критерий (вопрос 12)', 'sociogramma_delovoy.png')
