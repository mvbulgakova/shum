"""Собирает финальный HTML-отчёт с инлайновыми SVG-графиками.

Самодостаточный файл: без CDN, без внешних шрифтов, работает в светлой и
тёмной теме. Графики рисуются как SVG прямо из данных — воспроизводимо и
не требует plotly в рантайме.

Палитра — референсная из гайда по визуализации, проверена валидатором
в обоих режимах (categorical 3 слота; diverging blue↔red с серой серединой).
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data" / "processed" / "panel.csv"
INFOM = ROOT / "data" / "processed" / "infom.csv"
VALID = ROOT / "data" / "processed" / "validation.json"
LP = ROOT / "data" / "processed" / "local_projections.json"
ROB = ROOT / "data" / "processed" / "robustness.json"
DEL = ROOT / "data" / "processed" / "deliberation.json"
OUT = ROOT / "report.html"


def load_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ---------------------------------------------------------------------------
# Геометрия графиков
# ---------------------------------------------------------------------------

W, H = 980, 190
PAD_L, PAD_R, PAD_T, PAD_B = 54, 18, 14, 26


def xscale(d: date, d0: date, d1: date) -> float:
    span = (d1 - d0).days or 1
    return PAD_L + (W - PAD_L - PAD_R) * ((d - d0).days / span)


def yscale(v: float, lo: float, hi: float, h: int = H) -> float:
    span = (hi - lo) or 1
    return PAD_T + (h - PAD_T - PAD_B) * (1 - (v - lo) / span)


def year_ticks(d0: date, d1: date) -> list[date]:
    return [date(y, 1, 1) for y in range(d0.year, d1.year + 1)
            if d0 <= date(y, 1, 1) <= d1]


def axis_and_grid(d0: date, d1: date, lo: float, hi: float, steps: list[float],
                  h: int = H, fmt: str = "{:.0f}") -> str:
    parts = []
    for v in steps:
        y = yscale(v, lo, hi, h)
        parts.append(
            f'<line class="grid" x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" y2="{y:.1f}"/>')
        parts.append(
            f'<text class="tick" x="{PAD_L - 8}" y="{y + 3.5:.1f}" text-anchor="end">'
            f'{fmt.format(v)}</text>')
    for t in year_ticks(d0, d1):
        x = xscale(t, d0, d1)
        parts.append(
            f'<text class="tick" x="{x:.1f}" y="{h - 8}" text-anchor="middle">{t.year}</text>')
    return "".join(parts)


# ---------------------------------------------------------------------------
# График 1: ключевая ставка (step-линия)
# ---------------------------------------------------------------------------

def chart_rate(panel: list[dict]) -> str:
    pts = [(date.fromisoformat(r["date"]), float(r["rate_new"]))
           for r in panel if r["rate_new"]]
    d0, d1 = pts[0][0], pts[-1][0]
    lo, hi = 0, 22
    steps = [0, 5, 10, 15, 20]

    seg = []
    prev = None
    for d, v in pts:
        x, y = xscale(d, d0, d1), yscale(v, lo, hi)
        if prev is None:
            seg.append(f"M {x:.1f} {y:.1f}")
        else:
            seg.append(f"L {x:.1f} {prev[1]:.1f} L {x:.1f} {y:.1f}")
        prev = (x, y)
    seg.append(f"L {xscale(d1, d0, d1):.1f} {prev[1]:.1f}")

    hov = "".join(
        f'<circle class="hot" cx="{xscale(d, d0, d1):.1f}" cy="{yscale(v, lo, hi):.1f}" r="9">'
        f'<title>{d.isoformat()} — {v:.2f}%</title></circle>'
        for d, v in pts)

    return f'''<svg viewBox="0 0 {W} {H}" role="img" aria-label="Ключевая ставка Банка России, 2013–2026">
  {axis_and_grid(d0, d1, lo, hi, steps, fmt="{:.0f}%")}
  <path class="rate-line" d="{' '.join(seg)}"/>
  {hov}
</svg>'''


# ---------------------------------------------------------------------------
# График 2: индекс жёсткости (диверging бары)
# ---------------------------------------------------------------------------

def chart_hardness(panel: list[dict]) -> str:
    pts = [(date.fromisoformat(r["date"]), float(r["hardness_v2"]),
            r["modality"], r["direction_signal"], int(r["delta_bp"]),
            r["cbr_label"])
           for r in panel]
    d0, d1 = pts[0][0], pts[-1][0]
    lo, hi = -0.8, 0.8
    zero = yscale(0, lo, hi)

    bars = []
    for d, v, mod, dirn, dbp, lab in pts:
        x = xscale(d, d0, d1)
        y = yscale(v, lo, hi)
        tip = (f"{d.isoformat()}\nиндекс {v:+.3f}\nмодальность: {mod or '—'}\n"
               f"вектор: {dirn}\nΔставки: {dbp:+d} б.п."
               + (f"\nярлык ЦБ: {lab}" if lab else ""))

        if abs(v) <= 0.02:
            # Нейтральный сигнал — это измеренное значение, а не отсутствие
            # данных. Рисуем различимой засечкой на нуле, иначе 43 таких
            # заседания визуально исчезают и путаются с пропуском.
            bars.append(
                f'<rect class="bar-neutral" x="{x - 2.6:.1f}" y="{zero - 2.5:.1f}" '
                f'width="5.2" height="5" rx="2"><title>{esc(tip)}</title></rect>')
            continue

        cls = "bar-hawk" if v > 0 else "bar-dove"
        top, ht = (y, zero - y) if v > 0 else (zero, y - zero)
        bars.append(
            f'<rect class="{cls}" x="{x - 2.6:.1f}" y="{top:.1f}" width="5.2" '
            f'height="{max(ht, 3):.1f}" rx="2"><title>{esc(tip)}</title></rect>')

    return f'''<svg viewBox="0 0 {W} {H}" role="img" aria-label="Индекс жёсткости сигнала по заседаниям">
  {axis_and_grid(d0, d1, lo, hi, [-0.5, 0, 0.5], fmt="{:+.1f}")}
  <line class="baseline" x1="{PAD_L}" y1="{zero:.1f}" x2="{W - PAD_R}" y2="{zero:.1f}"/>
  {''.join(bars)}
</svg>'''


# ---------------------------------------------------------------------------
# График 3: инфляционные ожидания инФОМ
# ---------------------------------------------------------------------------

def chart_infom(infom: list[dict], d0: date, d1: date) -> str:
    exp = [(date.fromisoformat(r["month"]), float(r["expected_med"]))
           for r in infom if r["expected_med"]]
    obs = [(date.fromisoformat(r["month"]), float(r["observed_med"]))
           for r in infom if r["observed_med"]]
    exp = [p for p in exp if d0 <= p[0] <= d1]
    obs = [p for p in obs if d0 <= p[0] <= d1]
    lo, hi = 0, 24
    steps = [0, 6, 12, 18, 24]

    def path(pts):
        return " ".join(
            ("M" if i == 0 else "L") + f" {xscale(d, d0, d1):.1f} {yscale(v, lo, hi):.1f}"
            for i, (d, v) in enumerate(pts))

    hov = "".join(
        f'<circle class="hot" cx="{xscale(d, d0, d1):.1f}" cy="{yscale(v, lo, hi):.1f}" r="7">'
        f'<title>{d.strftime("%Y-%m")} — ожидаемая {v:.1f}%</title></circle>'
        for d, v in exp)

    return f'''<svg viewBox="0 0 {W} {H}" role="img" aria-label="Инфляционные ожидания инФОМ">
  {axis_and_grid(d0, d1, lo, hi, steps, fmt="{:.0f}%")}
  <path class="ser-observed" d="{path(obs)}"/>
  <path class="ser-expected" d="{path(exp)}"/>
  {hov}
  <text class="lbl lbl-expected" x="{W - PAD_R - 4}" y="{yscale(exp[-1][1], lo, hi) - 9:.1f}" text-anchor="end">ожидаемая</text>
  <text class="lbl lbl-observed" x="{W - PAD_R - 4}" y="{yscale(obs[-1][1], lo, hi) + 16:.1f}" text-anchor="end">наблюдаемая</text>
</svg>'''


# ---------------------------------------------------------------------------
# График 4: валидация — индекс vs ярлык ЦБ
# ---------------------------------------------------------------------------

LABEL_ORDER = ["умеренно мягкий", "нейтральный", "умеренно жесткий", "жесткий"]


def chart_validation(v: dict) -> str:
    pairs = v["test1"]["pairs"]
    w, h = 520, 300
    pl, pr, pt, pb = 128, 22, 16, 40
    xs_lo, xs_hi = -0.5, 0.5

    def X(val):
        return pl + (w - pl - pr) * ((val - xs_lo) / (xs_hi - xs_lo))

    def Y(lab):
        i = LABEL_ORDER.index(lab)
        return pt + (h - pt - pb) * (1 - i / (len(LABEL_ORDER) - 1))

    parts = []
    for i, lab in enumerate(LABEL_ORDER):
        y = Y(lab)
        parts.append(f'<line class="grid" x1="{pl}" y1="{y:.1f}" x2="{w - pr}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{pl - 10}" y="{y + 3.5:.1f}" text-anchor="end">{lab}</text>')
    for tick in (-0.5, -0.25, 0, 0.25, 0.5):
        x = X(tick)
        parts.append(f'<text class="tick" x="{x:.1f}" y="{h - 14}" text-anchor="middle">{tick:+.2f}</text>')
    parts.append(f'<text class="axis-title" x="{(pl + w - pr) / 2:.0f}" y="{h - 1}" '
                 f'text-anchor="middle">индекс жёсткости по пресс-релизу</text>')

    # Совпадающие точки разводим симметрично относительно своей линии, иначе
    # стопка уползает в одну сторону и перестаёт читаться как «на уровне».
    groups: dict[tuple, list[dict]] = {}
    for p in pairs:
        groups.setdefault((round(p["index"], 3), p["cbr_label"]), []).append(p)

    for (idx_v, lab), members in groups.items():
        n = len(members)
        for i, p in enumerate(members):
            off = (i - (n - 1) / 2) * 7.5
            cx, cy = X(idx_v), Y(lab) + off
            cls = ("dot-hawk" if p["cbr_score"] > 0
                   else "dot-dove" if p["cbr_score"] < 0 else "dot-neutral")
            parts.append(
                f'<circle class="{cls}" cx="{cx:.1f}" cy="{cy:.1f}" r="5.5">'
                f'<title>{p["date"]}\nиндекс {p["index"]:+.3f}\nярлык ЦБ: {lab}</title></circle>')

    return f'''<svg viewBox="0 0 {w} {h}" role="img" aria-label="Индекс против собственного ярлыка Банка России">
  {''.join(parts)}
</svg>'''


# ---------------------------------------------------------------------------
# График 5: local projections
# ---------------------------------------------------------------------------

def chart_lp(lp: dict) -> str:
    spec = lp["full"]["specs"]["полная спецификация"]
    pts = [(e["h"], e["beta"], e["se"]) for e in spec if "beta" in e]
    w, h = 520, 300
    pl, pr, pt, pb = 54, 22, 16, 42
    lo, hi = -0.8, 2.2

    def X(hh):
        return pl + (w - pl - pr) * (hh / max(p[0] for p in pts))

    def Y(v):
        return pt + (h - pt - pb) * (1 - (v - lo) / (hi - lo))

    parts = []
    for v in (0, 1, 2):
        y = Y(v)
        parts.append(f'<line class="grid" x1="{pl}" y1="{y:.1f}" x2="{w - pr}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{pl - 8}" y="{y + 3.5:.1f}" text-anchor="end">{v:+.0f}</text>')
    parts.append(f'<line class="baseline" x1="{pl}" y1="{Y(0):.1f}" x2="{w - pr}" y2="{Y(0):.1f}"/>')

    up = " ".join(("M" if i == 0 else "L") + f" {X(hh):.1f} {Y(b + 1.645 * se):.1f}"
                  for i, (hh, b, se) in enumerate(pts))
    dn = " ".join(f"L {X(hh):.1f} {Y(b - 1.645 * se):.1f}"
                  for hh, b, se in reversed(pts))
    parts.append(f'<path class="ci-band" d="{up} {dn} Z"/>')

    line = " ".join(("M" if i == 0 else "L") + f" {X(hh):.1f} {Y(b):.1f}"
                    for i, (hh, b, _) in enumerate(pts))
    parts.append(f'<path class="lp-line" d="{line}"/>')
    for hh, b, se in pts:
        t = b / se if se else 0
        parts.append(
            f'<circle class="lp-dot" cx="{X(hh):.1f}" cy="{Y(b):.1f}" r="4.5">'
            f'<title>горизонт {hh} мес\nβ = {b:+.3f}\nse = {se:.3f}\nt = {t:.2f}</title></circle>')
        parts.append(f'<text class="tick" x="{X(hh):.1f}" y="{h - 20}" text-anchor="middle">{hh}</text>')
    parts.append(f'<text class="axis-title" x="{(pl + w - pr) / 2:.0f}" y="{h - 3}" '
                 f'text-anchor="middle">горизонт, месяцев после заседания</text>')

    return f'''<svg viewBox="0 0 {w} {h}" role="img" aria-label="Реакция инфляционных ожиданий на сигнал по горизонтам">
  {''.join(parts)}
</svg>'''


# ---------------------------------------------------------------------------
# Сборка
# ---------------------------------------------------------------------------

CSS = """
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);
  font:16px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif;
  -webkit-text-size-adjust:100%}
