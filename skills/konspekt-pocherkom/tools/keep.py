import json, sys, os
ids = json.load(open("qa_ids.json"))
K = json.load(open("keep.json")) if os.path.exists("keep.json") else {}
ch = sys.argv[1]; spec = sys.argv[2]
sel = set()
for part in spec.split(","):
    part = part.strip()
    if not part: continue
    if "-" in part: a, b = map(int, part.split("-")); sel |= set(range(a, b + 1))
    else: sel.add(int(part))
K[ch] = sorted(ids[i] for i in sel if i < len(ids))
json.dump(K, open("keep.json", "w"), ensure_ascii=False)
print(ch, len(K[ch]))
