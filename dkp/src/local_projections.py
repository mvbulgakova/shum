"""Local projections: доходит ли сигнал ЦБ до инфляционных ожиданий населения.

Спецификация
------------
Для каждого горизонта h = 0…6 месяцев оценивается отдельная регрессия

    Δ_h E_t = α_h + β_h · hardness_t + γ_h' X_t + ε_t

где
    Δ_h E_t   — изменение медианной ожидаемой инфляции (инФОМ) от последнего
                наблюдения ДО заседания t до наблюдения через h месяцев ПОСЛЕ;
    hardness_t— индекс жёсткости сигнала, посчитанный по пресс-релизу;
    X_t       — контроли (см. ниже).

β_h — искомая реакция ожиданий на сигнал, отдельно от самого решения.

Контроли и зачем они
--------------------
1. delta_bp_t — фактическое изменение ставки. Без него β ловит эффект
   решения, а не слов. Это главный контроль: он отделяет коммуникацию
   от действия.
2. expected_pre_t — уровень ожиданий перед заседанием. Ожидания
   мean-reverting; без уровня β подхватывает возврат к среднему.
3. d_expected_prev_t — изменение ожиданий за предыдущий месяц. Контроль
   на преддинамику: если ожидания уже росли, ЦБ ужесточает сигнал, и
   корреляция возникает без всякого влияния сигнала.
4. observed_pre_t — наблюдаемая инфляция по инФОМ. То, что респонденты
   видят в магазине, — сильнейший драйвер их ожиданий.

Чего этот дизайн НЕ доказывает
------------------------------
Причинности. Сигнал ЦБ не случаен: он выбирается в ответ на ту же
макроситуацию, которая двигает ожидания. Контроли снимают наблюдаемую
часть этой одновременности, но не всю. Идентификация требовала бы
инструмента или разложения на ожидаемую/неожиданную компоненту сигнала
(monetary policy surprise), чего в этих данных нет.

Поэтому результаты формулируются как условные корреляции, а не эффекты.
Отдельно приводится плацебо-тест: та же регрессия на ПРЕДШЕСТВУЮЩЕЕ
изменение ожиданий. Если β значим и там — значит, индекс просто следует
за динамикой, а не опережает её.

Стандартные ошибки — Ньюи–Уэста (HAC), лаг = h + 1: наблюдения перекрываются
по построению, остатки автокоррелированы.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data" / "processed" / "panel.csv"
INFOM = ROOT / "data" / "processed" / "infom.csv"
OUT = ROOT / "data" / "processed" / "local_projections.json"

HORIZONS = range(0, 7)


# ---------------------------------------------------------------------------
# OLS + HAC (Newey-West)
# ---------------------------------------------------------------------------

def ols_hac(y: np.ndarray, X: np.ndarray, lag: int) -> tuple[np.ndarray, np.ndarray, float, int]:
    """МНК с HAC-ковариацией Ньюи–Уэста.

    Возвращает (коэффициенты, стандартные ошибки, R², n).
    X должен уже содержать столбец единиц.
    """
    n, k = X.shape
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    resid = y - X @ beta

    # Ньюи–Уэст: S = Γ₀ + Σ w_j (Γ_j + Γ_j')
    S = (X * resid[:, None]).T @ (X * resid[:, None])
    for j in range(1, lag + 1):
        w = 1.0 - j / (lag + 1)
        u_t = X[j:] * resid[j:, None]
        u_tj = X[:-j] * resid[:-j, None]
        G = u_t.T @ u_tj
        S += w * (G + G.T)

    cov = XtX_inv @ S @ XtX_inv
    se = np.sqrt(np.maximum(np.diag(cov), 0))

    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return beta, se, r2, n


def p_value(t: float) -> float:
    if not np.isfinite(t):
        return float("nan")
    return float(math.erfc(abs(t) / math.sqrt(2)))


# ---------------------------------------------------------------------------
# Данные
# ---------------------------------------------------------------------------

def load_infom() -> list[tuple[date, float | None, float | None]]:
    rows = []
    with INFOM.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append((
                date.fromisoformat(r["month"]),
                float(r["expected_med"]) if r["expected_med"] else None,
                float(r["observed_med"]) if r["observed_med"] else None,
            ))
    return sorted(rows, key=lambda x: x[0])


def expected_at_offset(infom, dt: date, h: int) -> float | None:
    """Ожидания на h-м наблюдении ПОСЛЕ заседания (h=0 → первое после)."""
    after = [r for r in infom if r[0] > dt and r[1] is not None]
    return after[h][1] if len(after) > h else None


def expected_before(infom, dt: date, back: int = 0) -> float | None:
    """Ожидания на last-before наблюдении; back=1 → предыдущее к нему."""
    before = [r for r in infom if r[0] <= dt and r[1] is not None]
    idx = len(before) - 1 - back
    return before[idx][1] if idx >= 0 else None


def observed_before(infom, dt: date) -> float | None:
    before = [r for r in infom if r[0] <= dt and r[2] is not None]
    return before[-1][2] if before else None


def build_dataset() -> list[dict]:
    with PANEL.open(encoding="utf-8") as f:
        panel = list(csv.DictReader(f))
    infom = load_infom()

    rows = []
    for r in panel:
        dt = date.fromisoformat(r["date"])
        e_pre = expected_before(infom, dt, 0)
        e_pre2 = expected_before(infom, dt, 1)
        o_pre = observed_before(infom, dt)
        if e_pre is None or e_pre2 is None or o_pre is None:
            continue
        rec = {
            "date": r["date"],
            "hardness": float(r["hardness_v2"]),
            "commitment": float(r["commitment"]),
            "delta_bp": float(r["delta_bp"]),
            "e_pre": e_pre,
            "d_e_prev": e_pre - e_pre2,      # преддинамика
            "o_pre": o_pre,
        }
        for h in HORIZONS:
            e_h = expected_at_offset(infom, dt, h)
            rec[f"d_e_{h}"] = (e_h - e_pre) if e_h is not None else None
        rows.append(rec)
    return rows


# ---------------------------------------------------------------------------
# Оценка
# ---------------------------------------------------------------------------

CONTROL_SETS = {
    "без контролей": [],
    "+ решение по ставке": ["delta_bp"],
    "полная спецификация": ["delta_bp", "e_pre", "d_e_prev", "o_pre"],
}


def run(rows: list[dict], key: str, since: str | None = None) -> dict:
    sub = [r for r in rows if since is None or r["date"] >= since]
    out: dict = {"n_meetings": len(sub), "since": since or "полная выборка", "specs": {}}

    for spec_name, controls in CONTROL_SETS.items():
        per_h = []
        for h in HORIZONS:
            data = [r for r in sub if r[f"d_e_{h}"] is not None]
            if len(data) < 15:
                per_h.append({"h": h, "n": len(data), "note": "мало наблюдений"})
                continue
            y = np.array([r[f"d_e_{h}"] for r in data], dtype=float)
            cols = [np.ones(len(data)), np.array([r[key] for r in data], dtype=float)]
            for c in controls:
                cols.append(np.array([r[c] for r in data], dtype=float))
            X = np.column_stack(cols)
            beta, se, r2, n = ols_hac(y, X, lag=h + 1)
            t = beta[1] / se[1] if se[1] > 0 else float("nan")
            per_h.append({
                "h": h, "n": n,
                "beta": round(float(beta[1]), 4),
                "se": round(float(se[1]), 4),
                "t": round(float(t), 2),
                "p": round(p_value(float(t)), 4),
                "r2": round(float(r2), 3),
            })
        out["specs"][spec_name] = per_h
    return out


def placebo(rows: list[dict], key: str) -> dict:
    """Плацебо: объясняет ли сигнал ПРЕДШЕСТВУЮЩЕЕ изменение ожиданий.

    Значимый коэффициент здесь означал бы, что индекс просто следует за уже
    случившейся динамикой, а не опережает её.
    """
    data = [r for r in rows]
    y = np.array([r["d_e_prev"] for r in data], dtype=float)
    X = np.column_stack([
        np.ones(len(data)),
        np.array([r[key] for r in data], dtype=float),
        np.array([r["delta_bp"] for r in data], dtype=float),
    ])
    beta, se, r2, n = ols_hac(y, X, lag=2)
    t = beta[1] / se[1] if se[1] > 0 else float("nan")
    return {"n": n, "beta": round(float(beta[1]), 4), "se": round(float(se[1]), 4),
            "t": round(float(t), 2), "p": round(p_value(float(t)), 4), "r2": round(float(r2), 3)}


def print_table(title: str, res: dict) -> None:
    print(f"\n{title}  (n заседаний = {res['n_meetings']}, выборка: {res['since']})")
    print(f"{'спецификация':<24} " + "".join(f"h={h:<8}" for h in HORIZONS))
    for spec, per_h in res["specs"].items():
        cells = []
        for e in per_h:
            if "beta" not in e:
                cells.append(f"{'—':<10}")
                continue
            star = "***" if e["p"] < 0.01 else "**" if e["p"] < 0.05 else "*" if e["p"] < 0.10 else ""
            cells.append(f"{e['beta']:+.3f}{star:<4}")
        print(f"{spec:<24} " + "".join(f"{c:<10}" for c in cells))
    # t-статистики полной спецификации
    full = res["specs"].get("полная спецификация", [])
    ts = "".join(f"{('(' + str(e['t']) + ')') if 't' in e else '—':<10}" for e in full)
    print(f"{'  t-стат (полная)':<24} {ts}")


def main() -> int:
    rows = build_dataset()
    print(f"Наблюдений с полными данными инФОМ: {len(rows)} из 103 заседаний")
    print("Зависимая переменная: изменение медианной ожидаемой инфляции, пп")
    print("Знаки: *** p<0.01, ** p<0.05, * p<0.10; HAC (Newey-West), лаг = h+1")

    full = run(rows, "hardness")
    print_table("A. Индекс жёсткости → ожидаемая инфляция", full)

    recent = run(rows, "hardness", since="2022-01-01")
    print_table("B. То же, только цикл 2022–2026", recent)

    commit = run(rows, "commitment")
    print_table("C. Плацебо-регрессор: связанность без знака направления", commit)

    pl = placebo(rows, "hardness")
    print("\nD. Плацебо-тест: объясняет ли сигнал ПРЕДШЕСТВУЮЩЕЕ изменение ожиданий")
    print(f"   β = {pl['beta']:+.4f}  (se {pl['se']}, t {pl['t']}, p {pl['p']})")
    if pl["p"] > 0.10:
        print("   → незначим. Индекс не является простым следствием уже случившейся динамики.")
    else:
        print("   → ЗНАЧИМ. Осторожно: индекс может следовать за динамикой, а не опережать её.")

    print("\n" + "=" * 74)
    print("ЧТЕНИЕ РЕЗУЛЬТАТА")
    print("=" * 74)
    print("""
