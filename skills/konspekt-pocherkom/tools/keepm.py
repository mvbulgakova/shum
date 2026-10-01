import json, sys, os
M = json.load(open("qa_multi.json")); K = json.load(open("keep.json"))
for blk in sys.argv[1].split(";"):
    if not blk.strip(): continue
    ch, spec = blk.split("=", 1); ch = ch.strip()
    ids = M[ch]; sel = set()
    if spec.strip() == "all": sel = set(range(len(ids)))
    else:
        for p in spec.split(","):
            p = p.strip()
            if not p: continue
            if "-" in p: a, b = map(int, p.split("-")); sel |= set(range(a, b + 1))
            else: sel.add(int(p))
    K[ch] = sorted(ids[i] for i in sel if i < len(ids)); print(ch, len(K[ch]))
json.dump(K, open("keep.json", "w"), ensure_ascii=False)
