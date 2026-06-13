import json
import requests as http_requests
import dash
from dash import dcc, html, Input, Output, State, ALL
import plotly.graph_objects as go

# ── начальные данные ──────────────────────────────────────────────────────────

CITY_COORDS = {
    "Москва":       (55.7558, 37.6176),
    "Воронеж":      (51.6683, 39.1844),
    "Губкин":       (51.2833, 37.5500),
    "Калининград":  (54.7104, 20.4522),
    "Тамбов":       (52.7212, 41.4523),
    "Ижевск":       (56.8527, 53.2114),
    "Волгоград":    (48.7080, 44.5133),
    "Пятигорск":    (44.0398, 43.0617),
}

INITIAL_DATA = {
    "services": ["Волонтёры образовательных программ"],
    "volunteers": [
        {"handle": "@lizabeta_b",       "name": "Лиза",  "cities": ["Воронеж", "Губкин"],     "service": "Волонтёры образовательных программ"},
        {"handle": "@p.nekr",           "name": "П.",    "cities": ["Калининград"],            "service": "Волонтёры образовательных программ"},
        {"handle": "@peaid",            "name": "П.",    "cities": ["Тамбов", "Ижевск"],       "service": "Волонтёры образовательных программ"},
        {"handle": "@a_z1609",          "name": "А.",    "cities": ["Волгоград", "Пятигорск"], "service": "Волонтёры образовательных программ"},
        {"handle": "@daria_volkova328", "name": "Дарья", "cities": ["Москва"],                 "service": "Волонтёры образовательных программ"},
    ],
}

PALETTE = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4",
    "#FFEAA7", "#DDA0DD", "#98D8C8", "#F7DC6F",
    "#BB8FCE", "#85C1E9",
]


# ── геокодирование ────────────────────────────────────────────────────────────

def geocode(city_name: str):
    """Возвращает (lat, lon) через Nominatim или None."""
    cached = CITY_COORDS.get(city_name)
    if cached:
        return cached
    try:
        resp = http_requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": city_name, "format": "json", "limit": 1},
            headers={"User-Agent": "SHUM-Forum-Map/1.0"},
            timeout=5,
        )
        data = resp.json()
        if data:
            lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
            CITY_COORDS[city_name] = (lat, lon)
            return lat, lon
    except Exception:
        pass
    return None


# ── вспомогательные функции ───────────────────────────────────────────────────

def get_color_map(services):
    return {s: PALETTE[i % len(PALETTE)] for i, s in enumerate(services)}