.viz-root{
  --plane:#f9f9f7; --surface:#fcfcfb;
  --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --base:#c3c2b7; --border:rgba(11,11,11,.10);
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a;
  --hawk:#e34948; --dove:#2a78d6; --neutral:#c3c2b7;
  --band:rgba(42,120,214,.16);
}
@media (prefers-color-scheme:dark){
  :root:where(:not([data-theme="light"])) .viz-root{
    --plane:#0d0d0d; --surface:#1a1a19;
    --ink:#fff; --ink-2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --base:#383835; --border:rgba(255,255,255,.10);
    --s1:#3987e5; --s2:#d95926; --s3:#199e70;
    --hawk:#e66767; --dove:#3987e5; --neutral:#383835;
    --band:rgba(57,135,229,.20);
  }
}
:root[data-theme="dark"] .viz-root{
  --plane:#0d0d0d; --surface:#1a1a19;
  --ink:#fff; --ink-2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --base:#383835; --border:rgba(255,255,255,.10);
  --s1:#3987e5; --s2:#d95926; --s3:#199e70;
  --hawk:#e66767; --dove:#3987e5; --neutral:#383835;
  --band:rgba(57,135,229,.20);
}
.wrap{max-width:1080px;margin:0 auto;padding:40px 22px 80px}
h1{font-size:29px;line-height:1.25;margin:0 0 6px;letter-spacing:-.02em}
h2{font-size:21px;margin:46px 0 12px;letter-spacing:-.01em}
h3{font-size:16px;margin:26px 0 8px;color:var(--ink-2)}
.sub{color:var(--ink-2);margin:0 0 30px;font-size:15px}
.card{background:var(--surface);border:1px solid var(--border);
  border-radius:12px;padding:18px 20px;margin:16px 0}
