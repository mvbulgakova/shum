import json, sys
K = json.load(open("keep.json"))
for blk in sys.argv[1].split(";"):
    if not blk.strip(): continue
    ch, spec = blk.split("="); ch = ch.strip(); bad = set()
    for p in spec.split(","):
        p = p.strip()
        if "-" in p: a, b = map(int, p.split("-")); bad |= set(range(a, b + 1))
        elif p: bad.add(int(p))
    K[ch] = [g for k, g in enumerate(K[ch]) if k not in bad]; print(ch, len(K[ch]))
json.dump(K, open("keep.json", "w"), ensure_ascii=False)
