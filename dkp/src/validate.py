"""Валидация индекса жёсткости. Три независимых теста.

Проблема, ради которой это написано
-----------------------------------
Любой индекс тональности упрекают в произвольности шкалы. Нужны проверки,
которые не опираются на суждение автора. Здесь их три, по возрастанию силы.

ТЕСТ 1. Конструктная валидность против собственной таксономии ЦБ.
    Индекс считается по ПРЕСС-РЕЛИЗУ. Ярлык («жёсткий», «умеренно жёсткий»,
    «нейтральный», «умеренно мягкий») извлекается из РЕЗЮМЕ ОБСУЖДЕНИЯ —
    другого документа, опубликованного на шесть рабочих дней позже.
    Проверка не круговая: два разных текста, разные процедуры извлечения.
    Метрика — ранговая корреляция Спирмена и точность попадания в класс.

ТЕСТ 2. Воспроизводит ли (модальность × вектор) таксономию ЦБ.
    ЦБ сам расшифровал свои ярлыки:
        жёсткий          = «допускает возможность повышения»
        умеренно жёсткий = «оценит целесообразность повышения»
        умеренно мягкий  = «об оценке целесообразности снижения»
        нейтральный      = «без указания на направленность»
    Это в точности перекрёстная таблица (модальность × направление).
    Проверяем, воспроизводит ли её независимо посчитанная пара признаков.

ТЕСТ 3. Предсказательная сила: индекс(t) → изменение ставки(t+1).
    Если сигнал информативен, жёсткость на заседании t должна коррелировать
    с фактическим шагом на заседании t+1. Тест на предсказание, не на
    причинность — поэтому корректен без инструментальных переменных.
    Сравнивается с наивным словарным бенчмарком (подсчёт «ястребиных» и
    «голубиных» слов без учёта морфосинтаксиса).

Все статистики считаются вручную (без scipy), чтобы не тянуть зависимость.
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEATS = ROOT / "data" / "processed" / "features_v2.csv"
LABELS = ROOT / "data" / "processed" / "signal_labels.csv"
PRESS = ROOT / "data" / "processed" / "press.jsonl"
OUT = ROOT / "data" / "processed" / "validation.json"


# ---------------------------------------------------------------------------
# Статистика без внешних зависимостей
# ---------------------------------------------------------------------------

def _rank(xs: list[float]) -> list[float]:
    """Ранги со средним для связок."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else float("nan")


def spearman(xs: list[float], ys: list[float]) -> float:
    return pearson(_rank(xs), _rank(ys))


def t_stat(r: float, n: int) -> float:
    """t-статистика для коэффициента корреляции."""
    if n < 3 or abs(r) >= 1:
        return float("nan")
    return r * math.sqrt((n - 2) / (1 - r * r))


def p_two_sided(t: float, df: int) -> float:
    """Двусторонний p-value через нормальную аппроксимацию (df>=20 достаточно)."""
    if math.isnan(t):
        return float("nan")
    z = abs(t)
    # аппроксимация хвоста стандартного нормального
    return 2 * 0.5 * math.erfc(z / math.sqrt(2))


# ---------------------------------------------------------------------------
# Наивный словарный бенчмарк — то, с чем сравниваемся
# ---------------------------------------------------------------------------

HAWKISH_WORDS = re.compile(
    r"\b(ужесточ\w*|повыш\w*|жестк\w*|ж[ёе]стк\w*|проинфляцион\w*|"
    r"инфляцион\w+\s+риск\w*|перегрев\w*|напряжен\w*)", re.I)
DOVISH_WORDS = re.compile(
    r"\b(сниж\w*|смягч\w*|мягк\w*|дезинфляцион\w*|замедлен\w*|"
    r"охлажден\w*|ослаблен\w*)", re.I)


def dictionary_score(text: str) -> float:
    """Наивная тональность: (ястребиные − голубиные) / всего.

    Ровно то, что делают существующие работы. Не учитывает ни модальность,
    ни направление, ни то, к чему относится слово.
    """
    h = len(HAWKISH_WORDS.findall(text))
    d = len(DOVISH_WORDS.findall(text))
    return (h - d) / (h + d) if (h + d) else 0.0


# ---------------------------------------------------------------------------
# Загрузка
# ---------------------------------------------------------------------------

def load() -> tuple[list[dict], dict[str, dict], dict[str, str]]:
    with FEATS.open(encoding="utf-8") as f:
        feats = list(csv.DictReader(f))
    with LABELS.open(encoding="utf-8") as f:
        labels = {r["decision_date"]: r for r in csv.DictReader(f) if r["label_chosen"]}
    texts = {}
    with PRESS.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                texts[r["date"]] = r["text"]
    return feats, labels, texts


# ---------------------------------------------------------------------------
# ТЕСТ 1: против собственной таксономии ЦБ
# ---------------------------------------------------------------------------

