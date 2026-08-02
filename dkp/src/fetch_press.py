"""Скачивает пресс-релизы ЦБ РФ по решениям о ключевой ставке.

Схема:
1. Читает список дат из data/reference/decisions.csv.
2. Для каждой даты:
   - пробует ряд типовых URL (для 2018+);
   - если не подходит — идёт в поиск cbr.ru и берёт первую ссылку /press/pr/,
     у которой имя файла начинается с DDMMYYYY (или DDMMYY для 2013),
     а заголовок содержит ставку.
3. Сохраняет сырой HTML в data/raw/press/YYYY-MM-DD.html.
4. Ведёт data/interim/press_index.csv (дата, URL, статус, размер).

Запуск: python3 dkp/src/fetch_press.py
"""

from __future__ import annotations

import csv
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "data" / "reference" / "decisions.csv"
RAW = ROOT / "data" / "raw" / "press"
INDEX = ROOT / "data" / "interim" / "press_index.csv"

UA = "Mozilla/5.0 (compatible; cbr-dkp-research/0.1)"
BASE = "https://www.cbr.ru"

RU_MONTHS = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]

CANDIDATE_TIMES = ["133000", "013000", "103000", "120000", "150000", "160000"]

# Прямые URL для дат, где поиск даёт нерелевантный или пустой ответ.
MANUAL_URLS: dict[str, str] = {
    "2013-09-13": "/press/pr/?file=130913_1350427l.htm",
    "2014-10-31": "/press/pr/?file=31102014_133027dkp2014-10-31t13_15_16.htm",
    "2014-12-11": "/press/pr/?file=11122014_133014dkp2014-12-11t13_08_33.htm",
    "2022-04-08": "/press/pr/?file=08042022_114000key.htm",
}


def http_get(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def is_real_release(html: str) -> bool:
    """Настоящий релиз всегда содержит landing-text + 'Совет директоров Банка России'."""
    return "landing-text" in html and "Совет директоров Банка России" in html


def title_of(html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def try_direct(iso_date: str) -> tuple[str, str] | None:
    """Быстрый путь для 2018+: URL со схемой DDMMYYYY_HHMMSSkey.htm."""
    y, m, d = iso_date.split("-")
    if int(y) < 2018:
        return None
    dd = f"{d}{m}{y}"
    for hhmmss in CANDIDATE_TIMES:
        for suffix in ("key", "Key"):
            url = f"{BASE}/press/pr/?file={dd}_{hhmmss}{suffix}.htm"
            try:
                html = http_get(url)
            except Exception:
                continue
            if is_real_release(html):
                return url, html
            time.sleep(0.3)
    return None


def try_search(iso_date: str) -> tuple[str, str] | None:
    """Медленный путь: поиск по cbr.ru + фильтр по префиксу даты в URL."""
    y, m, d = iso_date.split("-")
    ru_date = f"{int(d)} {RU_MONTHS[int(m)]} {y}"
    # Префикс имени файла: с 2014 — 8 цифр DDMMYYYY, для 2013 — 6 цифр DDMMYY.
    prefix8 = f"{d}{m}{y}"
    prefix6 = f"{d}{m}{y[2:]}"

    for query in [
        f'"ключевую ставку" "{ru_date}" совет директоров',
        f'ключевая ставка {ru_date}',
        f'о ключевой ставке банка россии {ru_date}',
    ]:
        url = f"{BASE}/search/?text=" + urllib.parse.quote(query)
        try:
            html = http_get(url)
        except Exception:
            continue
        hits = re.findall(
            r'href="(/press/pr/\?file=([\w.-]+)\.htm)"[^>]*>([^<]+)',
            html,
        )
        for href, name, title in hits:
            if not (name.startswith(prefix8 + "_") or name.startswith(prefix6 + "_")):
                continue
            title = title.strip()
            if "ключевой ставке" not in title.lower() and "ключевую ставку" not in title.lower():
                continue
            try:
                page = http_get(BASE + href)
            except Exception:
                continue
            if is_real_release(page):
                return BASE + href, page
            time.sleep(0.3)
        time.sleep(0.6)
    return None


def load_decisions() -> list[dict[str, str]]:
    with DECISIONS.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    INDEX.parent.mkdir(parents=True, exist_ok=True)

    decisions = load_decisions()
    index_rows: list[dict[str, str]] = []

    for row in decisions:
        iso = row["date"]
        out_path = RAW / f"{iso}.html"
        if out_path.exists() and out_path.stat().st_size > 5000:
            # Уже скачано — просто фиксируем в индексе.
            html = out_path.read_text(encoding="utf-8")
            url_m = re.search(r"<!-- source_url: (.*?) -->", html)
            url = url_m.group(1) if url_m else ""
            index_rows.append({
                "date": iso, "url": url, "status": "cached",
                "size": str(out_path.stat().st_size), "title": title_of(html),
            })
            print(f"[cached] {iso}")
            continue

        result = None
        if iso in MANUAL_URLS:
            url = BASE + MANUAL_URLS[iso]
            try:
                html = http_get(url)
                if is_real_release(html):
                    result = (url, html)
            except Exception as e:
                print(f"  manual URL failed: {e}")
        if result is None:
            result = try_direct(iso) or try_search(iso)
        if result is None:
            print(f"[MISS  ] {iso}")
            index_rows.append({"date": iso, "url": "", "status": "not_found", "size": "0", "title": ""})
            continue

        url, html = result
        # Помечаем источник в комментарии — чтобы индекс восстанавливался из файла.
        html_with_meta = f"<!-- source_url: {url} -->\n<!-- fetched: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} -->\n" + html
        out_path.write_text(html_with_meta, encoding="utf-8")
        print(f"[  ok  ] {iso} -> {url}")
        index_rows.append({
            "date": iso, "url": url, "status": "ok",
            "size": str(out_path.stat().st_size), "title": title_of(html),
        })
        time.sleep(0.8)

    with INDEX.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "url", "status", "size", "title"])
        writer.writeheader()
        writer.writerows(index_rows)

    ok = sum(1 for r in index_rows if r["status"] in ("ok", "cached"))
    print(f"\nИтого: {ok}/{len(index_rows)} релизов собрано.")
    return 0 if ok == len(index_rows) else 1


if __name__ == "__main__":
    sys.exit(main())
