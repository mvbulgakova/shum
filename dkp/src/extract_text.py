"""Извлекает чистый текст из сырых HTML пресс-релизов и резюме.

Выходы:
- data/processed/press.jsonl   — по одному релизу на строку
- data/processed/summaries.jsonl
- data/processed/press.csv     — короткая сводка (для просмотра в Excel)

Формат JSONL (пресс-релиз):
{
  "date": "2024-10-25",
  "rate_new": 21.0, "rate_old": 19.0, "delta_bp": 200, "direction": "up",
  "url": "...",
  "title": "Банк России ... 21,00% годовых",
  "text": "<чистый текст релиза>",
  "n_chars": ..., "n_words": ...,
  "signal_sentence": "<последний абзац/фраза о сигнале>",
}
"""

from __future__ import annotations

import csv
import html as html_lib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "data" / "reference" / "decisions.csv"
PRESS_RAW = ROOT / "data" / "raw" / "press"
SUMM_RAW = ROOT / "data" / "raw" / "summaries"
PROC = ROOT / "data" / "processed"

# «Сигнальная» фраза — то, что ЦБ говорит про будущее.
SIGNAL_MARKERS = [
    r"Банк России будет ",
    r"Банк России продолжит ",
    r"Банк России допускает ",
    r"Банк России считает",
    r"Банк России оценивает",
    r"требуется дальнейш",
    r"требуется более ",
    r"дальнейш\w+ решения",
    r"поддержание жестких",
    r"на пути к цели",
    r"вернется к цели",
    r"будет принимать дальнейшие",
    r"будет оценивать",
    r"продолжит принимать",
]


def strip_tags(html: str) -> str:
    # remove scripts/styles
    html = re.sub(r"<(script|style|noscript)\b[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    # entities to unicode
    html = html_lib.unescape(html)
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace(" ", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_body(html: str) -> tuple[str, str, str]:
    """Возвращает (title, url, body_text)."""
    m = re.search(r"<!-- source_url: (.*?) -->", html)
    url = m.group(1) if m else ""

    tm = re.search(r"<title>(.*?)</title>", html, re.S)
    title = re.sub(r"\s+", " ", html_lib.unescape(tm.group(1))).strip() if tm else ""
    title = title.replace(" | Банк России", "").strip()

    # Основной контент — landing-text; отсекаем до соцкнопок или конца div-цепочки.
    bm = re.search(r'<div class="landing-text[^"]*"[^>]*>(.*?)<div class="social', html, re.S)
    if not bm:
        bm = re.search(r'<div class="landing-text[^"]*"[^>]*>(.*?)(?:<div class="footer|</main)', html, re.S)
    if not bm:
        bm = re.search(r'<div class="landing-text[^"]*"[^>]*>(.*)', html, re.S)
    body_html = bm.group(1) if bm else html

    text = strip_tags(body_html)

    # Отбросим стандартный хвост релиза (навигация, номера телефонов, реквизиты сайта).
    for cut in [
        "Следующее заседание Совета директоров",
        "Заявление Председателя Банка России",
        "При использовании материала ссылка",
        "Схема расположения",
        "8 800 300-30-00",
        "Единый портал",
        "Основные направления",
    ]:
        i = text.find(cut)
        if i > 0:
            text = text[:i].strip()

    return title, url, text


def find_signal_sentence(text: str) -> str:
    # Ищем предложение про будущее ДКП (обычно ближе к концу первого блока / в 3-4 абзаце).
    for pat in SIGNAL_MARKERS:
        m = re.search(rf"[^.]*{pat}[^.]*\.", text, re.I)
        if m:
            return m.group(0).strip()
    return ""


def load_decisions() -> dict[str, dict[str, str]]:
    with DECISIONS.open(encoding="utf-8") as f:
        return {r["date"]: r for r in csv.DictReader(f)}


def process_press() -> list[dict]:
    decisions = load_decisions()
    out: list[dict] = []
    for path in sorted(PRESS_RAW.glob("*.html")):
        iso = path.stem
        raw = path.read_text(encoding="utf-8")
        title, url, text = extract_body(raw)
        d = decisions.get(iso, {})
        rec = {
            "date": iso,
            "rate_new": float(d.get("rate_new") or "nan") if d.get("rate_new") else None,
            "rate_old": float(d.get("rate_old") or "nan") if d.get("rate_old") else None,
            "delta_bp": int(d.get("delta_bp") or "0") if d.get("delta_bp") else None,
            "direction": d.get("direction", ""),
            "url": url,
            "title": title,
            "n_chars": len(text),
            "n_words": len(text.split()),
            "signal_sentence": find_signal_sentence(text),
            "text": text,
        }
        out.append(rec)
    return out


def process_summaries() -> list[dict]:
    out: list[dict] = []
    for path in sorted(SUMM_RAW.glob("*.html")):
        stem = path.stem  # DECISION__pub_PUB or unknown__pub_PUB
        m = re.match(r"(?P<dec>[\d-]+|unknown)__pub_(?P<pub>\d{8})", stem)
        decision = m.group("dec") if m else ""
        pub = m.group("pub") if m else ""
        raw = path.read_text(encoding="utf-8")
        title, url, text = extract_body(raw)
        out.append({
            "decision_date": decision if decision != "unknown" else "",
            "pub_date": f"{pub[:2]}.{pub[2:4]}.{pub[4:]}" if pub else "",
            "url": url, "title": title,
            "n_chars": len(text), "n_words": len(text.split()),
            "text": text,
        })
    return out


def main() -> int:
    PROC.mkdir(parents=True, exist_ok=True)

    press = process_press()
    (PROC / "press.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in press) + "\n",
        encoding="utf-8",
    )
    # короткая сводка
    with (PROC / "press.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "date", "rate_new", "rate_old", "delta_bp", "direction",
            "n_chars", "n_words", "signal_sentence", "url",
        ])
        w.writeheader()
        for r in press:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})

    summaries = process_summaries()
    (PROC / "summaries.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in summaries) + "\n",
        encoding="utf-8",
    )
    with (PROC / "summaries.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "decision_date", "pub_date", "n_chars", "n_words", "url",
        ])
        w.writeheader()
        for r in summaries:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})

    print(f"press: {len(press)} релизов | сумма симв: {sum(r['n_chars'] for r in press):,}")
    print(f"summaries: {len(summaries)} | сумма симв: {sum(r['n_chars'] for r in summaries):,}")
    # быстрый sanity-check: длина текста по годам
    from collections import defaultdict
    by_year: dict[str, list[int]] = defaultdict(list)
    for r in press:
        by_year[r["date"][:4]].append(r["n_words"])
    print("\nсредняя длина релиза по годам (слов):")
    for y in sorted(by_year):
        s = by_year[y]
        print(f"  {y}: n={len(s):>3}  avg={sum(s)//len(s):>4}  min={min(s):>3} max={max(s):>4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
