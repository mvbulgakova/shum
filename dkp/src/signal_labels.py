"""Извлечение СОБСТВЕННОЙ таксономии сигнала Банка России из резюме обсуждения.

Зачем
-----
Главная методологическая проблема любого индекса тональности — произвольность
шкалы. Жюри справедливо спросит: «почему „допускает возможность“ у вас жёстче,
чем „оценит целесообразность“? Вы сами так решили?»

Ответ обнаруживается в резюме обсуждения. Банк России в них явно называет
градацию собственного сигнала и расшифровывает, какая формулировка какой
ступени соответствует:

  2024-10-25: «Обсуждалось два варианта сигнала: жесткий (допускает
              возможность повышения) и умеренно жесткий (оценит
              целесообразность повышения)»
  2025-07-25: «Рассматривалось два варианта сигнала: умеренно мягкий сигнал
              (об оценке целесообразности снижения ключевой ставки) и
              нейтральный сигнал (без указания на направленность)»

То есть шкала не сконструирована исследователем — она реконструирована из
внутренней практики регулятора. Порядок ступеней:

    жёсткий > умеренно жёсткий > нейтральный > умеренно мягкий > мягкий

Это даёт внешний критерий валидности (construct validity): индекс, посчитанный
по ПРЕСС-РЕЛИЗУ, проверяется против ярлыка, названного в РЕЗЮМЕ — другом
документе, опубликованном на шесть рабочих дней позже. Проверка не круговая.

Ограничение выборки: резюме существуют с февраля 2024, поэтому ярлыки
доступны только для 20 заседаний. Для остальных 83 индекс остаётся
неваллидированным напрямую — это надо оговаривать.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMM = ROOT / "data" / "processed" / "summaries.jsonl"
OUT = ROOT / "data" / "processed" / "signal_labels.csv"


# Порядковая шкала ЦБ. Значение — позиция на оси жёсткости.
LABEL_SCALE: dict[str, float] = {
    "жесткий": 1.0,
    "умеренно жесткий": 0.5,
    "нейтральный": 0.0,
    "умеренно мягкий": -0.5,
    "мягкий": -1.0,
}


def _norm_label(raw: str) -> str:
    """Нормализует написание: ё/е, лишние пробелы, род/падеж."""
    s = raw.lower().replace("ё", "е")
    s = re.sub(r"\s+", " ", s).strip()
    # отсекаем окончания прилагательных: жесткого/жесткому/жестким → жесткий
    s = re.sub(r"жестк\w+", "жесткий", s)
    s = re.sub(r"мягк\w+", "мягкий", s)
    s = re.sub(r"нейтральн\w+", "нейтральный", s)
    s = re.sub(r"умеренно\s+", "умеренно ", s)
    return s


# Итоговый раздел резюме: «По итогам дискуссии Совет директоров … [решение].
# [характеристика сигнала]». Ярлык часто не назван словом, а описан.
OUTCOME_BLOCK = re.compile(
    r"По\s+итогам\s+(?:состоявшейся\s+)?дискуссии.{0,2500}", re.I | re.S
)

# Описательные характеристики сигнала в итоговом блоке, если ярлык не назван.
# Ключи — те же формулировки, которые ЦБ сам приводит как расшифровки.
OUTCOME_GLOSS_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"допускает\s+возможность\s+повышени|"
                r"направленный\s+сигнал\s+о\s+возможном\s+повышении|"
                r"сигнал\s+о\s+возможности\s+(?:ее\s+|её\s+)?повышени", re.I), "жесткий"),
    (re.compile(r"оцен\w+\s+целесообразност\w*\s+(?:дальнейшего\s+)?повышени", re.I),
     "умеренно жесткий"),
    (re.compile(r"допускает\s+возможность\s+снижени", re.I), "мягкий"),
    (re.compile(r"оцен\w+\s+целесообразност\w*\s+(?:дальнейшего\s+)?снижени", re.I),
     "умеренно мягкий"),
    (re.compile(r"будут\s+приниматься\s+в\s+зависимости\s+от|"
                r"без\s+указания\s+на\s+направленность", re.I), "нейтральный"),
]

# Ярлык, который в итоге ВЫБРАН (а не просто обсуждался).
CHOSEN_PATTERNS = [
    # «участники согласились сохранить нейтральный сигнал»
    re.compile(r"(?:согласились|единодушны|сошлись)[^.]{0,80}?"
               r"(умеренно\s+жестк\w+|умеренно\s+мягк\w+|нейтральн\w+|жестк\w+|мягк\w+)\s+сигнал", re.I),
    # «Совет директоров посчитал оправданным ... сигнал»
    re.compile(r"Совет\s+директоров[^.]{0,120}?"
               r"(умеренно\s+жестк\w+|умеренно\s+мягк\w+|нейтральн\w+|жестк\w+|мягк\w+)\s+сигнал", re.I),
    # «большинство участников высказались за умеренно жесткий сигнал»
    re.compile(r"большинство[^.]{0,80}?"
               r"(умеренно\s+жестк\w+|умеренно\s+мягк\w+|нейтральн\w+|жестк\w+|мягк\w+)\s+сигнал", re.I),
    # «необходимо сохранить нейтральный сигнал»
    re.compile(r"(?:необходимо|решили|выбрали)\s+сохранить\s+"
               r"(умеренно\s+жестк\w+|умеренно\s+мягк\w+|нейтральн\w+|жестк\w+|мягк\w+)\s+сигнал", re.I),
]

# Все ярлыки, которые ОБСУЖДАЛИСЬ (мера разброса мнений в Совете).
DISCUSSED_PATTERN = re.compile(
    r"(умеренно\s+жестк\w+|умеренно\s+мягк\w+|нейтральн\w+|жестк\w+|мягк\w+)\s+сигнал",
    re.I,
)

# Блок, где перечисляются варианты сигнала.
OPTIONS_BLOCK = re.compile(
    r"(?:обсужда\w+|рассматрива\w+)\s+(?:два|три|несколько|два)\s+вариант\w*\s+сигнала"
    r"|вариант\w*\s+(?:направленного\s+)?сигнала",
    re.I,
)

# Расшифровка: «жесткий (допускает возможность повышения)» — ярлык + формулировка.
GLOSS = re.compile(
    r"(умеренно\s+жестк\w+|умеренно\s+мягк\w+|нейтральн\w+|жестк\w+|мягк\w+)\s*"
    r"(?:сигнал\w*\s*)?\(([^)]{10,160})\)",
    re.I,
)

# Обсуждавшиеся уровни ставки — мера разброса по самому решению.
RATE_DEBATE = re.compile(
    r"(?:выступили\s+за|предложени\w+\s+о|высказыва\w+\s+за)[^.]{0,160}?(\d{1,2},\d{2})\s*%",
    re.I,
)


def extract(text: str) -> dict:
    # --- выбранный ярлык: сначала прямое называние ---
    chosen, chosen_src = "", ""
    for pat in CHOSEN_PATTERNS:
        m = pat.search(text)
        if m:
            chosen = _norm_label(m.group(1))
            chosen_src = "explicit"
            break

    # --- если ярлык не назван словом, определяем по описанию в итоговом блоке,
    #     используя расшифровки, которые ЦБ дал сам ---
    if chosen not in LABEL_SCALE:
        blk = OUTCOME_BLOCK.search(text)
        window = blk.group(0) if blk else text[-2500:]
        for pat, label in OUTCOME_GLOSS_MAP:
            if pat.search(window):
                chosen, chosen_src = label, "gloss"
                break

    # --- все обсуждавшиеся ярлыки ---
    discussed = []
    blk = OPTIONS_BLOCK.search(text)
    if blk:
        window = text[blk.start(): blk.start() + 900]
        discussed = [_norm_label(x) for x in DISCUSSED_PATTERN.findall(window)]
    if not discussed:
        discussed = [_norm_label(x) for x in DISCUSSED_PATTERN.findall(text)]
    # уникальные, с сохранением порядка
    seen, uniq = set(), []
    for d in discussed:
        if d in LABEL_SCALE and d not in seen:
            seen.add(d)
            uniq.append(d)

    # --- расшифровки формулировок ---
    glosses = []
    for label, gloss in GLOSS.findall(text):
        lab = _norm_label(label)
        if lab in LABEL_SCALE:
            clean = re.sub(r"\s+", " ", gloss).strip()
            glosses.append(f"{lab} = {clean}")

    # --- обсуждавшиеся уровни ставки ---
    rates = sorted(set(RATE_DEBATE.findall(text)))

    return {
        "label_chosen": chosen if chosen in LABEL_SCALE else "",
        "label_source": chosen_src if chosen in LABEL_SCALE else "",
        "label_score": LABEL_SCALE.get(chosen, ""),
        "labels_discussed": "|".join(uniq),
        "n_labels_discussed": len(uniq),
        "glosses": " ;; ".join(dict.fromkeys(glosses)),
        "rates_discussed": "|".join(rates),
        "n_rates_discussed": len(rates),
    }


def main() -> int:
    with SUMM.open(encoding="utf-8") as f:
        rows = sorted(
            (json.loads(l) for l in f if l.strip()),
            key=lambda x: x["decision_date"],
        )

    out = []
    for r in rows:
        rec = {"decision_date": r["decision_date"], "pub_date": r["pub_date"]}
        rec.update(extract(r["text"]))
        out.append(rec)

    fields = ["decision_date", "pub_date", "label_chosen", "label_source", "label_score",
              "labels_discussed", "n_labels_discussed",
              "rates_discussed", "n_rates_discussed", "glosses"]
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out)

    got = sum(1 for r in out if r["label_chosen"])
    print(f"резюме: {len(out)}; ярлык сигнала извлечён: {got}")
    print(f"{'дата':<12} {'ярлык':<18} {'ист.':<9} {'обсуждались':<34}")
    for r in out:
        print(f"{r['decision_date']:<12} {r['label_chosen'] or '—':<18} "
              f"{r['label_source'] or '—':<9} {r['labels_discussed'] or '—':<34}")

    print("\n=== расшифровки формулировок, данные самим ЦБ ===")
    seen = set()
    for r in out:
        for g in r["glosses"].split(" ;; "):
            if g and g not in seen:
                seen.add(g)
                print(f"  {g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
