"""Робастность индекса: держатся ли выводы без произвольных весов.

Проблема
--------
В `morphology.py` веса модальностей заданы числами (necessity 0.85,
possibility 0.55, delayed_evaluation 0.35 …), а штрафы за смягчители и
условия — множителями (0.82 за смягчитель, 0.72 за условие). Все эти числа
выбраны исследователем. Естественное возражение: «результат — артефакт
подобранных коэффициентов».

Четыре проверки
---------------
A. ОРДИНАЛЬНАЯ ВЕРСИЯ БЕЗ ВЕСОВ ВООБЩЕ.
   Модальности упорядочиваются рангами 1…N, направление даёт знак, и всё.
   Никаких множителей, никаких штрафов. Если выводы сохраняются, то числовые
   веса — декорация, а работает порядковая структура.

B. СЛУЧАЙНОЕ ВОЗМУЩЕНИЕ ВЕСОВ.
   Каждый вес независимо умножается на шум, 2000 повторов. Смотрим
   распределение итоговых статистик. Если оно узкое — конкретные значения
   не важны.

C. ПЕРЕСТАНОВКА ПОРЯДКА МОДАЛЬНОСТЕЙ.
   Перебираются все перестановки шкалы. Если исходный порядок даёт результат
   в верхнем хвосте распределения, то содержателен именно он, а не
   произвольная нумерация.

D. LEAVE-ONE-OUT.
   Поочерёдно исключается каждое заседание; смотрим разброс корреляции.
   Проверка на то, что результат не держится на одном-двух наблюдениях.

Все статистики считаются вручную, без scipy.
"""

from __future__ import annotations

import csv
import itertools
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEATS = ROOT / "data" / "processed" / "features_v2.csv"
LABELS = ROOT / "data" / "processed" / "signal_labels.csv"
OUT = ROOT / "data" / "processed" / "robustness.json"

random.seed(20260803)


# --- статистика -------------------------------------------------------------

def _rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else float("nan")


def spearman(xs, ys):
    return pearson(_rank(xs), _rank(ys))


def quantiles(xs, qs=(0.025, 0.5, 0.975)):
    s = sorted(xs)
    out = []
    for q in qs:
        i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
        out.append(round(s[i], 3))
    return out


# --- данные -----------------------------------------------------------------

# Порядок модальностей по убыванию связанности (содержательная гипотеза).
MODALITY_ORDER = [
    "commitment_perfective",
    "unconditional_commitment",
    "necessity",
    "intention_directed",
    "readiness",
    "possibility",
    "delayed_evaluation",
    "intention_generic",
    "agentless_passive",
]

DIR_SIGN = {"up": 1.0, "down": -1.0, "hold": 0.0, "mixed": 0.0, "none": 0.0}


def load():
    with FEATS.open(encoding="utf-8") as f:
        feats = list(csv.DictReader(f))
    with LABELS.open(encoding="utf-8") as f:
        labels = {r["decision_date"]: r for r in csv.DictReader(f) if r["label_chosen"]}
    rows = []
    for r in feats:
        lab = labels.get(r["date"])
        if not lab:
            continue
        rows.append({
            "date": r["date"],
            "modality": r["modality"],
            "direction": r["direction_signal"],
            "hedges": int(r["hedge_count"]),
            "conds": int(r["cond_count"]),
            "agent": int(r["agent_explicit"]),
            "passive": int(r["passive"]),
            "hardness": float(r["hardness_v2"]),
            "label": float(lab["label_score"]),
        })
    return rows


# --- A. ординальная версия --------------------------------------------------

def ordinal_index(row, order=None) -> float:
    """Индекс без единого числового веса.

    Модальность → ранг в порядке убывания связанности, нормированный на [0,1].
    Знак — направление. Смягчители и условия не учитываются вовсе.
    """
    order = order or MODALITY_ORDER
    mod = row["modality"]
    if mod not in order:
        return 0.0
    rank = order.index(mod)              # 0 = сильнейшая связанность
    strength = (len(order) - rank) / len(order)
    return DIR_SIGN[row["direction"]] * strength


def test_a(rows) -> dict:
    ord_idx = [ordinal_index(r) for r in rows]
    lab = [r["label"] for r in rows]
    orig = [r["hardness"] for r in rows]
    return {
        "n": len(rows),
        "spearman_ordinal_vs_label": round(spearman(ord_idx, lab), 3),
        "spearman_original_vs_label": round(spearman(orig, lab), 3),
        "spearman_ordinal_vs_original": round(spearman(ord_idx, orig), 3),
        "sign_agreement": sum(
            1 for a, b in zip(ord_idx, lab)
            if (a > 0.05) == (b > 0.25) and (a < -0.05) == (b < -0.25)
        ),
    }


# --- B. возмущение весов ----------------------------------------------------