def test1(feats: list[dict], labels: dict[str, dict]) -> dict:
    pairs = []
    for r in feats:
        lab = labels.get(r["date"])
        if not lab:
            continue
        pairs.append((r["date"], float(r["hardness_v2"]), float(lab["label_score"]),
                      lab["label_chosen"]))

    if len(pairs) < 3:
        return {"n": len(pairs), "note": "недостаточно наблюдений"}

    idx = [p[1] for p in pairs]
    lab = [p[2] for p in pairs]
    rho = spearman(idx, lab)
    r = pearson(idx, lab)
    n = len(pairs)

    # Знаковое согласие: совпадает ли направление (ястреб/нейтр/голубь).
    def sign_bucket(v: float, thr: float = 0.12) -> int:
        return 1 if v > thr else -1 if v < -thr else 0

    agree = sum(1 for _, i, l, _ in pairs if sign_bucket(i) == sign_bucket(l, 0.25))
    return {
        "n": n,
        "spearman": round(rho, 3),
        "pearson": round(r, 3),
        "t": round(t_stat(rho, n), 2),
        "p": round(p_two_sided(t_stat(rho, n), n - 2), 4),
        "sign_agreement": f"{agree}/{n}",
        "sign_agreement_pct": round(100 * agree / n, 1),
        "pairs": [{"date": d, "index": i, "cbr_label": lb, "cbr_score": l}
                  for d, i, l, lb in pairs],
    }


# ---------------------------------------------------------------------------
# ТЕСТ 2: воспроизводит ли (модальность × вектор) таксономию ЦБ
# ---------------------------------------------------------------------------

# Отображение, выведенное ИЗ расшифровок самого ЦБ, а не назначенное автором.
#
# ВАЖНО про статус строк. Первые четыре выведены напрямую из расшифровок,
# которые ЦБ дал в резюме («жесткий (допускает возможность повышения)»), —
# они получены ДО сопоставления с ярлыками и потому являются независимой
# проверкой. Строки с 'hold' и 'none' добавлены ПОСЛЕ того, как выяснилось,
# что ЦБ относит «будет поддерживать жёсткость ДКУ» к нейтральному сигналу.
# Это калибровка под наблюдаемую практику, а не независимое подтверждение;
# в отчёте они помечены отдельно.
CBR_CROSSTAB: dict[tuple[str, str], str] = {
    # — выведено из расшифровок ЦБ (независимо) —
    ("possibility", "up"): "жесткий",
    ("delayed_evaluation", "up"): "умеренно жесткий",
    ("possibility", "down"): "мягкий",
    ("delayed_evaluation", "down"): "умеренно мягкий",
    # — калибровано по наблюдаемым ярлыкам (не независимо) —
    ("intention_generic", "none"): "нейтральный",
    ("agentless_passive", "none"): "нейтральный",
    ("intention_directed", "hold"): "нейтральный",
    ("readiness", "hold"): "нейтральный",
    ("commitment_perfective", "hold"): "нейтральный",
}

# Какие ячейки получены независимо от ярлыков (для честной отчётности).
INDEPENDENT_CELLS = {
    ("possibility", "up"), ("delayed_evaluation", "up"),
    ("possibility", "down"), ("delayed_evaluation", "down"),
}


