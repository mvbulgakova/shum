"""Разведочный график: ставка, ожидаемая инфляция, индекс жёсткости.

Три панели, общая ось X:
1) Ключевая ставка (step) + Δbp на каждой точке.
2) Инфляционные ожидания инФОМ (ожидаемая 12м, наблюдаемая).
3) Hardness_v1 по решениям (bar, знак = ястреб/голубь).

Выход: dkp/fig/exploratory.html
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data" / "processed" / "panel.csv"
INFOM = ROOT / "data" / "processed" / "infom.csv"
DECS = ROOT / "data" / "reference" / "decisions.csv"
FIG = ROOT / "fig"


def load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)

    panel = load_csv(PANEL)
    infom = load_csv(INFOM)
    dec = load_csv(DECS)

    dec_by_date = {r["date"]: r for r in dec}

    # ---- ряд ставки: строим step из decisions ----
    rate_dates = [date.fromisoformat(r["date"]) for r in dec]
    rate_vals = [float(r["rate_new"]) for r in dec]

    # ---- инФОМ ----
    infom_x, infom_exp, infom_obs = [], [], []
    for r in infom:
        infom_x.append(date.fromisoformat(r["month"]))
        infom_exp.append(float(r["expected_med"]) if r["expected_med"] else None)
        infom_obs.append(float(r["observed_med"]) if r["observed_med"] else None)

    # ---- hardness ----
    h_x, h_y, h_txt = [], [], []
    for r in panel:
        h_x.append(date.fromisoformat(r["date"]))
        h_y.append(float(r["hardness_v1"]))
        d = dec_by_date[r["date"]]
        h_txt.append(
            f"{r['date']}<br>"
            f"Δставки: {int(r['delta_bp']):+d} бп → {d['rate_new']}%<br>"
            f"модальность: {r['modality'] or '—'}<br>"
            f"сигнал: {r['direction_signal']} | смягчители: {r['hedge_count']}<br>"
            f"условия: {'да' if r['has_conditionality']=='1' else 'нет'}<br>"
            f"<b>hardness_v1: {float(r['hardness_v1']):+.2f}</b>"
        )
    h_colors = ["#c62828" if v > 0.1 else "#1565c0" if v < -0.1 else "#9e9e9e" for v in h_y]

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04,
        row_heights=[0.34, 0.34, 0.32],
        subplot_titles=(
            "Ключевая ставка ЦБ РФ (step)",
            "Инфляционные ожидания инФОМ, медиана (%)",
            "Индекс жёсткости сигнала hardness_v1 (−1 голубь · +1 ястреб)",
        ),
    )

    fig.add_trace(
        go.Scatter(
            x=rate_dates, y=rate_vals, mode="lines+markers",
            line=dict(shape="hv", color="#000", width=2), marker=dict(size=5),
            name="Ключевая ставка, %",
            hovertemplate="%{x|%Y-%m-%d}: <b>%{y:.2f}%</b><extra></extra>",
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=infom_x, y=infom_exp, mode="lines+markers", name="Ожидаемая инфляция (12м)",
            line=dict(color="#c62828", width=2), marker=dict(size=4),
            connectgaps=False,
        ),
        row=2, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=infom_x, y=infom_obs, mode="lines+markers", name="Наблюдаемая инфляция",
            line=dict(color="#ef9a9a", width=2, dash="dot"), marker=dict(size=3),
            connectgaps=False,
        ),
        row=2, col=1,
    )
    fig.add_trace(
        go.Bar(
            x=h_x, y=h_y, marker_color=h_colors,
            hovertext=h_txt, hoverinfo="text",
            name="hardness_v1",
        ),
        row=3, col=1,
    )
    fig.add_hline(y=0, line_color="#666", line_width=1, row=3, col=1)

    fig.update_yaxes(title_text="%", row=1, col=1)
    fig.update_yaxes(title_text="%", row=2, col=1)
    fig.update_yaxes(title_text="hardness_v1", row=3, col=1, range=[-1, 1])
    fig.update_xaxes(row=3, col=1, title_text="дата")

    fig.update_layout(
        title=dict(
            text="Тональность коммуникации ЦБ РФ и инфляционные ожидания · разведка v1",
            font=dict(size=16),
        ),
        height=880, width=1300, hovermode="x unified",
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
        margin=dict(l=60, r=30, t=100, b=60),
        plot_bgcolor="white",
    )
    for i in range(1, 4):
        fig.update_xaxes(gridcolor="#eee", row=i, col=1)
        fig.update_yaxes(gridcolor="#eee", row=i, col=1)

    out = FIG / "exploratory.html"
    fig.write_html(out, include_plotlyjs="cdn")
    print(f"OK → {out}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
