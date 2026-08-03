"""Собирает единую панель для анализа: решение × сигнал × инФОМ.

Логика привязки инФОМ к заседанию:
- pre  — последнее наблюдение инФОМ *до* заседания (то, что видел ЦБ).
- post — первое наблюдение инФОМ *после* заседания (реакция).
- delta = post − pre  (сдвиг ожиданий вокруг решения).

На выходе: data/processed/panel.csv, по одной строке на решение.
"""

from __future__ import annotations

import csv
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEATS = ROOT / "data" / "processed" / "features.csv"
INFOM = ROOT / "data" / "processed" / "infom.csv"
OUT = ROOT / "data" / "processed" / "panel.csv"


def load_infom() -> list[dict]:
    with INFOM.open(encoding="utf-8") as f:
        rows = []
        for r in csv.DictReader(f):
            def num(x): return float(x) if x else None
            rows.append({
                "month": date.fromisoformat(r["month"]),
                "observed": num(r["observed_med"]),
                "expected": num(r["expected_med"]),
                "expected_5y": num(r["expected_5y_med"]),
            })
    return sorted(rows, key=lambda r: r["month"])


def pick_nearest(infom: list[dict], dt: date, side: str, key: str) -> tuple[date | None, float | None]:
    """side='pre': последнее <= dt; side='post': первое > dt."""
    if side == "pre":
        cands = [r for r in infom if r["month"] <= dt and r[key] is not None]
        cands.sort(key=lambda r: r["month"])
        return (cands[-1]["month"], cands[-1][key]) if cands else (None, None)
    else:
        cands = [r for r in infom if r["month"] > dt and r[key] is not None]
        cands.sort(key=lambda r: r["month"])
        return (cands[0]["month"], cands[0][key]) if cands else (None, None)


def main() -> int:
    with FEATS.open(encoding="utf-8") as f:
        feats = list(csv.DictReader(f))
    infom = load_infom()

    out_rows = []
    for r in feats:
        dt = date.fromisoformat(r["date"])
        pre_m, pre_v = pick_nearest(infom, dt, "pre", "expected")
        post_m, post_v = pick_nearest(infom, dt, "post", "expected")
        obs_pre_m, obs_pre_v = pick_nearest(infom, dt, "pre", "observed")

        delta_exp = None
        if pre_v is not None and post_v is not None:
            delta_exp = round(post_v - pre_v, 3)

        out_rows.append({
            "date": r["date"],
            "rate_new": float(r["delta_bp"]) / 100 + None if False else "",  # placeholder
            "delta_bp": int(r["delta_bp"]),
            "direction_actual": r["direction_actual"],
            "modality": r["modality"],
            "direction_signal": r["direction_signal"],
            "hedge_count": int(r["hedge_count"]),
            "has_conditionality": int(r["has_conditionality"]),
            "hardness_v1": float(r["hardness_v1"]),
            "n_words": int(r["n_words"]),
            "infom_pre_month": pre_m.isoformat() if pre_m else "",
            "infom_expected_pre": pre_v if pre_v is not None else "",
            "infom_post_month": post_m.isoformat() if post_m else "",
            "infom_expected_post": post_v if post_v is not None else "",
            "infom_expected_delta": delta_exp if delta_exp is not None else "",
            "infom_observed_pre": obs_pre_v if obs_pre_v is not None else "",
        })

    # Уберём мусорный placeholder — просто напишем reasonable order.
    fieldnames = [
        "date", "delta_bp", "direction_actual",
        "modality", "direction_signal", "hedge_count", "has_conditionality",
        "hardness_v1", "n_words",
        "infom_pre_month", "infom_expected_pre",
        "infom_post_month", "infom_expected_post",
        "infom_expected_delta", "infom_observed_pre",
    ]
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)

    n = len(out_rows)
    filled_delta = sum(1 for r in out_rows if r["infom_expected_delta"] != "")
    print(f"panel: {n} строк; delta ожиданий вычислен для {filled_delta} решений")

    # квик-стата: средний delta ожиданий по знаку сигнала (пилотный «действует ли»)
    from collections import defaultdict
    buckets: dict[str, list[float]] = defaultdict(list)
    for r in out_rows:
        if r["infom_expected_delta"] == "":
            continue
        sign = ("hawkish" if r["hardness_v1"] > 0.15
                else "dovish" if r["hardness_v1"] < -0.15
                else "neutral")
        buckets[sign].append(float(r["infom_expected_delta"]))
    print("\nсредний Δ ожидаемой инфляции (после − до), по знаку сигнала:")
    for label in ("hawkish", "neutral", "dovish"):
        vs = buckets.get(label, [])
        if vs:
            print(f"  {label:>8s}: n={len(vs):>3}  mean={sum(vs)/len(vs):+.3f} пп")
    return 0


if __name__ == "__main__":
    sys.exit(main())
