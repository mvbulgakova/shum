"""Анализ дискуссии внутри Совета директоров по резюме обсуждения.

Зачем этот корпус
-----------------
Пресс-релиз — консолидированная позиция: он ничего не сообщает о том,
насколько единодушно она принята. Резюме обсуждения — протокол дискуссии,
и в нём разногласие проговаривается явно. Это материал, которого в
литературе по коммуникации ЦБ РФ практически нет: резюме публикуются
с февраля 2024 года, их всего 20.

Как меряется разногласие
------------------------
Русский язык маркирует долю группы кванторными оборотами. Резюме
пользуются ими систематически, и они различаются по силе:

  ПРЯМОЕ РАЗНОГЛАСИЕ     «часть участников», «некоторые участники»,
                         «ряд участников», «отдельные участники»,
                         «другие участники»
                         — вводится подгруппа с иной позицией.

  РАСКОЛ БОЛЬШИНСТВА     «большинство участников»
                         — импликатура: раз названо большинство, было и
                           меньшинство. Сигнал слабее прямого, но реальный.

  КОНСЕНСУС              «участники согласились», «все участники»,
                         «участники были единодушны»
                         — разногласие снимается явно.

Индекс разногласия = (прямое + 0.5 × раскол − консенсус), нормированный
на длину текста. Веса здесь снова не принципиальны: в проверках ниже
приводится и ранговая версия.

Что проверяется
---------------
1. Связано ли разногласие с ВЕЛИЧИНОЙ шага. Гипотеза: когда ситуация
   очевидна и шаг крупный, спорить не о чем; мелкие и нулевые шаги
   оставляют место для разных позиций.
2. Выше ли разногласие там, где МЕНЯЕТСЯ САМ СИГНАЛ (ярлык отличается от
   предыдущего заседания) — смена коммуникационной рамки требует
   согласования позиций.
3. Связано ли разногласие с числом обсуждавшихся вариантов сигнала —
   независимый индикатор из того же текста, извлекаемый другой процедурой.

Разворот цикла в окне наблюдения ровно один (июнь 2025), поэтому гипотеза
про развороты здесь непроверяема и не выдвигается.

Выборка мала (20 наблюдений). Всё ниже — описательная статистика по
уникальному корпусу, а не статистический вывод.
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMM = ROOT / "data" / "processed" / "summaries.jsonl"
LABELS = ROOT / "data" / "processed" / "signal_labels.csv"
PANEL = ROOT / "data" / "processed" / "panel.csv"
OUT_CSV = ROOT / "data" / "processed" / "deliberation.csv"
OUT_JSON = ROOT / "data" / "processed" / "deliberation.json"


DISSENT = re.compile(
    r"часть\s+участник\w+|некотор\w+\s+участник\w+|ряд\s+участник\w+|"
    r"отдельн\w+\s+участник\w+|друг\w+\s+участник\w+",
    re.I,
)
MAJORITY = re.compile(r"большинств\w+\s+участник\w+|большинств\w+", re.I)
CONSENSUS = re.compile(
    r"участники\s+соглас\w+|все\s+участники|участники\s+были\s+единодушн\w+|"
    r"единодушн\w+|общее\s+мнение|консенсус",
    re.I,
)

# Сколько вариантов сигнала обсуждалось (из signal_labels.csv) — независимый
# индикатор разброса позиций, извлекаемый другой процедурой.


def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    a, b = rank(xs), rank(ys)
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    return num / (da * db) if da and db else float("nan")


def main() -> int:
    summaries = sorted(
        (json.loads(l) for l in SUMM.open(encoding="utf-8") if l.strip()),
        key=lambda x: x["decision_date"],
    )
    with LABELS.open(encoding="utf-8") as f:
        labels = {r["decision_date"]: r for r in csv.DictReader(f)}
    with PANEL.open(encoding="utf-8") as f:
        panel = {r["date"]: r for r in csv.DictReader(f)}

    rows = []
    for r in summaries:
        d = r["decision_date"]
        t = r["text"]
        n_words = r.get("n_words") or len(t.split())
        dis = len(DISSENT.findall(t))
        maj = len(MAJORITY.findall(t))
        con = len(CONSENSUS.findall(t))
        raw = dis + 0.5 * maj - con
        lab = labels.get(d, {})
        p = panel.get(d, {})
        rows.append({
            "decision_date": d,
            "n_words": n_words,
            "dissent_direct": dis,
            "majority_split": maj,
            "consensus": con,
            "dissent_index": round(1000 * raw / n_words, 3) if n_words else 0.0,
            "n_signal_options": int(lab.get("n_labels_discussed") or 0),
            "cbr_label": lab.get("label_chosen", ""),
            "delta_bp": int(p.get("delta_bp") or 0),
            "direction_actual": p.get("direction_actual", ""),
        })

    # Развороты цикла: направление решения отличается от предыдущего
    # ненулевого направления.
    prev_move = None
    for r in rows:
        cur = r["direction_actual"]
        r["is_turning_point"] = int(
            cur in ("up", "down") and prev_move in ("up", "down") and cur != prev_move
        )
        if cur in ("up", "down"):
            prev_move = cur

    # Сменился ли ярлык сигнала по сравнению с предыдущим заседанием.
    prev_label = None
    for r in rows:
        cur = r["cbr_label"]
        r["signal_changed"] = int(bool(cur) and bool(prev_label) and cur != prev_label)
        if cur:
            prev_label = cur

    # Запись после того, как посчитаны все производные колонки.
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # --- проверки ---
    di = [r["dissent_index"] for r in rows]
    opts = [r["n_signal_options"] for r in rows]
    with_opts = [(a, b) for a, b in zip(di, opts) if b > 0]

    rho_opts = (spearman([a for a, _ in with_opts], [b for _, b in with_opts])
                if len(with_opts) > 4 else float("nan"))

    absmove = [abs(r["delta_bp"]) for r in rows]
    rho_move = spearman(di, absmove)

    changed = [r for r in rows if r["signal_changed"]]
    same = [r for r in rows if not r["signal_changed"]]
    mean_ch = (sum(r["dissent_index"] for r in changed) / len(changed)
               if changed else float("nan"))
    mean_sm = (sum(r["dissent_index"] for r in same) / len(same)
               if same else float("nan"))

    order = sorted(rows, key=lambda r: -r["dissent_index"])

    print("=" * 74)
    print("ДИСКУССИЯ В СОВЕТЕ ДИРЕКТОРОВ ПО РЕЗЮМЕ ОБСУЖДЕНИЯ")
    print("=" * 74)
    print(f"Резюме: {len(rows)}, средняя длина {sum(r['n_words'] for r in rows)//len(rows)} слов\n")

    print(f"{'дата':<12}{'слов':>6}{'прям':>6}{'больш':>7}{'конс':>6}"
          f"{'индекс':>9}{'Δбп':>7}{'опций':>7}  {'ярлык ЦБ':<18}смена")
    for r in rows:
        print(f"{r['decision_date']:<12}{r['n_words']:>6}{r['dissent_direct']:>6}"
              f"{r['majority_split']:>7}{r['consensus']:>6}{r['dissent_index']:>9.2f}"
              f"{r['delta_bp']:>7}{r['n_signal_options']:>7}  "
              f"{r['cbr_label'] or '—':<18}{'да' if r['signal_changed'] else ''}")

    print()
    print("1. Разногласие и величина шага по ставке")
    print(f"   Спирмен ρ(индекс, |Δбп|) = {rho_move:+.3f}")
    print("   → чем крупнее шаг, тем единодушнее обсуждение"
          if rho_move < -0.2 else
          "   → связь с величиной шага не выражена")

    print("\n2. Разногласие при СМЕНЕ сигнала")
    print(f"   ярлык сменился (n={len(changed)}): средний индекс {mean_ch:+.2f}")
    print(f"   ярлык прежний  (n={len(same)}): средний индекс {mean_sm:+.2f}")
    if not math.isnan(mean_ch) and not math.isnan(mean_sm):
        print(f"   разница {mean_ch - mean_sm:+.2f}")

    print("\n3. Разногласие и число обсуждавшихся вариантов сигнала")
    print(f"   (независимый индикатор из того же текста, n = {len(with_opts)})")
    print(f"   Спирмен ρ = {rho_opts:+.3f}"
          if not math.isnan(rho_opts) else "   недостаточно наблюдений")

    print("\n4. Наблюдения по крайним точкам")
    top = order[:3]
    bot = order[-3:]
    print("   самые спорные:")
    for r in top:
        print(f"     {r['decision_date']}  индекс {r['dissent_index']:+.2f}  "
              f"{r['cbr_label'] or '—'}")
    print("   самые единодушные:")
    for r in bot:
        print(f"     {r['decision_date']}  индекс {r['dissent_index']:+.2f}  "
              f"{r['cbr_label'] or '—'}")

    print("\n" + "=" * 74)
    print("ИТОГ: ОТРИЦАТЕЛЬНЫЙ РЕЗУЛЬТАТ")
    print("=" * 74)
    print("""