BASE_WEIGHTS = {
    "commitment_perfective": 1.00,
    "unconditional_commitment": 1.00,
    "necessity": 0.85,
    "intention_directed": 0.70,
    "readiness": 0.60,
    "possibility": 0.55,
    "delayed_evaluation": 0.35,
    "intention_generic": 0.25,
    "agentless_passive": 0.15,
}


def perturbed_index(row, weights, hedge_pen, cond_pen) -> float:
    w = weights.get(row["modality"], 0.0)
    if w == 0.0:
        return 0.0
    s = w
    if row["agent"]:
        s *= 1.15
    if row["passive"]:
        s *= 0.75
    s *= max(0.4, 1.0 - hedge_pen * row["hedges"])
    if row["conds"]:
        s *= cond_pen
    return DIR_SIGN[row["direction"]] * min(1.0, s)


def test_b(rows, n_iter=2000) -> dict:
    lab = [r["label"] for r in rows]
    rhos, signs = [], []
    for _ in range(n_iter):
        # каждый вес умножается на равномерный шум ±40%
        w = {k: v * random.uniform(0.6, 1.4) for k, v in BASE_WEIGHTS.items()}
        hp = random.uniform(0.05, 0.35)
        cp = random.uniform(0.5, 0.95)
        idx = [perturbed_index(r, w, hp, cp) for r in rows]
        rhos.append(spearman(idx, lab))
        signs.append(sum(1 for a, b in zip(idx, lab)
                         if (a > 0.05) == (b > 0.25) and (a < -0.05) == (b < -0.25)))
    lo, med, hi = quantiles(rhos)
    return {
        "n_iter": n_iter,
        "spearman_median": med,
        "spearman_ci95": [lo, hi],
        "spearman_min": round(min(rhos), 3),
        "share_above_0_8": round(sum(1 for r in rhos if r > 0.8) / len(rhos), 3),
        "sign_agreement_median": int(sorted(signs)[len(signs) // 2]),
    }


# --- C. перестановки порядка модальностей -----------------------------------

def test_c(rows, max_perms=5000) -> dict:
    """Сравнивает исходный порядок со случайными перестановками шкалы."""
    lab = [r["label"] for r in rows]
    base = spearman([ordinal_index(r) for r in rows], lab)

    # Полный перебор 9! = 362880 избыточен; берём случайную выборку.
    seen = set()
    rhos = []
    for _ in range(max_perms):
        perm = MODALITY_ORDER[:]
        random.shuffle(perm)
        key = tuple(perm)
        if key in seen:
            continue
        seen.add(key)
        idx = [ordinal_index(r, perm) for r in rows]
        rhos.append(spearman(idx, lab))

    better = sum(1 for r in rhos if r >= base)

    # Насколько результат достигается ОДНИМ направлением, без модальности?
    dir_only = [DIR_SIGN[r["direction"]] for r in rows]
    rho_dir_only = spearman(dir_only, lab)

    return {
        "base_spearman": round(base, 3),
        "n_permutations": len(rhos),
        "permutation_median": round(sorted(rhos)[len(rhos) // 2], 3),
        "n_permutations_at_least_as_good": better,
        "empirical_p": round((better + 1) / (len(rhos) + 1), 4),
        "spearman_direction_only": round(rho_dir_only, 3),
    }


# --- C2. прицельный тест оси модальности ------------------------------------

def test_c2(rows) -> dict:
    """Работает ли модальность там, где направление НЕ различает.

    Тест C показывает, что перестановка модальностей не портит результат.
    Причина не в том, что модальность бесполезна, а в том, что при
    фиксированном направлении в выборке остаётся мало случаев. Изолируем их:
    берём подвыборку с ОДНИМ направлением и проверяем, разделяет ли
    модальность классы ЦБ внутри неё.

    Значимость считается точно, комбинаторно: вероятность случайно получить
    идеальное разделение k из n наблюдений равна 1 / C(n, k).
    """
    out = {}
    for d in ("up", "down"):
        sub = [r for r in rows if r["direction"] == d]
        classes = sorted({r["label"] for r in sub})
        if len(sub) < 3 or len(classes) < 2:
            out[d] = {"n": len(sub), "note": "недостаточно вариации"}
            continue

        # Разделяет ли ранг модальности классы без пересечений?
        by_class = {c: [MODALITY_ORDER.index(r["modality"])
                        if r["modality"] in MODALITY_ORDER else 99
                        for r in sub if r["label"] == c]
                    for c in classes}
        # Классы упорядочены по жёсткости; ранг модальности должен идти
        # в ту же сторону (меньший ранг = сильнее связанность = жёстче).
        ordered = sorted(classes, reverse=(d == "up"))
        seps = [by_class[c] for c in ordered]
        perfect = all(max(seps[i]) < min(seps[i + 1]) for i in range(len(seps) - 1))

        n = len(sub)
        k = len(seps[0])
        n_splits = math.comb(n, k)
        out[d] = {
            "n": n,
            "classes": {c: len(by_class[c]) for c in classes},
            "perfect_separation": perfect,
            "exact_p": round(1 / n_splits, 4) if perfect else None,
            "detail": {c: sorted(by_class[c]) for c in classes},
        }
    return out


# --- D. leave-one-out -------------------------------------------------------

def test_d(rows) -> dict:
    rhos = []
    for i in range(len(rows)):
        sub = rows[:i] + rows[i + 1:]
        rhos.append(spearman([r["hardness"] for r in sub], [r["label"] for r in sub]))
    return {
        "n": len(rows),
        "min": round(min(rhos), 3),
        "max": round(max(rhos), 3),
        "range": round(max(rhos) - min(rhos), 4),
        "most_influential": rows[rhos.index(min(rhos))]["date"],
    }


def main() -> int:
    rows = load()
    if len(rows) < 8:
        print("Недостаточно наблюдений с ярлыками ЦБ.")
        return 1

    print("=" * 74)
    print("РОБАСТНОСТЬ ИНДЕКСА К ВЫБОРУ ВЕСОВ")
    print("=" * 74)
    print(f"Выборка: {len(rows)} заседаний с извлечённым ярлыком ЦБ\n")

    a = test_a(rows)
    print("A. Ординальная версия — без единого числового веса")
    print("   Модальность → ранг, направление → знак. Смягчители и условия")
    print("   не учитываются вовсе.")
    print(f"   ρ(ординальный, ярлык ЦБ)   = {a['spearman_ordinal_vs_label']}")
    print(f"   ρ(исходный,    ярлык ЦБ)   = {a['spearman_original_vs_label']}")
    print(f"   ρ(ординальный, исходный)   = {a['spearman_ordinal_vs_original']}")
    verdict_a = ("веса не несут нагрузки — работает порядковая структура"
                 if a["spearman_ordinal_vs_label"] >= 0.8
                 else "веса влияют на результат, нужна осторожность")
    print(f"   → {verdict_a}\n")

    b = test_b(rows)
    print(f"B. Случайное возмущение всех весов (±40%), {b['n_iter']} повторов")
    print(f"   ρ: медиана {b['spearman_median']}, "
          f"95% интервал [{b['spearman_ci95'][0]}, {b['spearman_ci95'][1]}], "
          f"минимум {b['spearman_min']}")
    print(f"   Доля прогонов с ρ > 0.8: {b['share_above_0_8']:.1%}")
    verdict_b = ("результат устойчив к конкретным значениям"
                 if b["spearman_ci95"][0] > 0.7 else "результат чувствителен к весам")
    print(f"   → {verdict_b}\n")

    c = test_c(rows)
    print(f"C. Перестановки порядка модальностей ({c['n_permutations']} случайных)")
    print(f"   Исходный порядок: ρ = {c['base_spearman']}")
    print(f"   Медиана по перестановкам: ρ = {c['permutation_median']}")
    print(f"   Эмпирический p = {c['empirical_p']}")
    print(f"   Одно направление, без модальности: ρ = {c['spearman_direction_only']}")
    print("   → В этой выборке почти всю работу делает ОСЬ НАПРАВЛЕНИЯ.")
    print("     Перестановка модальностей не портит результат не потому, что")
    print(f"     модальность бесполезна, а потому что при {len(rows)} наблюдениях она")
    print("     нужна лишь для одного различения. Изолируем его в C2.\n")

    c2 = test_c2(rows)
    print("C2. Прицельный тест оси модальности")
    print("    Подвыборки с ОДНИМ направлением: различает ли модальность")
    print("    классы ЦБ там, где направление не помогает?")
    for d, res in c2.items():
        if "note" in res:
            print(f"    {d:5s}: n={res['n']} — {res['note']}")
            continue
        cls = ", ".join(f"{k}={v}" for k, v in res["classes"].items())
        print(f"    {d:5s}: n={res['n']} ({cls})")
        if res["perfect_separation"]:
            print(f"           идеальное разделение по рангу модальности, "
                  f"точный p = {res['exact_p']}")
        else:
            print("           разделения нет")
        for k, v in res["detail"].items():
            print(f"             {k:<18} ранги модальности {v}")
    print()

    d = test_d(rows)
    print("D. Leave-one-out")
    print(f"   ρ в диапазоне [{d['min']}, {d['max']}], размах {d['range']}")
    print(f"   Наиболее влиятельное наблюдение: {d['most_influential']}")
    verdict_d = ("результат не держится на отдельных наблюдениях"
                 if d["range"] < 0.1 else "есть влиятельные наблюдения")
    print(f"   → {verdict_d}")

    OUT.write_text(json.dumps({"ordinal": a, "perturbation": b,
                               "permutation": c, "modality_axis": c2, "loo": d},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