.panel-title{font-size:13px;font-weight:600;color:var(--ink-2);margin:0 0 2px}
.panel-note{font-size:12.5px;color:var(--muted);margin:0 0 8px}
svg{display:block;width:100%;height:auto;overflow:visible}
.grid{stroke:var(--grid);stroke-width:1}
.baseline{stroke:var(--base);stroke-width:1.5}
.tick{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
.axis-title{fill:var(--ink-2);font-size:12px}
.rate-line{fill:none;stroke:var(--ink);stroke-width:2;
  stroke-linejoin:round;stroke-linecap:round}
.bar-hawk{fill:var(--hawk)}
.bar-dove{fill:var(--dove)}
.bar-neutral{fill:var(--neutral)}
.ser-expected{fill:none;stroke:var(--s2);stroke-width:2;
  stroke-linejoin:round;stroke-linecap:round}
.ser-observed{fill:none;stroke:var(--s1);stroke-width:2;stroke-dasharray:4 3;
  stroke-linejoin:round;stroke-linecap:round}
.lbl{font-size:12px;font-weight:600}
.lbl-expected{fill:var(--s2)}
.lbl-observed{fill:var(--s1)}
.hot{fill:transparent;pointer-events:all}
.dot-hawk{fill:var(--hawk);stroke:var(--surface);stroke-width:2}
.dot-dove{fill:var(--dove);stroke:var(--surface);stroke-width:2}
.dot-neutral{fill:var(--muted);stroke:var(--surface);stroke-width:2}
.ci-band{fill:var(--band);stroke:none}
.lp-line{fill:none;stroke:var(--s1);stroke-width:2;stroke-linejoin:round}
.lp-dot{fill:var(--s1);stroke:var(--surface);stroke-width:2}
.legend{display:flex;gap:18px;flex-wrap:wrap;margin:10px 0 0;
  font-size:12.5px;color:var(--ink-2)}
.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;
  margin-right:6px;vertical-align:-1px}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px;min-width:560px}
