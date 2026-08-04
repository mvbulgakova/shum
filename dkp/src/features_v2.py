"""Морфосинтаксические признаки по всему корпусу (пресс-релизы + резюме).

Использует src/morphology.py. Выход:
  data/processed/features_v2.csv      — по пресс-релизам
  data/processed/summary_features.csv — по резюме обсуждения

Резюме отличаются структурно: это не единый нарратив, а протокол дискуссии.
Там есть блок «Опции по ключевой ставке» — сколько вариантов рассматривалось.
Это прямой индикатор разброса мнений внутри Совета, которого нет в релизе.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from morphology import analyze, tokenize, parse  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PRESS = ROOT / "data" / "processed" / "press.jsonl"
SUMM = ROOT / "data" / "processed" / "summaries.jsonl"
OUT_PRESS = ROOT / "data" / "processed" / "features_v2.csv"
OUT_SUMM = ROOT / "data" / "processed" / "summary_features.csv"


# Якоря forward-guidance, отобраны эмпирически: из корпуса извлечены все
# предложения, где будущее время сочетается с упоминанием ставки/ДКП, и
# отранжированы по частоте. Порядок = приоритет (специфичные раньше общих),
# потому что в одном релизе может сработать несколько.
FG_ANCHORS = [
    # Совершенный вид будущего — сильнейшее обязательство
    r"Банк России возобновит", r"Банк России рассмотрит",
    r"Банк России снизит", r"Банк России повысит", r"Банк России сохранит",
    r"Банк России перейд[её]т",
    # Необходимость
    r"требуется дальнейш", r"требуется более", r"требуется поддержан",
    r"требуется сохранени", r"потребуется сохранени", r"потребуется поддержани",
    r"период поддержания жестк", r"период поддержания ж[ёе]стк",
    # Возможность / готовность
    r"Банк России допускает", r"Банк России не исключает",
    r"Банк России будет готов", r"Банк России может проводить",
    r"будет рассматривать возможность",
    # Отложенная оценка
    r"будет оценивать целесообразность", r"Банк России будет оценивать",
    # Направленное намерение
    r"Банк России продолжит снижение", r"Банк России продолжит повышение",
    r"Банк России продолжит переходить", r"будет поддерживать такую",
    r"Банк России будет поддерживать", r"Банк России продолжит ",
    # Общее намерение
    r"Банк России будет принимать", r"Банк России будет ",
    r"Банк России намерен",
    # Безагентный пассив — сигнал есть, деятель удалён
    r"Решения по ключевой ставке будут приниматься",
    r"Дальнейшие решения по ключевой ставке будут приниматься",
    r"будут приниматься",
    # Прочее
    r"на ближайших заседаниях", r"на ближайшем заседании",
    r"дальнейш\w+ решени",
]


# Сценарный конditional: описание альтернативного развития событий, а НЕ
# базового сигнала. «В случае более высоких расходов … потребуется более
# жёсткая ДКП» — это оговорка про риск-сценарий, не guidance по ставке.
# Такие предложения нужно отличать от базового сигнала, иначе индекс
# читает условную оговорку как основное обещание.
SCENARIO_PREFIX = re.compile(
    r"^\s*(?:В\s+случае|Если\b|При\s+(?:более|усилении|реализации|сохранении|"
    r"дальнейшем|отсутствии)|В\s+сценарии|В\s+альтернативном)",
    re.I,
)

# Указание на то, что предложение описывает БАЗОВЫЙ путь.
BASELINE_HINT = re.compile(
    r"Банк\s+России|Совет\s+директоров|Решения\s+по\s+ключевой\s+ставке", re.I
)


def find_signal(text: str) -> tuple[str, str, int]:
    """Находит основное forward-guidance предложение.

    Возвращает (core, context, n_candidates).

    Отбор кандидатов — по якорям. Выбор основного из них:
      1. Сценарные оговорки («В случае …, потребуется …») отбрасываются:
         это описание альтернативы, а не базовый сигнал.
      2. Среди оставшихся предпочитается предложение с явным субъектом
         (Банк России / Совет директоров) — именно там регулятор говорит
         о собственных будущих действиях.
      3. При равенстве — более специфичный якорь (меньший ранг).
      4. При прочих равных — более позднее предложение: forward guidance
         в релизах ЦБ стоит в конце содержательного блока.
    """
    sents = re.split(r"(?<=[.!?])\s+", text)
    cands: list[tuple[int, int, bool, bool]] = []  # (rank, idx, is_scenario, has_agent)
    for i, s in enumerate(sents):
        for rank, anchor in enumerate(FG_ANCHORS):
            if re.search(anchor, s):
                has_agent = bool(BASELINE_HINT.search(s))
                # Условная конструкция считается сценарной оговоркой только
                # если в главной части НЕТ регулятора как субъекта действия.
                #   «В случае роста расходов потребуется более жёсткая ДКП»
                #       — безличная апо́досис, это описание риск-сценария;
                #   «Если дезинфляция не обеспечит цель, Банк России рассмотрит
                #    вопрос о повышении ставки»
                #       — регулятор назван, это state-contingent guidance,
                #         полноценная форма сигнала.
                # Без этой оговорки условный сигнал теряется целиком: в марте
                # 2025 года ЦБ намеренно выбрал именно такую форму, отметив,
                # что «стандартные формы умеренно жёсткого сигнала недостаточно
                # чётко отражают условия, при которых это может произойти».
                is_scenario = bool(SCENARIO_PREFIX.search(s)) and not has_agent
                cands.append((rank, i, is_scenario, has_agent))
                break
    if not cands:
        return "", "", 0

    non_scenario = [c for c in cands if not c[2]]
    pool = non_scenario or cands  # если все сценарные — берём что есть

    with_agent = [c for c in pool if c[3]]
    pool = with_agent or pool

    # Меньший rank лучше; при равном rank — большее i (позже в тексте).
    best = min(pool, key=lambda c: (c[0], -c[1]))
    i = best[1]
    tail = sents[i + 1] if i + 1 < len(sents) else ""
    return sents[i].strip(), (sents[i] + " " + tail).strip(), len(cands)


def signal_breadth(text: str, primary_core: str) -> tuple[int, str]:
    """Сколько ЕЩЁ предложений релиза несут направленное содержание.

    Найдено при ручной разметке (см. markup/manual_markup_10.md, находка №1):
    сигнал бывает распределён. В релизах 26.07.2024 и 25.10.2024 ястребиное
    содержание разложено на два предложения — утверждение о необходимости
    («требуется дополнительное ужесточение», «потребуется значительно более
    высокая траектория») и указание о ближайших заседаниях («будет оценивать
    целесообразность повышения»). Основной индекс берёт одно предложение и
    добавку теряет.

    Основной индекс НЕ меняется: он валидирован против таксономии ЦБ, а она
    описывает ровно одно указание — о следующих заседаниях. Поэтому широта
    сигнала выносится отдельным признаком.

    Возвращает (число дополнительных направленных предложений, их направления).
    """
    sents = re.split(r"(?<=[.!?])\s+", text)
    primary = re.sub(r"\s+", " ", primary_core).strip()
    extra_dirs: list[str] = []
    for s in sents:
        clean = re.sub(r"\s+", " ", s).strip()
        if not clean or clean == primary:
            continue
        # Сценарные оговорки не в счёт — это альтернатива, а не базовый путь.
        if SCENARIO_PREFIX.search(clean) and not BASELINE_HINT.search(clean):
            continue
        # Ретроспектива: описание эффекта уже принятого решения, не сигнал.
        if RETROSPECTIVE.search(clean):
            continue
        # Нужна связка «необходимость/возможность» + названное направление
        # применительно к ставке или ДКП.
        m = MODAL_MARKER.search(clean)
        if not m:
            continue
        sub = analyze(clean, clean)
        if sub.direction not in ("up", "down"):
            continue
        # Модальный маркер должен УПРАВЛЯТЬ направлением, а не просто стоять
        # в том же предложении. Проверка отсеивает «Повышение ключевой ставки
        # позволит … до уровней, необходимых, чтобы …»: там «необходимых»
        # относится к депозитным ставкам, а не к политике, и стоит далеко.
        if not _modal_governs_direction(clean, m):
            continue
        extra_dirs.append(sub.direction)
    return len(extra_dirs), "|".join(extra_dirs)


MODAL_MARKER = re.compile(r"требуется|потребуется|необходим\w+|допускает", re.I)
DIRECTION_WORD = re.compile(
    r"ужесточени\w+|повышени\w+|снижени\w+|смягчени\w+|ужесточ\w+|смягч\w+", re.I)

# Описание эффекта уже принятого решения, а не обещания на будущее.
RETROSPECTIVE = re.compile(
    r"позволит|позволяет|принято\w*\s+решени|произошедш\w+|реализованн\w+|"
    r"принятое\s+решение|уже\s+принят",
    re.I,
)

# Максимальное расстояние в словах между модальным маркером и направлением.
GOVERN_WINDOW = 6


def _modal_governs_direction(sentence: str, modal_match: re.Match) -> bool:
    """Стоит ли направление достаточно близко к модальному маркеру."""
    words = sentence.split()
    # позиция модального маркера в словах
    prefix_words = len(sentence[: modal_match.start()].split())
    for i, w in enumerate(words):
        if DIRECTION_WORD.search(w) and abs(i - prefix_words) <= GOVERN_WINDOW:
            return True
    return False


PRESS_FIELDS = [
    "date", "direction_actual", "delta_bp", "rate_new", "n_fg_candidates",
    "extra_directional_sents", "extra_directions",
    "modality", "modality_weight",
    "direction_signal", "level_stance", "direction_withheld",
    "agent_explicit", "impersonal", "passive",
    "hedge_count", "hedges", "cond_count", "conditionals",
    "nominalization_ratio", "finite_verbs", "verbal_nouns",
    "commitment", "hardness_v2", "stance",
    "n_words", "signal_core",
]


def process_press() -> list[dict]:
    rows = []
    with PRESS.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            core, ctx, n_cand = find_signal(r["text"])
            s = analyze(core, ctx)
            n_extra, extra_dirs = signal_breadth(r["text"], core)
            rows.append({
                "date": r["date"],
                "n_fg_candidates": n_cand,
                "extra_directional_sents": n_extra,
                "extra_directions": extra_dirs,
                "direction_actual": r.get("direction", ""),
                "delta_bp": r.get("delta_bp") or 0,
                "rate_new": r.get("rate_new") or "",
                "modality": s.modality,
                "modality_weight": s.modality_weight,
                "direction_signal": s.direction,
                "level_stance": s.level_stance,
                "direction_withheld": int(s.direction_withheld),
                "agent_explicit": int(s.agent_explicit),
                "impersonal": int(s.impersonal),
                "passive": int(s.passive),
                "hedge_count": len(s.hedges),
                "hedges": "|".join(s.hedges),
                "cond_count": len(s.conditionals),
                "conditionals": "|".join(s.conditionals),
                "nominalization_ratio": s.nominalization_ratio,
                "finite_verbs": s.finite_verbs,
                "verbal_nouns": s.verbal_nouns,
                "commitment": s.commitment,
                "hardness_v2": s.hardness,
                "stance": s.stance,
                "n_words": r.get("n_words") or 0,
                "signal_core": core,
            })
    return rows


# ---------------------------------------------------------------------------
# Резюме обсуждения — отдельная логика
# ---------------------------------------------------------------------------

# В резюме есть блок, где перечислены рассмотренные варианты ставки.
# Формулировки: «Участники обсуждали following варианты», «рассматривались
# варианты», «Опции по ключевой ставке».
OPTIONS_BLOCK = re.compile(
    r"(?:опци\w+\s+по\s+ключевой\s+ставке|"
    r"рассматрива\w+\s+(?:следующие\s+)?(?:варианты|опции)|"
    r"обсужда\w+\s+(?:следующие\s+)?(?:варианты|опции))",
    re.I,
)

# Числовые варианты ставки в тексте: «сохранение на уровне 21,00%», «повышение до 22%».
RATE_OPTION = re.compile(r"(\d{1,2},\d{2})\s*%")

# Маркеры разброса мнений внутри Совета.
DISSENT_MARKERS = re.compile(
    r"часть\s+участник\w+|некоторые\s+участник\w+|ряд\s+участник\w+|"
    r"другие\s+участник\w+|отдельные\s+участник\w+|"
    r"мнения\s+разделились|высказыва\w+\s+мнение|"
    r"вместе\s+с\s+тем\s+участник\w+",
    re.I,
)

CONSENSUS_MARKERS = re.compile(
    r"участники\s+согласились|участники\s+сошлись|"
    r"общее\s+мнение|единодушн\w+|консенсус",
    re.I,
)


SUMM_FIELDS = [
    "decision_date", "pub_date", "n_words",
    "modality", "direction_signal", "level_stance",
    "commitment", "hardness_v2",
    "n_rate_options", "rate_options",
    "dissent_count", "consensus_count", "dissent_per_1k",
    "signal_core",
]


def process_summaries() -> list[dict]:
    rows = []
    with SUMM.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            text = r["text"]
            core, ctx, _ = find_signal(text)
            s = analyze(core, ctx)

            # Сколько вариантов ставки обсуждалось.
            options: list[str] = []
            m = OPTIONS_BLOCK.search(text)
            if m:
                window = text[m.start(): m.start() + 1200]
                options = sorted(set(RATE_OPTION.findall(window)))

            dissent = len(DISSENT_MARKERS.findall(text))
            consensus = len(CONSENSUS_MARKERS.findall(text))
            n_words = r.get("n_words") or 0

            rows.append({
                "decision_date": r.get("decision_date", ""),
                "pub_date": r.get("pub_date", ""),
                "n_words": n_words,
                "modality": s.modality,
                "direction_signal": s.direction,
                "level_stance": s.level_stance,
                "commitment": s.commitment,
                "hardness_v2": s.hardness,
                "n_rate_options": len(options),
                "rate_options": "|".join(options),
                "dissent_count": dissent,
                "consensus_count": consensus,
                "dissent_per_1k": round(1000 * dissent / n_words, 2) if n_words else 0,
                "signal_core": core,
            })
    return sorted(rows, key=lambda x: x["decision_date"])


def main() -> int:
    press = process_press()
    with OUT_PRESS.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PRESS_FIELDS)
        w.writeheader()
        w.writerows(press)

    summ = process_summaries()
    with OUT_SUMM.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SUMM_FIELDS)
        w.writeheader()
        w.writerows(summ)

    from collections import Counter
    print(f"press features_v2: {len(press)}")
    print("  модальность:", dict(Counter(r["modality"] or "—" for r in press)))
    print("  вектор:", dict(Counter(r["direction_signal"] for r in press)))
    print("  уровень:", dict(Counter(r["level_stance"] for r in press)))
    withheld = sum(r["direction_withheld"] for r in press)
    print(f"  сигнал без названного вектора: {withheld}")
    nosig = sum(1 for r in press if not r["signal_core"])
    print(f"  без forward-guidance вообще: {nosig}")

    print(f"\nsummary features: {len(summ)}")
    opts = [r["n_rate_options"] for r in summ if r["n_rate_options"]]
    if opts:
        print(f"  варианты ставки найдены в {len(opts)}/{len(summ)} резюме, "
              f"в среднем {sum(opts)/len(opts):.1f}")
    print(f"  средняя длина: {sum(r['n_words'] for r in summ)//len(summ)} слов")
    print(f"  разброс мнений (на 1000 слов): "
          f"{sum(r['dissent_per_1k'] for r in summ)/len(summ):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
