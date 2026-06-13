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
        {"handle": "@lizabeta_b",       "name": "Лиза",  "cities": ["Воронеж", "Губкин"],     "service": "Волонтёры образовательных программ", "photo": None},
        {"handle": "@p.nekr",           "name": "П.",    "cities": ["Калининград"],            "service": "Волонтёры образовательных программ", "photo": None},
        {"handle": "@peaid",            "name": "П.",    "cities": ["Тамбов", "Ижевск"],       "service": "Волонтёры образовательных программ", "photo": None},
        {"handle": "@a_z1609",          "name": "А.",    "cities": ["Волгоград", "Пятигорск"], "service": "Волонтёры образовательных программ", "photo": None},
        {"handle": "@daria_volkova328", "name": "Дарья", "cities": ["Москва"],                 "service": "Волонтёры образовательных программ", "photo": None},
    ],
}

PALETTE = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4",
    "#FFEAA7", "#DDA0DD", "#98D8C8", "#F7DC6F",
    "#BB8FCE", "#85C1E9",
]


# ── геокодирование ────────────────────────────────────────────────────────────

def geocode(city_name: str):
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


def build_city_panel(city, data):
    color_map = get_color_map(data["services"])
    vols = [(i, v) for i, v in enumerate(data["volunteers"]) if city in v.get("cities", [])]
    if not vols:
        return [html.P("Нет участников", style={"color": "#999", "fontSize": "12px", "margin": "0"})]

    items = []
    for i, v in vols:
        color = color_map.get(v["service"], "#888")
        photo = v.get("photo")
        photo_el = (
            html.Img(src=photo, className="vol-photo")
            if photo
            else html.Div("📷", className="vol-photo-placeholder")
        )
        del_btn = ([
            html.Button("Удалить", id={"type": "btn-del-photo", "index": i},
                        n_clicks=0, className="btn-photo-sm btn-photo-del"),
        ] if photo else [])

        items.append(html.Div([
            html.Div(photo_el, style={"marginRight": "10px", "flexShrink": "0"}),
            html.Div([
                html.Div([
                    html.Span(v["handle"],
                              style={"fontWeight": "bold", "color": color, "fontSize": "13px"}),
                    (html.Span(" " + v["name"],
                               style={"color": "#777", "fontSize": "12px"}) if v.get("name") else ""),
                ]),
                html.Div(", ".join(v["cities"]),
                         style={"color": "#999", "fontSize": "11px", "marginBottom": "4px"}),
                html.Div([
                    dcc.Upload(
                        id={"type": "upload-photo", "index": i},
                        children=html.Button(
                            "Изменить" if photo else "+ фото",
                            className="btn-photo-sm",
                        ),
                        accept="image/*",
                        style={"display": "inline-block", "marginRight": "4px"},
                    ),
                ] + del_btn, style={"display": "flex", "alignItems": "center", "gap": "4px"}),
            ], style={"flex": "1"}),
        ], style={"display": "flex", "alignItems": "center",
                  "padding": "8px 0", "borderBottom": "1px solid #f0f0f0"}))
    return items


# ── приложение ────────────────────────────────────────────────────────────────

app = dash.Dash(__name__, title="Форум ШУМ 2026 — Карта команды",
                suppress_callback_exceptions=True)
server = app.server

