"""Первый проход: паттерн-детектирование признаков forward-guidance в релизах ЦБ.

Не финальный анализ — скелет, который человек проверяет по 10 релизам.
Категории — из плана исследования:
  1) модальность сигнала (тип);
  2) направление (up/down/none);
  3) смягчители степени;
  4) условность (state-dependence).

Индекс hardness_v1 — арифметическая свёртка этих признаков; интерпретируется
не как «истинная тональность», а как отправная точка калибровки.

Вход:  data/processed/press.jsonl
Выход: data/processed/features.csv
"""

from __future__ import annotations

import csv
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "data" / "processed" / "press.jsonl"
OUT = ROOT / "data" / "processed" / "features.csv"


# ---------------------------------------------------------------------------
# Паттерны
# ---------------------------------------------------------------------------

# Индикаторы forward-guidance предложения — по ним ищем «сигнальный» sentence.
FG_ANCHORS = [
    r"Банк России будет ",
    r"Банк России продолжит ",
    r"Банк России допускает ",
    r"Банк России считает",
    r"Банк России оценивает",
    r"Банк России рассматривает",
    r"продолжит принимать",
    r"будет принимать дальнейшие",
    r"будет оценивать",
    r"требуется дальнейш",
    r"требуется более",
    r"на ближайших заседаниях",
    r"дальнейш\w+ решени",
]

# Модальность (порядок = приоритет: сначала более специфичные шаблоны).
MOD_PATTERNS: list[tuple[str, str]] = [
    ("conditional_evaluation", r"будет\s+оценивать|будет\s+рассматривать|будет\s+анализировать|оцен\w+\s+целесообразност"),
    ("possibility_speaker", r"допускает(?:ся)?\s+возможност|не\s+исключает|может\s+(?:потребовать|повысить|снизить|сохранить|продолжить)"),
    ("necessity_impersonal", r"\bтребуется\b|\bнеобходимо\b|\bпотребуется\b|\bпонадобит(?:ся|ься)\b|\bследует\b"),
    ("unconditional_commitment", r"продолжит\s+поддержив|сохранит\s+(?:жестк|высок)|обеспечит\b"),
    ("intention", r"Банк\s+России\s+будет\b|Банк\s+России\s+продолжит\b|намерен\b"),
]

# Направление, названное в сигнале
DIR_UP = re.compile(
    r"\b(ужесточ\w*|повышени\w*|повыси(?:ть|л|т|м)\w*|повышать|более\s+жестк\w+|поддержани\w+\s+жестк)",
    re.I,
)
DIR_DOWN = re.compile(
    r"\b(снижени\w*|снизит\w*|снижать|смягчени\w*|смягчи(?:ть|л|т)\w*|смягчать)",
    re.I,
)

# Смягчители степени и условности
HEDGES = re.compile(
    r"\b(плавн\w+|постепенн\w+|умеренн\w+|аккуратн\w+|более\s+плавн|в\s+меньшей\s+степени)",
    re.I,
)

# State-dependence
CONDITIONS = re.compile(
    r"в\s+зависимости\s+от|с\s+учет(?:ом|а)\s+|в\s+случае\s+|если\s+будут|при\s+условии"
    r"|при\s+развитии\s+ситуации|при\s+сохранени\w+|при\s+реализаци\w+"
    r"|в\s+соответствии\s+с\s+базов\w+\s+прогноз|в\s+базовом\s+сценари|исходя\s+из\s+оценк",
    re.I,
)


# ---------------------------------------------------------------------------
# Логика
# ---------------------------------------------------------------------------


@dataclass
class Features:
    date: str
    direction_actual: str        # up/down/hold (из decisions.csv)
    delta_bp: int
    signal_sentence: str
    modality: str                # первая сработавшая категория; "" если нет
    modality_all: str            # все сработавшие через |
    direction_signal: str        # up/down/none/mixed
    hedge_count: int
    hedges_found: str
    has_conditionality: int
    conditions_found: str
    hardness_v1: float           # свёртка (см. compute_hardness)
    n_words: int