def test2(feats: list[dict], labels: dict[str, dict]) -> dict:
    rows, hits = [], 0
    for r in feats:
        lab = labels.get(r["date"])
        if not lab:
            continue
        cell = (r["modality"], r["direction_signal"])
        pred = CBR_CROSSTAB.get(cell, "")
        actual = lab["label_chosen"]
        ok = pred == actual
        hits += ok
        rows.append({
            "date": r["date"],
            "modality": r["modality"],
            "direction": r["direction_signal"],
            "predicted": pred or "—",
            "cbr_actual": actual,
            "match": ok,
            "independent": cell in INDEPENDENT_CELLS,
        })
    covered = [x for x in rows if x["predicted"] != "—"]
    indep = [x for x in rows if x["independent"]]
    return {
        "n": len(rows),
        "n_covered": len(covered),
        "exact_match": hits,
        "exact_match_pct": round(100 * hits / len(rows), 1) if rows else 0,
        "match_where_covered_pct": round(100 * sum(x["match"] for x in covered) / len(covered), 1) if covered else 0,
        "n_independent": len(indep),
        "independent_match": sum(x["match"] for x in indep),
        "independent_match_pct": round(100 * sum(x["match"] for x in indep) / len(indep), 1) if indep else 0,
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# ТЕСТ 3: предсказание следующего решения
# ---------------------------------------------------------------------------

def test3(feats: list[dict], texts: dict[str, str]) -> dict:
    feats = sorted(feats, key=lambda r: r["date"])
    idx_now, dict_now, next_delta, dates = [], [], [], []
    for i in range(len(feats) - 1):
        cur, nxt = feats[i], feats[i + 1]
        idx_now.append(float(cur["hardness_v2"]))
        dict_now.append(dictionary_score(texts[cur["date"]]))
        next_delta.append(float(nxt["delta_bp"]))
        dates.append(cur["date"])

    n = len(idx_now)
    res = {"n": n}
    for name, xs in (("index_v2", idx_now), ("dictionary_baseline", dict_now)):
        rho = spearman(xs, next_delta)
        r = pearson(xs, next_delta)
        res[name] = {
            "spearman": round(rho, 3),
            "pearson": round(r, 3),
            "t": round(t_stat(rho, n), 2),
            "p": round(p_two_sided(t_stat(rho, n), n - 2), 4),
        }

    # Отдельно — на подвыборке 2022–2026 (экстремальный цикл, ядро работы).
    sub = [(x, d, dt) for x, d, dt in zip(idx_now, next_delta, dates) if dt >= "2022-01-01"]
    if len(sub) > 5:
        xs = [s[0] for s in sub]
        ys = [s[1] for s in sub]
        rho = spearman(xs, ys)
        res["index_v2_2022plus"] = {
            "n": len(sub),
            "spearman": round(rho, 3),
            "t": round(t_stat(rho, len(sub)), 2),
            "p": round(p_two_sided(t_stat(rho, len(sub)), len(sub) - 2), 4),
        }
    return res


def main() -> int:
    feats, labels, texts = load()

    print("=" * 72)
    print("ТЕСТ 1 · Конструктная валидность: индекс (пресс-релиз) vs ярлык (резюме)")
    print("=" * 72)
    t1 = test1(feats, labels)
    if t1.get("n", 0) >= 3:
        print(f"n = {t1['n']} заседаний с извлечённым ярлыком ЦБ")
        print(f"Спирмен ρ = {t1['spearman']}   (t = {t1['t']}, p = {t1['p']})")
        print(f"Пирсон  r = {t1['pearson']}")
        print(f"Согласие по знаку: {t1['sign_agreement']} ({t1['sign_agreement_pct']}%)")
        print(f"\n{'дата':<12} {'индекс':>8}  {'ярлык ЦБ':<18} {'шкала':>6}")
        for p in t1["pairs"]:
            print(f"{p['date']:<12} {p['index']:>+8.3f}  {p['cbr_label']:<18} {p['cbr_score']:>+6.1f}")

    print()
    print("=" * 72)
    print("ТЕСТ 2 · Воспроизводит ли (модальность × вектор) таксономию ЦБ")
    print("=" * 72)
    t2 = test2(feats, labels)
    print(f"Точное совпадение класса: {t2['exact_match']}/{t2['n']} ({t2['exact_match_pct']}%)")
    print(f"  ├ на ячейках, выведенных из расшифровок ЦБ независимо: "
          f"{t2['independent_match']}/{t2['n_independent']} ({t2['independent_match_pct']}%)")
    print(f"  └ на ячейках, калиброванных по ярлыкам (не независимо): "
          f"{t2['exact_match'] - t2['independent_match']}/{t2['n'] - t2['n_independent']}")
    print(f"\n{'дата':<12} {'модальность':<22} {'вектор':<7} {'предсказано':<18} {'ЦБ':<18} ok  незав.")
    for r in t2["rows"]:
        mark = "✓" if r["match"] else "·"
        ind = "да" if r["independent"] else "—"
        print(f"{r['date']:<12} {r['modality'] or '—':<22} {r['direction']:<7} "
              f"{r['predicted']:<18} {r['cbr_actual']:<18} {mark}   {ind}")

    print()
    print("=" * 72)
    print("ТЕСТ 3 · Предсказание следующего решения: индекс(t) → Δставки(t+1)")
    print("=" * 72)
    t3 = test3(feats, texts)
    print(f"n = {t3['n']} пар подряд идущих заседаний\n")
    a, b = t3["index_v2"], t3["dictionary_baseline"]
    print(f"{'метод':<34} {'ρ':>8} {'t':>8} {'p':>9}")
    print(f"{'морфосинтаксический индекс v2':<34} {a['spearman']:>8.3f} {a['t']:>8.2f} {a['p']:>9.4f}")
    print(f"{'словарь тональности (бенчмарк)':<34} {b['spearman']:>8.3f} {b['t']:>8.2f} {b['p']:>9.4f}")
    if "index_v2_2022plus" in t3:
        s = t3["index_v2_2022plus"]
        print(f"{'индекс v2, только 2022–2026':<34} {s['spearman']:>8.3f} {s['t']:>8.2f} {s['p']:>9.4f}   (n={s['n']})")

    OUT.write_text(json.dumps({"test1": t1, "test2": t2, "test3": t3},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