app.layout = html.Div(className="page-wrap", children=[
    dcc.Store(id="data-store", data=INITIAL_DATA),
    dcc.Store(id="selected-city", data=None),

    html.Div(className="header", children=[
        html.H1("Форум ШУМ · 2026"),
        html.P("Работяги ШУМа · География команды"),
    ]),

    html.Div(className="main-layout", children=[

        # карта
        html.Div(className="map-col", children=[
            dcc.Graph(id="map-graph", config={"scrollZoom": True}),
        ]),

        # боковая панель
        html.Div(className="side-col", children=[

            # ── карточка города — появляется при клике на метку ──
            html.Div(id="city-detail", className="card city-detail",
                     style={"display": "none"}, children=[
                html.Div([
                    html.Span(id="city-detail-title",
                              style={"fontWeight": "700", "fontSize": "15px", "color": "#4a4a6a"}),
                    html.Button("×", id="btn-close-detail", className="btn-delete"),
                ], style={"display": "flex", "justifyContent": "space-between",
                          "alignItems": "center", "marginBottom": "8px"}),
                html.Div(id="city-detail-content"),
            ]),

            # список участников
            html.Div(style={"marginBottom": "14px"}, children=[
                html.P("Участники", className="vol-section-title"),
                html.Div(id="volunteer-list"),
            ]),

            # форма добавления участника
            html.Div(className="card", children=[
                html.H3("Добавить участника"),
                dcc.Input(id="in-handle", placeholder="@telegram",
                          className="field", style={"width": "100%"}),
                dcc.Input(id="in-name", placeholder="Имя (необязательно)",
                          className="field", style={"width": "100%"}),
                dcc.Input(id="in-city-1", placeholder="Город 1 (обязательно)",
                          className="field", style={"width": "100%"}),
                dcc.Input(id="in-city-2", placeholder="Город 2",
                          className="field", style={"width": "100%"}),
                dcc.Input(id="in-city-3", placeholder="Город 3",
                          className="field", style={"width": "100%"}),
                dcc.Dropdown(id="in-service", placeholder="Служба",
                             style={"marginBottom": "8px", "fontSize": "13px"}),
                dcc.Upload(
                    id="in-photo",
                    children=html.Div(id="in-photo-label", children="📷 Прикрепить фото"),
                    accept="image/*",
                    className="upload-photo-input",
                ),
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
    Output("in-photo-label", "children"),
    Input("in-photo", "contents"),
    Input("in-photo", "filename"),
    prevent_initial_call=True,
)
def update_photo_label(contents, filename):
    if contents:
        return f"✓ {filename}"
    return "📷 Прикрепить фото"


@app.callback(
    Output("data-store", "data", allow_duplicate=True),
    Output("msg-volunteer", "children"),
    Output("in-handle", "value"),
    Output("in-name", "value"),
    Output("in-city-1", "value"),
    Output("in-city-2", "value"),
    Output("in-city-3", "value"),
    Output("in-service", "value"),
    Output("in-photo", "contents"),
    Input("btn-add-volunteer", "n_clicks"),
    State("in-handle", "value"),
    State("in-name", "value"),
    State("in-city-1", "value"),
    State("in-city-2", "value"),
    State("in-city-3", "value"),
    State("in-service", "value"),
    State("in-photo", "contents"),
    State("data-store", "data"),
    prevent_initial_call=True,
)
def add_volunteer(n, handle, name, city1, city2, city3, service, photo, data):
    if not handle or not city1 or not service:
        return (data, "Заполните handle, город 1 и службу",
                handle, name, city1, city2, city3, service, photo)

    handle = handle.strip()
    cities = [c.strip() for c in [city1, city2 or "", city3 or ""] if c.strip()]

    failed = []
    for city in cities:
        if city not in CITY_COORDS:
            if geocode(city) is None:
                failed.append(city)

    if failed:
        return (data, f"Не удалось найти на карте: {', '.join(failed)}",
                handle, name, city1, city2, city3, service, photo)

    entry = {
        "handle": handle,
        "name": (name or "").strip(),
        "cities": cities,
        "service": service,
        "photo": photo,
    }
    data = dict(data)
    data["volunteers"] = data["volunteers"] + [entry]
    return data, "", "", "", "", "", "", None, None


@app.callback(
    Output("map-graph", "figure"),
    Output("volunteer-list", "children"),
    Input("data-store", "data"),
)
def refresh(data):
    return build_figure(data), build_volunteer_list(data)


# ── city detail panel ─────────────────────────────────────────────────────────

@app.callback(
    Output("selected-city", "data"),
    Input("map-graph", "clickData"),
    Input("btn-close-detail", "n_clicks"),
    prevent_initial_call=True,
)
def update_selected_city(click_data, _close):
    triggered = dash.callback_context.triggered[0]["prop_id"]
    if "btn-close-detail" in triggered:
        return None
    if click_data:
        text = click_data["points"][0].get("text", "")
        parts = text.split("<br>")
        if len(parts) >= 2:
            return parts[-1]
    return None


@app.callback(
    Output("city-detail", "style"),
    Output("city-detail-title", "children"),
    Output("city-detail-content", "children"),
    Input("selected-city", "data"),
    Input("data-store", "data"),
)
def render_city_detail(city, data):
    if not city:
        return {"display": "none"}, "", []
    return {"display": "block"}, city, build_city_panel(city, data)


@app.callback(
    Output("data-store", "data", allow_duplicate=True),
    Input({"type": "upload-photo", "index": ALL}, "contents"),
    State("data-store", "data"),
    prevent_initial_call=True,
)
def upload_photo(contents_list, data):
    if not any(c for c in contents_list if c):
        return data
    triggered_id = dash.callback_context.triggered[0]["prop_id"].split(".")[0]
    idx = json.loads(triggered_id)["index"]
    new_photo = dash.callback_context.triggered[0]["value"]
    if not new_photo or idx >= len(data["volunteers"]):
        return data
    data = dict(data)
    vols = list(data["volunteers"])
    vols[idx] = {**vols[idx], "photo": new_photo}
    data["volunteers"] = vols
    return data


@app.callback(
    Output("data-store", "data", allow_duplicate=True),
    Input({"type": "btn-del-photo", "index": ALL}, "n_clicks"),
    State("data-store", "data"),
    prevent_initial_call=True,
)
def delete_photo(n_clicks_list, data):
    if not any(n_clicks_list):
        return data
    triggered_id = dash.callback_context.triggered[0]["prop_id"].split(".")[0]
    idx = json.loads(triggered_id)["index"]
    if idx >= len(data["volunteers"]):
        return data
    data = dict(data)
    vols = list(data["volunteers"])
    vols[idx] = {**vols[idx], "photo": None}
    data["volunteers"] = vols
    return data


if __name__ == "__main__":
    app.run(debug=True, port=8051)