th,td{text-align:left;padding:8px 11px;border-bottom:1px solid var(--grid);
  vertical-align:top}
th{font-weight:600;color:var(--ink-2);font-size:12.5px;
  text-transform:uppercase;letter-spacing:.03em}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:16px}
code{background:var(--grid);padding:1.5px 5px;border-radius:4px;font-size:13.5px}
blockquote{margin:16px 0;padding:12px 18px;border-left:3px solid var(--s2);
  background:var(--surface);color:var(--ink-2);border-radius:0 8px 8px 0}
.tag{display:inline-block;font-size:11.5px;padding:2px 8px;border-radius:20px;
  background:var(--grid);color:var(--ink-2);margin-right:6px}
.warn{border-left:3px solid var(--s2)}
ul,ol{padding-left:22px}
li{margin:5px 0}
"""


def main() -> int:
    panel = load_csv(PANEL)
    infom = load_csv(INFOM)
    v = json.loads(VALID.read_text(encoding="utf-8"))
    lp = json.loads(LP.read_text(encoding="utf-8"))
    rob = json.loads(ROB.read_text(encoding="utf-8"))
    dl = json.loads(DEL.read_text(encoding="utf-8"))
    dl_sorted = sorted(dl["rows"], key=lambda r: -r["dissent_index"])
    dl_rows = "".join(
        f'<tr><td>{r["decision_date"]}</td>'
        f'<td class="num">{r["dissent_index"]:+.2f}</td>'
        f'<td class="num">{r["delta_bp"]:+d}</td>'
        f'<td>{r["cbr_label"] or "—"}</td></tr>'
        for r in dl_sorted[:3] + dl_sorted[-3:])

    d0 = date.fromisoformat(panel[0]["date"])
    d1 = date.fromisoformat(panel[-1]["date"])

    t1, t2, t3 = v["test1"], v["test2"], v["test3"]
    lp_full = lp["full"]["specs"]["полная спецификация"]
    lp_rows = "".join(
        f'<tr><td class="num">{e["h"]}</td><td class="num">{e["beta"]:+.3f}</td>'
        f'<td class="num">{e["se"]:.3f}</td><td class="num">{e["t"]:+.2f}</td>'
        f'<td class="num">{e["p"]:.3f}</td></tr>'
        for e in lp_full if "beta" in e)

    glossary = [
        ("жёсткий", "«допускает возможность повышения»", "possibility × up"),
        ("умеренно жёсткий", "«оценит целесообразность повышения»", "delayed_evaluation × up"),
        ("нейтральный", "«без указания на направленность»", "— × none / hold"),
        ("умеренно мягкий", "«об оценке целесообразности снижения»", "delayed_evaluation × down"),
    ]
    gloss_rows = "".join(
        f"<tr><td><b>{a}</b></td><td>{b}</td><td><code>{c}</code></td></tr>"
        for a, b, c in glossary)

    val_rows = "".join(
        f'<tr><td>{p["date"]}</td><td class="num">{p["index"]:+.3f}</td>'
        f'<td>{p["cbr_label"]}</td><td class="num">{p["cbr_score"]:+.1f}</td></tr>'
        for p in t1["pairs"])

    n_labels = sum(1 for r in panel if r["cbr_label"])
    n_summ = sum(1 for r in panel if r["summary_words"])

    html = f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Тональность коммуникации Банка России и инфляционные ожидания</title>
<style>{CSS}</style></head>
<body><div class="viz-root"><div class="wrap">

<h1>Тональность коммуникации Банка России и инфляционные ожидания</h1>
<p class="sub">Корпус 103 пресс-релизов по ключевой ставке (2013–2026) и 20 резюме
обсуждения (2024–2026). Морфосинтаксический индекс жёсткости сигнала,
валидация против собственной таксономии регулятора, связь с опросами инФОМ.</p>

<h2>В чём проблема словарного подхода</h2>
<p>Существующие работы по коммуникации ЦБ считают тональность по словарю
«позитив/негатив». Такой подход слепнет там, где два противоположных сигнала
выражены одной и той же лексемой:</p>

<div class="card">
<div class="scroll"><table>
<thead><tr><th>Заседание</th><th>Формулировка</th><th class="num">Δ ставки</th>
<th>Что видит словарь</th><th>Что видит морфосинтаксис</th></tr></thead>
<tbody>
<tr><td>25.10.2024</td><td>«…<b>требуется</b> дальнейшее <b>ужесточение</b> ДКП»</td>
<td class="num">+200 б.п.</td><td rowspan="2">одна и та же лемма
<code>требуется</code> → одинаковый вес</td>
<td>необходимость · вектор вверх · без смягчителей</td></tr>
<tr><td>24.07.2026</td><td>«…<b>требуется</b> более плавное <b>снижение</b> ставки»</td>
<td class="num">−25 б.п.</td>
<td>необходимость · вектор вниз · смягчитель степени</td></tr>
</tbody></table></div>
</div>

<p>Различают их не слова, а грамматика: тип модальности, направление, наличие
ограничителя, залог. Индекс меряет не тональность, а <b>степень связанности
регулятора обязательством</b>.</p>

<h2>Динамика: ставка, сигнал, ожидания</h2>

<div class="card">
<p class="panel-title">Ключевая ставка Банка России</p>
<p class="panel-note">Шаговая линия; 103 решения с сентября 2013 года</p>
{chart_rate(panel)}
</div>

<div class="card">
<p class="panel-title">Индекс жёсткости сигнала</p>
<p class="panel-note">Знак — направление следующего шага, величина — связанность
обязательством. Наведите на столбик: модальность, вектор, ярлык ЦБ</p>
{chart_hardness(panel)}
<div class="legend">
  <span><i style="background:var(--hawk)"></i>ястребиный сигнал</span>
  <span><i style="background:var(--neutral)"></i>нейтральный</span>
  <span><i style="background:var(--dove)"></i>голубиный сигнал</span>
</div>
</div>

<div class="card">
<p class="panel-title">Инфляционные ожидания населения, инФОМ</p>
<p class="panel-note">Медианные оценки, % годовых</p>
{chart_infom(infom, d0, d1)}
</div>

<h2>Ключевая находка: у ЦБ есть собственная таксономия сигнала</h2>
<p>В резюме обсуждения — корпусе, который до сих пор почти не исследовался, —
Банк России <b>сам называет градацию своего сигнала и расшифровывает её</b>:</p>

<blockquote>«Обсуждалось два варианта сигнала: <b>жесткий</b> (допускает возможность
повышения) и <b>умеренно жесткий</b> (оценит целесообразность повышения)»
<br><span class="tag">резюме от 06.11.2024</span></blockquote>

<p>Эта таксономия оказывается в точности перекрёстной таблицей двух осей,
которые индекс измеряет независимо — модальности и направления:</p>

<div class="card"><div class="scroll"><table>
<thead><tr><th>Ярлык ЦБ</th><th>Расшифровка регулятора</th>
<th>Ячейка индекса</th></tr></thead>
<tbody>{gloss_rows}</tbody></table></div></div>

<h2>Валидация</h2>
<p>Индекс считается по <b>пресс-релизу</b>. Ярлык извлекается из <b>резюме
обсуждения</b> — другого документа, опубликованного на шесть рабочих дней позже.
Проверка не круговая: разные тексты, разные процедуры извлечения.</p>

<div class="grid2">
  <div class="card">
    <p class="panel-title">Индекс против ярлыка ЦБ</p>
    <p class="panel-note">n = {t1['n']} заседаний · Спирмен ρ = {t1['spearman']}
      · согласие по знаку {t1['sign_agreement']}</p>
    {chart_validation(v)}
  </div>
  <div class="card">
    <p class="panel-title">Реакция ожиданий на сигнал</p>
    <p class="panel-note">β по горизонтам, полная спецификация;
      полоса — 90% доверительный интервал (HAC)</p>
    {chart_lp(lp)}
  </div>
</div>

<div class="card">
<h3>Три теста</h3>
<div class="scroll"><table>
<thead><tr><th>Тест</th><th>Что проверяет</th><th class="num">Результат</th></tr></thead>
<tbody>
<tr><td>Конструктная валидность</td>
    <td>Индекс по релизу против ярлыка из резюме</td>
    <td class="num">ρ = {t1['spearman']}, знак {t1['sign_agreement']}</td></tr>
<tr><td>Воспроизводимость таксономии</td>
    <td>Пара (модальность × вектор) → класс ЦБ, только на ячейках,
        выведенных независимо</td>
    <td class="num">{t2['independent_match']}/{t2['n_independent']}
        ({t2['independent_match_pct']}%)</td></tr>
<tr><td>Предсказание</td>
    <td>Индекс(t) → Δ ставки(t+1), против словарного бенчмарка</td>
    <td class="num">{t3['index_v2']['spearman']} против
        {t3['dictionary_baseline']['spearman']}</td></tr>
</tbody></table></div>
<p class="panel-note" style="margin-top:10px">На цикле 2022–2026 предсказательная
корреляция индекса — {t3['index_v2_2022plus']['spearman']}
(n = {t3['index_v2_2022plus']['n']}).</p>
</div>

<div class="card">
<h3>Сопоставление по заседаниям</h3>
<div class="scroll"><table>
<thead><tr><th>Дата</th><th class="num">Индекс</th><th>Ярлык ЦБ</th>
<th class="num">Шкала</th></tr></thead>
<tbody>{val_rows}</tbody></table></div>
</div>

<h2>Робастность: держится ли результат на подобранных числах</h2>
<p>Веса в индексе (необходимость 0.85, возможность 0.55, отложенная оценка 0.35…)
выбраны исследователем. Естественное возражение — результат есть артефакт
этих чисел. Четыре проверки.</p>

<div class="card"><div class="scroll"><table>
<thead><tr><th>Проверка</th><th>Что делается</th><th class="num">Результат</th></tr></thead>
<tbody>
<tr><td>Ординальная версия</td>
    <td>Все веса выброшены: модальность → ранг, направление → знак,
        смягчители и условия не учитываются вовсе</td>
    <td class="num">ρ = {rob['ordinal']['spearman_ordinal_vs_label']}</td></tr>
<tr><td>Возмущение весов</td>
    <td>Каждый вес × равномерный шум ±40%, {rob['perturbation']['n_iter']} повторов</td>
    <td class="num">медиана {rob['perturbation']['spearman_median']},
        95% [{rob['perturbation']['spearman_ci95'][0]}, {rob['perturbation']['spearman_ci95'][1]}]</td></tr>
<tr><td>Перестановки шкалы</td>
    <td>Случайный порядок модальностей вместо предложенного</td>
    <td class="num">p = {rob['permutation']['empirical_p']}</td></tr>
<tr><td>Leave-one-out</td>
    <td>Поочерёдное исключение каждого заседания</td>
    <td class="num">размах ρ = {rob['loo']['range']}</td></tr>
</tbody></table></div></div>

<div class="card warn">
<h3>Что показала проверка перестановок — и почему это важно</h3>
<p>Случайный порядок модальностей работает <b>не хуже</b> предложенного
(p = {rob['permutation']['empirical_p']}). Это не значит, что модальность
бесполезна. Причина в структуре выборки: <b>ось направления сама по себе даёт
ρ = {rob['permutation']['spearman_direction_only']}</b>, и модальность нужна лишь
для одного различения — «жёсткий» против «умеренно жёсткого» внутри восходящего
вектора.</p>
<p>Изолируем это различение: берём подвыборку, где направление одинаково, и
смотрим, разделяет ли модальность классы ЦБ там, где направление не помогает.</p>
<p>В {rob['modality_axis']['up']['n']} случаях с вектором «вверх» ранг модальности
разделяет классы <b>идеально</b>: все «умеренно жёсткие» — отложенная оценка,
все «жёсткие» — возможность. Точная вероятность такого разделения случайно
равна {rob['modality_axis']['up']['exact_p']}.</p>
<p><b>Вывод, который выдерживает возражение.</b> Ось направления валидирована
твёрдо. Ось модальности указывает в верную сторону во всех доступных случаях,
но выборка мала — это главное, что исправят новые данные. Числовые веса
не несут нагрузки вовсе: ординальная версия без единого коэффициента даёт
ρ = {rob['ordinal']['spearman_ordinal_vs_label']}.</p>
</div>

<h2>Связь с инфляционными ожиданиями</h2>
<p>Local projections на горизонтах 0–6 месяцев. Зависимая переменная — изменение
медианной ожидаемой инфляции инФОМ. Контроли: фактическое изменение ставки,
уровень ожиданий до заседания, их преддинамика, наблюдаемая инфляция.
Стандартные ошибки Ньюи–Уэста.</p>

<div class="card"><div class="scroll"><table>
<thead><tr><th class="num">Горизонт, мес</th><th class="num">β</th>
<th class="num">se</th><th class="num">t</th><th class="num">p</th></tr></thead>
<tbody>{lp_rows}</tbody></table></div></div>

<div class="card warn">
<h3>Как это читать — и чего это не доказывает</h3>
<p>Знак β положителен и растёт с горизонтом: после <b>более жёсткого</b> сигнала
ожидаемая инфляция через 3–6 месяцев оказывается <b>выше</b>, а не ниже.
Наивный вывод «коммуникация работает наоборот» неверен. Есть три объяснения:</p>
<ol>
<li><b>Обратная причинность.</b> ЦБ ужесточает сигнал, когда предвидит ускорение
инфляции. Ожидания растут потому, что инфляция действительно растёт.</li>
<li><b>Информационный эффект.</b> Жёсткий сигнал раскрывает частную информацию
регулятора о проблеме с инфляцией; агент обновляет ожидания вверх.</li>
<li><b>Сигнал не доходит.</b> Респонденты инФОМ пресс-релизов не читают,
и связь отражает общий макродрайвер.</li>
</ol>
<p>Против версии 3 работает контрольная спецификация: если регрессором взять
<i>связанность без знака направления</i> — насколько категорично сформулировано
безотносительно того, куда, — коэффициенты в основном незначимы. Значит, работает
именно направленное содержание, а чистый макродрайвер направления не различал бы.</p>
<p>Плацебо-тест на преддинамику незначим
(p = {lp['pretrend_placebo']['p']}): индекс не является простым следствием уже
случившегося движения ожиданий.</p>
<p>Развести версии 1 и 2 на этих данных <b>нельзя</b>. Нужна декомпозиция сигнала
на ожидаемую и неожиданную компоненту — например, через опросы аналитиков о том,
какого сигнала они ждали. Это следующий шаг, а не вывод текущей работы.</p>
</div>

<h2>Дискуссия в Совете: отрицательный результат</h2>
<p>Пресс-релиз — консолидированная позиция, он ничего не говорит о том,
насколько единодушно она принята. Резюме обсуждения — протокол дискуссии,
где разногласие проговаривается явно кванторными оборотами:
«<i>часть участников</i>», «<i>некоторые участники</i>» против
«<i>участники согласились</i>», «<i>были единодушны</i>». По ним построен
индекс разногласия.</p>

<div class="card">
<div class="scroll"><table>
<thead><tr><th>Гипотеза</th><th class="num">Результат</th></tr></thead>
<tbody>
<tr><td>Разногласие выше при мелких шагах (крупный шаг очевиден)</td>
    <td class="num">ρ = {dl['rho_dissent_vs_abs_move']:+.3f}</td></tr>
<tr><td>Разногласие выше при смене сигнала</td>
    <td class="num">разница {dl['mean_dissent_signal_changed'] - dl['mean_dissent_signal_same']:+.2f}</td></tr>
<tr><td>Разногласие растёт с числом обсуждавшихся вариантов</td>
    <td class="num">ρ = {dl['rho_dissent_vs_options']:+.3f}</td></tr>
</tbody></table></div>
</div>

<div class="card warn">
<p><b>Ни одна из трёх гипотез не подтвердилась</b>, и это сообщается как есть.
Перебирать спецификации до появления значимого коэффициента на 20 наблюдениях
означало бы найти шум: мощность теста мала даже для крупных эффектов.</p>
<p>Что остаётся полезного: измеритель построен и документирован — он готов
к работе, когда корпус вырастет (резюме выходят 8 раз в год). Отсутствие
связи с величиной шага само по себе наблюдение: крупный шаг не означает,
что он был очевиден для участников обсуждения.</p>
</div>

<div class="card">
<h3>Крайние точки по спорности</h3>
<div class="scroll"><table>
<thead><tr><th>Дата</th><th class="num">Индекс разногласия</th>
<th class="num">Δ ставки</th><th>Ярлык ЦБ</th></tr></thead>
<tbody>{dl_rows}</tbody></table></div>
<p class="panel-note" style="margin-top:10px">Первые три — самые спорные,
последние три — самые единодушные.</p>
</div>

<h2>Оговорки</h2>
<ul>
<li><b>Оценка внутривыборочная.</b> Правила извлечения дорабатывались,
глядя на расхождения с ярлыками: так, форма условного сигнала («Если динамика
дезинфляции не обеспечит цель, Банк России рассмотрит вопрос о повышении»)
была добавлена после того, как выяснилось, что она теряется. Это добросовестная
итеративная разработка, но она означает, что {t1['sign_agreement']} по знаку —
показатель <i>на той же выборке</i>. Честная внесыборочная проверка возможна
только на будущих заседаниях.</li>
<li><b>Калибровка против валидации.</b> Порядок модальностей (возможность жёстче
отложенной оценки) зафиксирован до знакомства с расшифровками ЦБ — это
независимое подтверждение. Отнесение «поддерживать жёсткость ДКУ» к нейтральному
классу сделано <i>после</i> и является калибровкой; в таблице тестов эти ячейки
посчитаны отдельно.</li>
<li><b>Словарь регулятора дрейфует.</b> В резюме 2024 года «допускает возможность
повышения» определено как <i>жёсткий</i> сигнал; в резюме от 02.04.2025 формула
«с указанием на возможность повышения» отнесена к <i>умеренно жёсткому</i>.
Собственная таксономия ЦБ во времени не вполне стабильна, и это ограничивает
вес, который может нести внешний критерий. Там, где в резюме перечислены
обсуждавшиеся варианты, ярлык разводится по ним — это снимает зависимость
от дрейфующей формулировки.</li>
<li><b>Малая выборка ярлыков.</b> Резюме публикуются с февраля 2024,
поэтому ярлык доступен для {n_labels} заседаний из 103. Для более ранних
периодов индекс прямой проверки не имеет.</li>
<li><b>Высокая ρ отчасти механическая.</b> Индекс принимает около пяти
различных значений, монотонно отображающихся на четыре класса; ранговая
корреляция на почти ступенчатой функции завышена. Содержательнее смотреть
на согласие по знаку и точность класса.</li>
<li><b>Структурный сдвиг 2024 года.</b> Средняя длина релиза упала с ~1050 слов
(2021) до ~570; часть содержания переехала в резюме (~3900 слов). Сравнивать
показатели «до» и «после» без поправки нельзя.</li>
<li><b>Пять релизов без forward guidance.</b> В основном это экстренные решения
2014 года; для них индекс не определён, а не равен нулю.</li>
</ul>

<h2>Что в датасете</h2>
<div class="card"><div class="scroll"><table>
<thead><tr><th>Файл</th><th>Содержание</th><th class="num">Строк</th></tr></thead>
<tbody>
<tr><td><code>data/raw/press/</code></td><td>сырой HTML пресс-релизов</td><td class="num">103</td></tr>
<tr><td><code>data/raw/summaries/</code></td><td>сырой HTML резюме обсуждения</td><td class="num">20</td></tr>
<tr><td><code>processed/press.jsonl</code></td><td>чистый текст + метаданные</td><td class="num">103</td></tr>
<tr><td><code>processed/features_v2.csv</code></td><td>морфосинтаксические признаки</td><td class="num">103</td></tr>
<tr><td><code>processed/signal_labels.csv</code></td><td>таксономия сигнала ЦБ из резюме</td><td class="num">{n_labels} с ярлыком</td></tr>
<tr><td><code>processed/infom.csv</code></td><td>ряды инфляционных ожиданий</td><td class="num">161 мес</td></tr>
<tr><td><code>processed/panel.csv</code></td><td>объединённая панель для анализа</td><td class="num">103</td></tr>
</tbody></table></div>
<p class="panel-note" style="margin-top:10px">Резюме сопоставлены с решениями
для {n_summ} заседаний. Все источники открыты на cbr.ru; сбор воспроизводим
скриптами в <code>src/</code>.</p>
</div>

</div></div></body></html>'''

    OUT.write_text(html, encoding="utf-8")
    print(f"→ {OUT}  ({len(html):,} байт)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
