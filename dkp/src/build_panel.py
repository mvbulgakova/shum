"""Собирает единую панель для анализа: решение × сигнал × ярлык ЦБ × инФОМ.

Логика привязки инФОМ к заседанию:
- pre  — последнее наблюдение инФОМ *до* заседания (то, что видел ЦБ).
- post — первое наблюдение инФОМ *после* заседания (реакция).
- delta = post − pre  (сдвиг ожиданий вокруг решения).

Ярлык сигнала ЦБ (из резюме обсуждения) добавляется там, где доступен — то
есть с февраля 2024. Для более ранних заседаний поле пустое.

На выходе: data/processed/panel.csv, по одной строке на решение.
"""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEATS = ROOT / "data" / "processed" / "features_v2.csv"
LABELS = ROOT / "data" / "processed" / "signal_labels.csv"
SUMMF = ROOT / "data" / "processed" / "summary_features.csv"
INFOM = ROOT / "data" / "processed" / "infom.csv"
DECS = ROOT / "data" / "reference" / "decisions.csv"
OUT = ROOT / "data" / "processed" / "panel.csv"


def load_infom() -> list[dict]:
    rows = []
    with INFOM.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            def num(x):
                return float(x) if x else None
            rows.append({
                "month": date.fromisoformat(r["month"]),
                "observed": num(r["observed_med"]),
                "expected": num(r["expected_med"]),
                "expected_5y": num(r["expected_5y_med"]),
            })
    return sorted(rows, key=lambda r: r["month"])


def pick(infom: list[dict], dt: date, side: str, key: str) -> tuple[date | None, float | None]:
    """side='pre': последнее <= dt; side='post': первое > dt."""
    if side == "pre":
        c = [r for r in infom if r["month"] <= dt and r[key] is not None]
        return (c[-1]["month"], c[-1][key]) if c else (None, None)
    c = [r for r in infom if r["month"] > dt and r[key] is not None]
    return (c[0]["month"], c[0][key]) if c else (None, None)


FIELDS = [
    "date", "rate_new", "delta_bp", "direction_actual",
    "modality", "direction_signal", "level_stance", "direction_withheld",
    "agent_explicit", "impersonal", "passive",
    "hedge_count", "cond_count", "nominalization_ratio",
    "commitment", "hardness_v2", "stance",
    "cbr_label", "cbr_label_score", "cbr_labels_discussed",
    "summary_words", "summary_dissent_per_1k",
    "infom_pre_month", "infom_expected_pre",
    "infom_post_month", "infom_expected_post",
    "infom_expected_delta", "infom_observed_pre",
    "n_words",
]


def main() -> int:
    with FEATS.open(encoding="utf-8") as f:
        feats = list(csv.DictReader(f))
    with LABELS.open(encoding="utf-8") as f:
        labels = {r["decision_date"]: r for r in csv.DictReader(f)}
    with SUMMF.open(encoding="utf-8") as f:
        summf = {r["decision_date"]: r for r in csv.DictReader(f)}
    with DECS.open(encoding="utf-8") as f:
        decs = {r["date"]: r for r in csv.DictReader(f)}
    infom = load_infom()

    out = []
    for r in feats:
        dt = date.fromisoformat(r["date"])
        pre_m, pre_v = pick(infom, dt, "pre", "expected")
        post_m, post_v = pick(infom, dt, "post", "expected")
        _, obs_pre = pick(infom, dt, "pre", "observed")
        lab = labels.get(r["date"], {})
        sm = summf.get(r["date"], {})

        out.append({
            "date": r["date"],
            "rate_new": decs.get(r["date"], {}).get("rate_new", ""),
            "delta_bp": int(r["delta_bp"]),
            "direction_actual": r["direction_actual"],
            "modality": r["modality"],
            "direction_signal": r["direction_signal"],
            "level_stance": r["level_stance"],
            "direction_withheld": r["direction_withheld"],
            "agent_explicit": r["agent_explicit"],
            "impersonal": r["impersonal"],
            "passive": r["passive"],
            "hedge_count": r["hedge_count"],
            "cond_count": r["cond_count"],
            "nominalization_ratio": r["nominalization_ratio"],
            "commitment": r["commitment"],
            "hardness_v2": r["hardness_v2"],
            "stance": r["stance"],
            "cbr_label": lab.get("label_chosen", ""),
            "cbr_label_score": lab.get("label_score", ""),
            "cbr_labels_discussed": lab.get("labels_discussed", ""),
            "summary_words": sm.get("n_words", ""),
            "summary_dissent_per_1k": sm.get("dissent_per_1k", ""),
            "infom_pre_month": pre_m.isoformat() if pre_m else "",
            "infom_expected_pre": pre_v if pre_v is not None else "",
            "infom_post_month": post_m.isoformat() if post_m else "",
            "infom_expected_post": post_v if post_v is not None else "",
            "infom_expected_delta": round(post_v - pre_v, 3)
            if (pre_v is not None and post_v is not None) else "",
            "infom_observed_pre": obs_pre if obs_pre is not None else "",
            "n_words": r["n_words"],
        })

    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out)

    n = len(out)
    with_lab = sum(1 for r in out if r["cbr_label"])
    print(f"panel: {n} решений; ярлык ЦБ доступен для {with_lab}")

    from collections import defaultdict
    buckets: dict[str, list[float]] = defaultdict(list)
    for r in out:
        if r["infom_expected_delta"] == "":
            continue
        h = float(r["hardness_v2"])
        key = "hawkish" if h > 0.12 else "dovish" if h < -0.12 else "neutral"
        buckets[key].append(float(r["infom_expected_delta"]))
    print("\nсредний Δ ожидаемой инфляции (месяц после − месяц до), по знаку сигнала:")
    for k in ("hawkish", "neutral", "dovish"):
        v = buckets.get(k, [])
        if v:
            print(f"  {k:>8s}: n={len(v):>3}  mean={sum(v)/len(v):+.3f} пп")
    return 0


if __name__ == "__main__":
    sys.exit(main())
