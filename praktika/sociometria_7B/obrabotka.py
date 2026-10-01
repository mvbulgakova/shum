import json, collections
A = json.load(open('ankety.json'))
# фамилия -> (подпись в социоматрице, пол); порядок = алфавит
CANON = {
 "Бабишев":("Бабишев А.","м"),"Бакин":("Бакин Г. (?)","м"),"Белявцева":("Белявцева В.","ж"),"Бельская":("Бельская А.","ж"),
 "Евдокимова":("Евдокимова З.","ж"),"Карцев":("Карцев С.","м"),"Кирьянова":("Кирьянова Е.","ж"),"Колчин":("Колчин М.","м"),
 "Колчина":("Колчина В.","ж"),"Кораблинова":("Кораблинова А.","ж"),"Костров":("Костров","м"),"Лубошева":("Лубошева М.","ж"),
 "Марчукова":("Марчукова М.","ж"),"Мастеренко":("Мастеренко А.","ж"),"Машкина":("Машкина","ж"),"Нестеренко":("Нестеренко К.","м"),
 "Новиков":("Новиков М.","м"),"Поливаев":("Поливаев М.","м"),"Разумный":("Разумный Е.","м"),"Рягузов":("Рягузов М.","м"),
 "Спирин":("Спирин Р.","м"),"Стрекач":("Стрекач В.","ж"),"Тарариков":("Тарариков Д. (?)","м"),"Хохлов":("Хохлов М. (?)","м"),
 "Черников":("Черников Ф.","м"),"Чернышев":("Чернышев","м"),"Чумакова":("Чумакова М.","ж"),"Шипилова":("Шипилова А.","ж"),
 "Шкурлетов":("Шкурлетов","м"),"Шульгин":("Шульгин Т.","м"),"Юневич":("Юневич","?"),"Аноним":("Без подписи","м"),
}
ALIAS = {"Дима Черемисов (?)":"Чернышев","Пансласт (?)":"Поливаев","Дудак (?)":"Бакин","Стёпа":"Карцев","Карцев Стёпа":"Карцев","Марина Чумакова":"Чумакова","Чумакова Марина":"Чумакова"}
def key(s):
    s = s.strip().rstrip('.')
    if s in ALIAS: return ALIAS[s]
    w = s.split()[0].rstrip('.,') if s else ''
    return w if w in CANON else None
def who(a):
    if a['fio'].startswith('(без'): return "Аноним"
    return key(a['fio'].replace(' (?)',''))
resp = {who(a): a for a in A}
assert None not in resp, [a['fio'] for a in A if who(a) is None]
people = sorted(CANON, key=lambda k: (k == "Аноним", CANON[k][0]))
idx = {p: i + 1 for i, p in enumerate(people)}
unres = collections.defaultdict(list)
def choices(a, q, lim=3):
    out = []
    for s in a[q]:
        k = key(s)
        if k is None:
            if s.lower().strip() not in ('никто', 'с кем угодно', 'ничего', '') and not s.startswith('никто'): unres[q].append((a['fio'], s))
            continue
        if k == who(a) or k in out: continue
        out.append(k)
    return out[:lim]
R = {}
for q in ('q11', 'q12', 'q5'):
    M = {p: choices(resp[p], q, 3 if q != 'q5' else 9) for p in resp}
    got = collections.Counter(c for v in M.values() for c in v)
    mutual = sorted({tuple(sorted((a, b))) for a in M for b in M[a] if b in M and a in M[b]})
    tot = sum(len(v) for v in M.values())
    mf = sum(1 for a in M for b in M[a] if CANON[a][1] != CANON[b][1] and '?' not in (CANON[a][1], CANON[b][1]))
    R[q] = dict(M=M, got=got, mutual=mutual, tot=tot, mf=mf, made=sum(1 for v in M.values() if v))
json.dump(dict(people=people, idx=idx, canon=CANON, resp=list(resp),
               R={q: dict(M=r['M'], got=dict(r['got']), mutual=r['mutual'], tot=r['tot'], mf=r['mf'], made=r['made']) for q, r in R.items()},
               unres=unres), open('result.json', 'w'), ensure_ascii=False, indent=1)
N = len(people)
for q in ('q11', 'q12'):
    r = R[q]; avg = r['tot'] / N
    print(q, 'всего', r['tot'], 'сделали', r['made'], 'сред', round(avg, 2), 'вз.пар', len(r['mutual']),
          'КВ', round(2 * len(r['mutual']) / r['tot'] * 100), '% мж', r['mf'])
    print('  ', sorted(((CANON[p][0], r['got'].get(p, 0)) for p in people), key=lambda x: -x[1]))
    print('  взаимные', [(CANON[a][0], CANON[b][0]) for a, b in r['mutual']])
print('q5', sorted(((CANON[p][0], R['q5']['got'].get(p, 0)) for p in people if R['q5']['got'].get(p)), key=lambda x: -x[1]))
print('нераспознано', dict(unres))
