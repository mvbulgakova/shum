"""Скачивает «Резюме обсуждения ключевой ставки» (2024–2026).

Резюме публикуется на 6-й рабочий день после решения. URL:
https://www.cbr.ru/dkp/mp_dec/decision_key_rate/summary_key_rate_DDMMYYYY/
где DDMMYYYY — дата *публикации резюме*, а не заседания.

Список summary_key_rate_* извлекаем из
https://www.cbr.ru/dkp/mp_dec/decision_key_rate/ (реестр по факту).
Сопоставление с датой решения — по дате публикации после ближайшего
предыдущего заседания в decisions.csv.
"""

from __future__ import annotations

import csv
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "data" / "reference" / "decisions.csv"
RAW = ROOT / "data" / "raw" / "summaries"
INDEX = ROOT / "data" / "interim" / "summaries_index.csv"

BASE = "https://www.cbr.ru"
LANDING = BASE + "/dkp/mp_dec/decision_key_rate/"
UA = "Mozilla/5.0 (compatible; cbr-dkp-research/0.1)"


def http_get(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def discover_summary_dates() -> list[str]:
    html = http_get(LANDING)
    dates = sorted({d for d in re.findall(r"summary_key_rate_(\d{8})", html)})
    return dates


def match_to_decision(pub_ddmmyyyy: str, decision_dates: list[str]) -> str | None:
    """К каждой публикации резюме — ближайшее предшествующее решение (за 4–15 дней)."""
    pub = datetime.strptime(pub_ddmmyyyy, "%d%m%Y").date()
    best = None
    for iso in decision_dates:
        d = datetime.strptime(iso, "%Y-%m-%d").date()
        gap = (pub - d).days
        if 4 <= gap <= 20 and (best is None or gap < best[1]):
            best = (iso, gap)
    return best[0] if best else None


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    INDEX.parent.mkdir(parents=True, exist_ok=True)

    with DECISIONS.open(encoding="utf-8") as f:
        decision_dates = [row["date"] for row in csv.DictReader(f)]

    pub_dates = discover_summary_dates()
    print(f"Найдено {len(pub_dates)} резюме на реестре.")

    rows = []
    for pub in pub_dates:
        decision = match_to_decision(pub, decision_dates)
        url = f"{LANDING}summary_key_rate_{pub}/"
        out = RAW / f"{decision or 'unknown'}__pub_{pub}.html"
        if out.exists() and out.stat().st_size > 5000:
            rows.append({"decision_date": decision or "", "pub_date": pub, "url": url, "status": "cached"})
            continue
        try:
            html = http_get(url)
        except Exception as e:
            print(f"  {pub}: ERR {e}")
            rows.append({"decision_date": decision or "", "pub_date": pub, "url": url, "status": f"err:{e}"})
            continue
        meta = f"<!-- source_url: {url} -->\n<!-- fetched: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} -->\n"
        out.write_text(meta + html, encoding="utf-8")
        print(f"  {pub} -> decision {decision}")
        rows.append({"decision_date": decision or "", "pub_date": pub, "url": url, "status": "ok"})
        time.sleep(0.7)

    with INDEX.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["decision_date", "pub_date", "url", "status"])
        w.writeheader()
        w.writerows(rows)
    print(f"\nИтого: {sum(1 for r in rows if r['status'] in ('ok','cached'))}/{len(rows)} резюме.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