def find_signal(text: str) -> tuple[str, str]:
    """Возвращает (core, context) — само предложение с якорем и оно+следующее.

    Направление и модальность определяются по CORE (там, где именно сигнал);
    условия ищем на CONTEXT — они часто в следующем предложении.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for i, s in enumerate(sentences):
        for anchor in FG_ANCHORS:
            if re.search(anchor, s):
                tail = sentences[i + 1] if i + 1 < len(sentences) else ""
                return s.strip(), (s + " " + tail).strip()
    return "", ""


def classify(rec: dict) -> Features:
    text = rec["text"]
    core, context = find_signal(text)
    if not core:
        core = context = rec.get("signal_sentence", "")

    mods = [name for name, pat in MOD_PATTERNS if re.search(pat, core, re.I)]
    modality = mods[0] if mods else ""

    dirs: list[str] = []
    if DIR_UP.search(core):
        dirs.append("up")
    if DIR_DOWN.search(core):
        dirs.append("down")
    if not dirs:
        direction_signal = "none"
    elif len(dirs) == 2:
        direction_signal = "mixed"
    else:
        direction_signal = dirs[0]

    hedges = HEDGES.findall(core)
    conditions = CONDITIONS.findall(context)  # условия — на широком контексте
    sig = context

    return Features(
        date=rec["date"],
        direction_actual=rec.get("direction", "") or "",
        delta_bp=int(rec.get("delta_bp") or 0),
        signal_sentence=sig,
        modality=modality,
        modality_all="|".join(mods),
        direction_signal=direction_signal,
        hedge_count=len(hedges),
        hedges_found="|".join(hedges),
        has_conditionality=1 if conditions else 0,
        conditions_found="|".join(str(c) for c in conditions),
        hardness_v1=compute_hardness(direction_signal, modality, len(hedges), bool(conditions)),
        n_words=int(rec.get("n_words") or 0),
    )


def compute_hardness(direction: str, modality: str, hedges: int, conditional: bool) -> float:
    """Индекс от −1 (мягко) до +1 (жёстко). Первое приближение, будет калиброваться.

    Свёртка = знак(направление) × вес(модальности) × штраф(смягчители) × штраф(условие).
    """
    dir_score = {"up": 1.0, "down": -1.0, "mixed": 0.0, "none": 0.0}[direction]
    mod_weight = {
        "unconditional_commitment": 1.00,
        "necessity_impersonal": 0.85,
        "possibility_speaker": 0.60,
        "intention": 0.50,
        "conditional_evaluation": 0.30,
        "": 0.20,
    }.get(modality, 0.20)
    hedge_penalty = max(0.0, 1.0 - 0.15 * hedges)
    cond_penalty = 0.6 if conditional else 1.0
    return round(dir_score * mod_weight * hedge_penalty * cond_penalty, 3)


def main() -> int:
    with IN.open(encoding="utf-8") as f:
        records = [json.loads(l) for l in f if l.strip()]

    feats = [classify(r) for r in records]

    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(feats[0]).keys()))
        w.writeheader()
        for x in feats:
            w.writerow(asdict(x))

    # мини-сводка в стдаут
    from collections import Counter
    print(f"features: {len(feats)}")
    print("модальность:", Counter(f.modality for f in feats))
    print("направление (сигнал):", Counter(f.direction_signal for f in feats))
    print("условности:", sum(f.has_conditionality for f in feats))
    print("среднее hardness:", round(sum(f.hardness_v1 for f in feats) / len(feats), 3))
    # покажем 4 контрольных сравнения
    key = {"2024-10-25", "2026-07-24", "2022-02-28", "2022-04-08", "2021-07-23", "2026-04-24"}
    print("\nконтрольные точки:")
    for f in feats:
        if f.date in key:
            print(f"  {f.date}  dir={f.direction_signal:5s}  mod={f.modality:24s}  hedges={f.hedge_count}  cond={f.has_conditionality}  hardness={f.hardness_v1:+.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