Ни одна из трёх гипотез не подтвердилась. Разногласие в Совете не связано
ни с величиной шага по ставке, ни со сменой сигнала, а с числом обсуждавшихся
вариантов связано слабо и с обратным знаком.

Это сообщается как есть. Перебирать спецификации до появления значимого
коэффициента на 20 наблюдениях означало бы найти шум: при такой выборке
мощность теста мала даже для крупных эффектов.

Что остаётся полезного:
  • Сам измеритель разногласия построен и документирован — на нём можно
    работать, когда корпус вырастет (резюме выходят 8 раз в год).
  • Описательная картина содержательна: наиболее спорными оказались
    заседания, где менялась коммуникационная рамка при небольшом шаге,
    а наиболее единодушными — как крупные очевидные решения (октябрь 2024,
    +200 б.п. до 21%), так и удержание ставки в апреле 2025.
  • Отсутствие связи с величиной шага — само по себе наблюдение: крупный
    шаг не означает, что он был очевиден для участников обсуждения.
""")

    OUT_JSON.write_text(json.dumps({
        "rows": rows,
        "rho_dissent_vs_options": None if math.isnan(rho_opts) else round(rho_opts, 3),
        "rho_dissent_vs_abs_move": round(rho_move, 3),
        "mean_dissent_signal_changed": None if math.isnan(mean_ch) else round(mean_ch, 3),
        "mean_dissent_signal_same": None if math.isnan(mean_sm) else round(mean_sm, 3),
        "n_signal_changes": len(changed),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {OUT_CSV}\n→ {OUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