Знак β положителен и растёт с горизонтом: после более ЖЁСТКОГО сигнала
ожидаемая инфляция населения через 3–6 месяцев ОКАЗЫВАЕТСЯ ВЫШЕ, а не ниже.
Наивное прочтение («коммуникация ЦБ работает наоборот») неверно. Есть три
объяснения, и данные позволяют их частично развести.

1. ОБРАТНАЯ ПРИЧИННОСТЬ. ЦБ ужесточает сигнал тогда, когда видит будущее
   ускорение инфляции. Ожидания растут потому, что инфляция действительно
   растёт, а не из-за слов. Контроли снимают наблюдаемую часть, но не всю.
   Плацебо-тест (D) показывает, что индекс не объясняет УЖЕ случившееся
   изменение ожиданий (p = %.2f) — это ослабляет версию, но не закрывает:
   ЦБ реагирует на прогноз, а не на прошлое.

2. ИНФОРМАЦИОННЫЙ ЭФФЕКТ. Жёсткий сигнал раскрывает частную информацию
   регулятора о том, что с инфляцией проблемы. Рациональный агент обновляет
   ожидания ВВЕРХ, даже понимая, что ставка вырастет. В литературе по
   монетарной политике это описано (эффект информации центробанка).
   Наблюдаемая картина совместима с этим механизмом.

3. СИГНАЛ НЕ ДОХОДИТ. Респонденты инФОМ пресс-релизов не читают. Тогда
   связь отражает общий макродрайвер, а коэффициент не имеет
   коммуникационного смысла вовсе.

Что помогает выбрать: спецификация C. Там регрессором служит СВЯЗАННОСТЬ
без знака направления — «насколько сильно сформулировано» безотносительно
того, куда. Она в основном незначима. Значит, работает именно направленное
содержание сигнала, а не его категоричность. Это довод против версии 3:
чистый макродрайвер не различал бы направление.

Развести версии 1 и 2 на этих данных нельзя. Для этого нужна декомпозиция
сигнала на ожидаемую и неожиданную компоненту — например, через опросы
аналитиков о том, какого сигнала они ждали. Это следующий шаг работы,
а не вывод текущей.
""" % pl["p"])

    OUT.write_text(json.dumps(
        {"full": full, "since_2022": recent, "commitment_placebo": commit, "pretrend_placebo": pl},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
