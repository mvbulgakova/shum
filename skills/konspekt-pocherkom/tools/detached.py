import sys
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from collections import defaultdict
f=TTFont(sys.argv[1]); gs=f.getGlyphSet(); d=defaultdict(list)
for n in f.getGlyphOrder():
    if not (n.startswith('uni') and '.v' in n): continue
    ch=chr(int(n[3:7],16))
    if not ('а'<=ch<='я'): continue
    rp=RecordingPen(); gs[n].draw(rp); cont=[];cur=[]
    for op,args in rp.value:
        if op=='moveTo': cur=[args[0]]
        elif op in('lineTo','curveTo'): cur+=list(args)
        elif op=='closePath': cont.append(cur)
    if len(cont)<2: continue
    boxes=[(min(p[0] for p in c),min(p[1] for p in c),max(p[0] for p in c),max(p[1] for p in c)) for c in cont]
    main=max(boxes,key=lambda b:(b[2]-b[0])*(b[3]-b[1]))
    for b in boxes:
        if b is main: continue
        if (b[1]>main[3]+60 or b[3]<main[1]-60) and ch not in 'йё': d[ch].append(int(n.split('.v')[1])); break
print(';'.join(f"{k}={','.join(map(str,sorted(v)))}" for k,v in d.items()))