def build_figure(data):
    color_map = get_color_map(data["services"])
    traces = {}
    for v in data["volunteers"]:
        svc = v["service"]
        if svc not in traces:
            traces[svc] = {"lats": [], "lons": [], "texts": []}
        for city in v["cities"]:
            coords = CITY_COORDS.get(city)
            if coords:
                traces[svc]["lats"].append(coords[0])
                traces[svc]["lons"].append(coords[1])
                traces[svc]["texts"].append(f"{v['handle']}<br>{city}")

    fig = go.Figure()
    for svc, pts in traces.items():
        color = color_map.get(svc, "#888")
        fig.add_trace(go.Scattergeo(
            lat=pts["lats"], lon=pts["lons"], text=pts["texts"],
            mode="markers+text", textposition="top center",
            textfont=dict(size=11, color="#333"),
            marker=dict(size=14, color=color, line=dict(width=2, color="white")),
            hovertemplate="<b>%{text}</b><extra></extra>",
            name=svc,
        ))

    fig.update_layout(
        geo=dict(
            scope="asia", resolution=50,
            showland=True,  landcolor="#F0EEE9",
            showocean=True, oceancolor="#D6EAF8",
            showcountries=True, countrycolor="#CCCCCC",
            showrivers=True, rivercolor="#AED6F1",
            showlakes=True,  lakecolor="#D6EAF8",
            center=dict(lat=62, lon=80), projection_scale=2.5,
            lataxis_range=[40, 80], lonaxis_range=[18, 170],
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(x=0.01, y=0.01, bgcolor="rgba(255,255,255,0.85)",
                    bordercolor="#ccc", borderwidth=1, font=dict(size=12)),
        paper_bgcolor="#FAFAFA", plot_bgcolor="#FAFAFA",
        height=520,
    )
    return fig


def build_volunteer_list(data):
    color_map = get_color_map(data["services"])
    items = []
    for i, v in enumerate(data["volunteers"]):
        color = color_map.get(v["service"], "#888")
        items.append(html.Div([
            html.Div([
                html.Span(v["handle"],
                          style={"fontWeight": "bold", "color": color, "fontSize": "14px"}),
                html.Span(" · " + ", ".join(v["cities"]),
                          style={"color": "#555", "fontSize": "13px"}),
                html.Br(),
                html.Span(v["service"], style={
                    "fontSize": "11px", "color": "white", "background": color,
                    "padding": "1px 8px", "borderRadius": "10px",
                    "display": "inline-block", "marginTop": "3px",
                }),
            ], style={"flex": "1"}),
            html.Button("×", id={"type": "btn-delete", "index": i},
                        n_clicks=0, className="btn-delete"),
        ], className="vol-item",
           style={"borderLeft": f"4px solid {color}", "display": "flex", "alignItems": "center"}))
    return items


# ── приложение ────────────────────────────────────────────────────────────────

app = dash.Dash(__name__, title="Форум ШУМ 2026 — Карта команды")
server = app.server

app.layout = html.Div(className="page-wrap", children=[
    dcc.Store(id="data-store", data=INITIAL_DATA),

    html.Div(className="header", children=[
        html.H1("Форум ШУМ · 2026"),
        html.P("Волонтёры образовательных программ · География команды"),
    ]),

    html.Div(className="main-layout", children=[

        # карта
        html.Div(className="map-col", children=[
            dcc.Graph(id="map-graph", config={"scrollZoom": True}),
        ]),

        # боковая панель
        html.Div(className="side-col", children=[

            # список участников
            html.Div(style={"marginBottom": "14px"}, children=[
                html.P("Участники", className="vol-section-title"),
                html.Div(id="volunteer-list"),
            ]),

            # форма добавления участника
            html.Div(className="card", children=[
                html.H3("Добавить участника"),
                dcc.Input(id="in-handle",  placeholder="@telegram",
                          className="field", style={"width": "100%"}),
                dcc.Input(id="in-name",    placeholder="Имя (необязательно)",
                          className="field", style={"width": "100%"}),
                dcc.Input(id="in-city-1", placeholder="Город 1 (обязательно)",
                          className="field", style={"width": "100%"}),
                dcc.Input(id="in-city-2", placeholder="Город 2",
                          className="field", style={"width": "100%"}),
                dcc.Input(id="in-city-3", placeholder="Город 3",
                          className="field", style={"width": "100%"}),
                dcc.Dropdown(id="in-service", placeholder="Служба",
                             style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Button("Добавить", id="btn-add-volunteer",
                            n_clicks=0, className="btn btn-primary"),
                html.Div(id="msg-volunteer", className="msg"),
            ]),

            # форма добавления службы
            html.Div(className="card", children=[
                html.H3("Добавить службу"),
                dcc.Input(id="in-service-name", placeholder="Название службы",
                          className="field", style={"width": "100%"}),
                html.Button("Добавить службу", id="btn-add-service",
                            n_clicks=0, className="btn btn-green"),
                html.Div(id="msg-service", className="msg"),
            ]),
        ]),
    ]),
])


# ── callbacks ─────────────────────────────────────────────────────────────────

@app.callback(
    Output("in-service", "options"),
    Input("data-store", "data"),
)
def update_service_options(data):
    return [{"label": s, "value": s} for s in data["services"]]


@app.callback(
    Output("data-store", "data", allow_duplicate=True),
    Output("msg-service", "children"),
    Output("in-service-name", "value"),
    Input("btn-add-service", "n_clicks"),
    State("in-service-name", "value"),
    State("data-store", "data"),
    prevent_initial_call=True,
)
def add_service(n, name, data):
    if not name or not name.strip():
        return data, "Введите название", ""
    name = name.strip()
    if name in data["services"]:
        return data, "Такая служба уже есть", ""
    data = dict(data)
    data["services"] = data["services"] + [name]
    return data, "", ""


@app.callback(
    Output("data-store", "data", allow_duplicate=True),
    Input({"type": "btn-delete", "index": ALL}, "n_clicks"),
    State("data-store", "data"),
    prevent_initial_call=True,
)
def delete_volunteer(n_clicks_list, data):
    if not any(n_clicks_list):
        return data
    triggered_id = dash.callback_context.triggered[0]["prop_id"].split(".")[0]
    idx = json.loads(triggered_id)["index"]
    data = dict(data)
    data["volunteers"] = [v for i, v in enumerate(data["volunteers"]) if i != idx]
    return data


@app.callback(
    Output("data-store", "data", allow_duplicate=True),
    Output("msg-volunteer", "children"),
    Output("in-handle", "value"),
    Output("in-name", "value"),
    Output("in-city-1", "value"),
    Output("in-city-2", "value"),
    Output("in-city-3", "value"),
    Output("in-service", "value"),
    Input("btn-add-volunteer", "n_clicks"),
    State("in-handle", "value"),
    State("in-name", "value"),
    State("in-city-1", "value"),
    State("in-city-2", "value"),
    State("in-city-3", "value"),
    State("in-service", "value"),
    State("data-store", "data"),
    prevent_initial_call=True,
)
def add_volunteer(n, handle, name, city1, city2, city3, service, data):
    if not handle or not city1 or not service:
        return data, "Заполните handle, город 1 и службу", handle, name, city1, city2, city3, service

    handle = handle.strip()
    cities = [c.strip() for c in [city1, city2 or "", city3 or ""] if c.strip()]

    failed = []
    for city in cities:
        if city not in CITY_COORDS:
            coords = geocode(city)
            if coords is None:
                failed.append(city)

    if failed:
        msg = f"Не удалось найти на карте: {', '.join(failed)}"
        return data, msg, handle, name, city1, city2, city3, service

    entry = {
        "handle": handle,
        "name": (name or "").strip(),
        "cities": cities,
        "service": service,
    }
    data = dict(data)
    data["volunteers"] = data["volunteers"] + [entry]
    return data, "", "", "", "", "", "", None


@app.callback(
    Output("map-graph", "figure"),
    Output("volunteer-list", "children"),
    Input("data-store", "data"),
)
def refresh(data):
    return build_figure(data), build_volunteer_list(data)


if __name__ == "__main__":
    app.run(debug=True, port=8051)
