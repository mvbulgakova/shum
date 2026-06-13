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

SERVICES = [
    "Тим-лидер",
    "Служба образовательных программ",
    "Служба по работе с участниками",
    "Служба по организации атмосферных программ и церемоний",
    "Служба комплексного сопровождения",
    "Пресс-служба",
]

INITIAL_DATA = {
    "services": SERVICES,
    "volunteers": [
        {"handle": "@lizabeta_b",       "name": "Лиза",  "cities": ["Воронеж", "Губкин"],     "service": "Служба образовательных программ", "photo": None},
        {"handle": "@p.nekr",           "name": "П.",    "cities": ["Калининград"],            "service": "Служба по работе с участниками",  "photo": None},
        {"handle": "@peaid",            "name": "П.",    "cities": ["Тамбов", "Ижевск"],       "service": "Служба образовательных программ", "photo": None},
        {"handle": "@a_z1609",          "name": "А.",    "cities": ["Волгоград", "Пятигорск"], "service": "Служба по работе с участниками",  "photo": None},
        {"handle": "@daria_volkova328", "name": "Дарья", "cities": ["Москва"],                 "service": "Служба образовательных программ", "photo": None},
    ],
}

PALETTE = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4",
    "#FFEAA7", "#DDA0DD", "#98D8C8", "#F7DC6F",
    "#BB8FCE", "#85C1E9",
]

ORG_STRUCTURE = [
    {
        "dept": "Администрация",
        "color": "#FF6B6B",
        "people": [
            {"name": "Мандрыкина Татьяна Леонидовна", "role": "Директор Форума", "tags": "#главная", "phone": "89145401232", "channel": "мах"},
            {"name": "Кузнецова Любовь", "role": "", "tags": "#протоколы_совещаний #статусы #контроль_сроков", "phone": "89114502401", "channel": ""},
            {"name": "Асаналиев Павел Аскарович", "role": "Заместитель директора", "tags": "#смета #расходы #контроль #закупки #контракты", "phone": "89114749951", "channel": ""},
            {"name": "Садырева Арина", "role": "Помощник (если Павел не отвечает)", "tags": "", "phone": "", "channel": ""},
        ],
    },
    {
        "dept": "Программный штаб",
        "color": "#4ECDC4",
        "people": [
            {"name": "Мерзлякова Мария Вячеславовна", "role": "Программный директор", "tags": "#программы #кураторы #эксперты #партнеры #подневка #расписание #сложные_вопросы", "phone": "89141530556", "channel": "вк/мах"},
            {"name": "Мерзлякова Елена", "role": "Операционный менеджер (1–4 программа)", "tags": "#входящие вопросы Программы", "phone": "89922050041", "channel": "вк/мах"},
            {"name": "Ширинкина Полина", "role": "Операционный менеджер (5 программа)", "tags": "#входящие вопросы Программы", "phone": "89519589058", "channel": "ВК/мах"},
            {"name": "Филимонова Юлия", "role": "Главтехнолог (трекеры)", "tags": "#трекеры", "phone": "89536740475", "channel": "вк/мах"},
            {"name": "Хугашвили Мари", "role": "Куратор дист. программы", "tags": "#дистанционная_программа", "phone": "89881177476", "channel": "вк/мах/тг"},
            {"name": "Асриян Давид", "role": "Игропрактик, мотивационная программа", "tags": "#мотивационная_программа #рейтинг", "phone": "89532112012", "channel": "ТГ/ВК"},
            {"name": "Именинник Елизавета", "role": "Продюсер образовательных событий", "tags": "#установки #ЛОМ #большие_встречи", "phone": "89377022672", "channel": "вк/мах"},
            {"name": "Майорова Валерия", "role": "Стажёр продюсера", "tags": "#установки #ЛОМ", "phone": "89025437770", "channel": "ВК/MAX/ТГ"},
            {"name": "Пашкевич Ксения", "role": "Контракты + отчёты", "tags": "#контракты #отчеты #смета", "phone": "89062147147", "channel": "ТГ/ВК"},
            {"name": "Штепа Иван", "role": "Итоговые продукты Форума", "tags": "#отчеты #продукты #результат", "phone": "89506788919", "channel": ""},
            {"name": "Некрасова Полина", "role": "Администратор чат-бота", "tags": "#чат-бот", "phone": "89950549455", "channel": "ТГ/ВК"},
            {"name": "Андреевских Александр", "role": "Менеджер МТО", "tags": "#сильные_мужчины", "phone": "89922009613", "channel": ""},
            {"name": "Колодкин Денис", "role": "Менеджер МТО", "tags": "#сильные_мужчины", "phone": "89223418958", "channel": ""},
        ],
    },
    {
        "dept": "Отдел атмосферных программ и церемоний",
        "color": "#45B7D1",
        "people": [
            {"name": "Мамаева Александра Андреевна", "role": "Руководитель отдела", "tags": "#церемонии #внеучебка #атмосфера #приколы #ктохедлайнер", "phone": "89519319237", "channel": "везде"},
            {"name": "Прусс Никита", "role": "Экскурсии, зарядки", "tags": "#атмосфера", "phone": "89316145123", "channel": "мах"},
            {"name": "Конторина Ольга", "role": "Эксперты/исполнители по блокам", "tags": "#атмосфера", "phone": "89003493028", "channel": "мах"},
            {"name": "Легензова Анастасия", "role": "Креативы, вечерки", "tags": "#атмосфера", "phone": "89247046964", "channel": "через Сашу Мамаеву"},
            {"name": "Черемных Александра", "role": "Документы, отчёты, договоры", "tags": "#атмосфера", "phone": "89526427433", "channel": "через Сашу Мамаеву"},
            {"name": "Белоцерковская Дарья", "role": "Церемонии: режиссёр", "tags": "#церемонии", "phone": "79173027082", "channel": "через Сашу Мамаеву"},
            {"name": "Кузнецов Вячеслав", "role": "Церемонии: операционный директор", "tags": "#церемонии", "phone": "79878258831", "channel": "через Сашу Мамаеву"},
            {"name": "Архипов Вячеслав", "role": "Церемонии: креативный директор", "tags": "#церемонии", "phone": "79053885529", "channel": "через Сашу Мамаеву"},
            {"name": "Ефимов Александр", "role": "Церемонии: технический директор", "tags": "#церемонии", "phone": "79172031800", "channel": "через Сашу Мамаеву"},
        ],
    },
    {
        "dept": "Техническо-инженерный отдел / САХСО",
        "color": "#96CEB4",
        "people": [
            {"name": "Леонов Александр Сергеевич", "role": "Площадка, МЧС, охрана", "tags": "", "phone": "89969593415", "channel": ""},
            {"name": "Обернихина Екатерина Алексеевна", "role": "Специалист по АХД", "tags": "", "phone": "89097822228", "channel": "Мах/звонок"},
            {"name": "Морозов Антон Сергеевич", "role": "Заведующий хозяйством", "tags": "", "phone": "", "channel": ""},
            {"name": "Байдураев Иван Михайлович", "role": "Системный администратор", "tags": "", "phone": "89052467015", "channel": "MAX/Звонки/TG"},
            {"name": "Борискин Иван Олегович", "role": "Специалист по АХД", "tags": "", "phone": "", "channel": ""},
        ],
    },
    {
        "dept": "Служба комплексного сопровождения",
        "color": "#DDA0DD",
        "people": [
            {"name": "Поддубная Екатерина Романовна", "role": "Руководитель службы", "tags": "#протокол #гости #логистика #проживание", "phone": "89114642021", "channel": "звонок"},
            {"name": "Бондарчук Анна", "role": "Руководитель сопровождения гостей", "tags": "", "phone": "", "channel": ""},
            {"name": "Миллер Анастасия", "role": "Куратор партнёрских интеграций", "tags": "", "phone": "89098411898", "channel": "Звонок/мах/тг"},
            {"name": "Соколова Ольга", "role": "Мастера, кураторы, эксперты", "tags": "#эксперты", "phone": "89062327334", "channel": "Макс/Телеграмм"},
            {"name": "Колесник Анастасия", "role": "Эксперты + сопровождение", "tags": "#эксперты", "phone": "89114987270", "channel": ""},
            {"name": "Орлова Виолетта", "role": "Авиалогистика", "tags": "", "phone": "89217117675", "channel": "Звонки/Макс/ТГ"},
            {"name": "Изотова Катя", "role": "Проживание, логистика", "tags": "", "phone": "89500552288", "channel": "Тг/макс"},
            {"name": "Бусень Ксюша", "role": "Логистика по КО", "tags": "", "phone": "89022525790", "channel": "Звонки/макс/тг"},
            {"name": "Катанова Ксюша", "role": "Питание в экспертном шатре", "tags": "", "phone": "89270799914", "channel": "макс"},
            {"name": "Камаева Алина Рашидовна", "role": "Партнёры, гости", "tags": "#партнеры", "phone": "89510965453", "channel": ""},
            {"name": "Чудайкина Татьяна", "role": "Визажист", "tags": "", "phone": "89634330629", "channel": ""},
            {"name": "Меньшикова Полина", "role": "Почётные гости", "tags": "", "phone": "89829068508", "channel": "тг/вк/звонки"},
            {"name": "Гудошников Александр", "role": "Почётные гости", "tags": "", "phone": "89053399626", "channel": "Звонки/Макс/ВК/ТГ"},
            {"name": "Смышляев Виталий Александрович", "role": "Гости", "tags": "", "phone": "79097311913", "channel": ""},
            {"name": "Тарасова Полина Александровна", "role": "Гости", "tags": "", "phone": "79527917960", "channel": "тг/макс"},
            {"name": "Никешина Анастасия", "role": "Встреча гостей в аэропорту", "tags": "", "phone": "89506782659", "channel": "макс"},
            {"name": "Ким Малике", "role": "Встреча гостей в аэропорту", "tags": "", "phone": "89114918758", "channel": "вк/макс"},
        ],
    },
    {
        "dept": "Служба по работе с участниками и аккредитации",
        "color": "#F7DC6F",
        "people": [
            {"name": "Асаналиева Вероника Владиславовна", "role": "Руководитель службы", "tags": "регистрация, аккредитация, волонтёры", "phone": "89052445429", "channel": ""},
            {"name": "Семенова Виктория Владимировна", "role": "Специалист (сообщества, сервисы)", "tags": "", "phone": "89053196720", "channel": ""},
            {"name": "Моин Андрей Константинович", "role": "Специалист (общий контур)", "tags": "", "phone": "89114617624", "channel": ""},
            {"name": "Медведева Нина Дмитриевна", "role": "Руководитель центра аккредитации", "tags": "", "phone": "89114712227", "channel": ""},
            {"name": "Малинник Рената Ивановна", "role": "Руководитель волонтёрского корпуса", "tags": "", "phone": "89527923998", "channel": ""},
            {"name": "Игнатенко Анастасия Михайловна", "role": "Закупка и реализация мерча", "tags": "", "phone": "89002797077", "channel": "тг/звонок"},
            {"name": "Джафарова Амина Афгановна", "role": "Коммуникации (каналы и чаты)", "tags": "", "phone": "89052400121", "channel": ""},
            {"name": "Поддубный Александр Романович", "role": "Специалист", "tags": "", "phone": "89114568917", "channel": ""},
            {"name": "Симонова Анжелика Евгеньевна", "role": "Специалист (мерч)", "tags": "", "phone": "89222044253", "channel": ""},
        ],
    },
    {
        "dept": "Медиацентр",
        "color": "#BB8FCE",
        "people": [
            {"name": "Свистунова Александра Михайловна", "role": "Руководитель медиацентра", "tags": "пресс-релизы, взаимодействие со СМИ, брендирование", "phone": "89114782095", "channel": ""},
            {"name": "Столбов Александр Евгеньевич", "role": "Руководитель контент-центра", "tags": "соцсети, фото и видео", "phone": "89585853345", "channel": ""},
            {"name": "Богданова Александра", "role": "Пресс-секретарь", "tags": "взаимодействие со СМИ, пресс-релизы", "phone": "79114539177", "channel": ""},
            {"name": "Корепина Полина", "role": "Менеджер медиацентра", "tags": "", "phone": "79216173264", "channel": ""},
            {"name": "Эллер Дарья", "role": "Выпускающий SMM-менеджер", "tags": "", "phone": "", "channel": ""},
            {"name": "Бобрышева Екатерина", "role": "SMM-менеджер", "tags": "", "phone": "", "channel": ""},
            {"name": "Волошина Александра", "role": "SMM-менеджер", "tags": "", "phone": "", "channel": ""},
            {"name": "Тырсикова Влада", "role": "Графический дизайнер", "tags": "", "phone": "", "channel": ""},
            {"name": "Горелов Иван", "role": "Графический дизайнер", "tags": "", "phone": "", "channel": ""},
            {"name": "Семенова София", "role": "Графический дизайнер", "tags": "", "phone": "", "channel": ""},
            {"name": "Носков Никита", "role": "Бильд-редактор", "tags": "", "phone": "", "channel": ""},
            {"name": "Казанков Илья", "role": "Фотограф", "tags": "", "phone": "", "channel": ""},
            {"name": "Шорохов Дмитрий", "role": "Фотограф", "tags": "", "phone": "", "channel": ""},
            {"name": "Скляревский Никита", "role": "Фотограф", "tags": "", "phone": "", "channel": ""},
            {"name": "Волошин Глеб", "role": "Старший видеограф", "tags": "", "phone": "", "channel": ""},
            {"name": "Золоторёв Денис", "role": "Специалист монтажа", "tags": "", "phone": "", "channel": ""},
            {"name": "Герасименко Антон", "role": "Оператор", "tags": "", "phone": "", "channel": ""},
            {"name": "Косолапов Михаил", "role": "Оператор", "tags": "", "phone": "", "channel": ""},
            {"name": "Жилов Амин", "role": "Оператор", "tags": "", "phone": "", "channel": ""},
            {"name": "Асланянц Максим", "role": "Клипмейкер", "tags": "", "phone": "", "channel": ""},
            {"name": "Бурля Алина", "role": "Клипмейкер", "tags": "", "phone": "", "channel": ""},
            {"name": "Локшина Екатерина", "role": "Креатор", "tags": "", "phone": "", "channel": ""},
            {"name": "Антипичев Илья", "role": "Продюсер студии", "tags": "", "phone": "", "channel": ""},
            {"name": "Лесникова Диана", "role": "Менеджер студии", "tags": "", "phone": "89114890893", "channel": ""},
        ],
    },
    {
        "dept": "Отдел правового сопровождения",
        "color": "#85C1E9",
        "people": [
            {"name": "Бондарева Ольга Олеговна", "role": "Руководитель отдела", "tags": "", "phone": "", "channel": ""},
            {"name": "Нугаева Светлана Викторовна", "role": "Секретарь-делопроизводитель", "tags": "", "phone": "", "channel": ""},
            {"name": "Федоров Дмитрий Сергеевич", "role": "Специалист по закупкам", "tags": "", "phone": "", "channel": ""},
            {"name": "Авдеева Юлия Игоревна", "role": "Ведущий юрист по договорной работе", "tags": "", "phone": "", "channel": ""},
            {"name": "Потёмкин Антон Андреевич", "role": "Ведущий юрист", "tags": "", "phone": "", "channel": ""},
        ],
    },
    {
        "dept": "Финансово-экономический отдел",
        "color": "#98D8C8",
        "people": [
            {"name": "Быханова Юлия Николаевна", "role": "Руководитель отдела", "tags": "", "phone": "", "channel": ""},
            {"name": "Вьюновец Елена Евгеньевна", "role": "Заместитель — замглавного бухгалтера", "tags": "", "phone": "", "channel": ""},
            {"name": "Никитина Наталья Викторовна", "role": "Бухгалтер", "tags": "", "phone": "", "channel": ""},
            {"name": "Сахарова Антонина Анатольевна", "role": "Бухгалтер", "tags": "", "phone": "", "channel": ""},
            {"name": "Рязанова Светлана Андреевна", "role": "Специалист по кадрам", "tags": "", "phone": "", "channel": ""},
            {"name": "Ерёменко Анастасия Эриковна", "role": "Ведущий экономист", "tags": "", "phone": "", "channel": ""},
        ],
    },
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


def build_figure(data, visible_services=None):
    if visible_services is None:
        visible_services = data["services"]
    color_map = get_color_map(data["services"])
    traces = {}
    for v in data["volunteers"]:
        svc = v["service"]
        if svc not in visible_services:
            continue
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
        uirevision="stable",
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


def build_volunteer_list(data, query=None, visible_services=None):
    color_map = get_color_map(data["services"])
    all_services = data["services"]
    if visible_services is None:
        visible_services = all_services

    filtered = []
    for i, v in enumerate(data["volunteers"]):
        if v["service"] not in visible_services:
            continue
        if query:
            q = query.strip().lower()
            if q and q not in v["handle"].lower() and q not in v.get("name", "").lower():
                continue
        filtered.append((i, v))

    if not filtered:
        return [html.P("Нет участников", style={"color": "rgba(255,255,255,0.6)", "fontSize": "13px", "margin": "0"})]

    items = []
    for svc in all_services:
        if svc not in visible_services:
            continue
        group = [(i, v) for i, v in filtered if v["service"] == svc]
        if not group:
            continue
        color = color_map.get(svc, "#888")
        items.append(html.Div([
            html.Span(svc, style={
                "fontSize": "11px", "color": "white", "background": color,
                "padding": "2px 8px", "borderRadius": "10px",
            }),
            html.Span(f"  {len(group)}", style={"fontSize": "12px", "color": "rgba(255,255,255,0.7)"}),
        ], style={"marginTop": "10px", "marginBottom": "4px"}))

        for i, v in group:
            items.append(html.Div([
                html.Div([
                    html.Span(v["handle"], style={"fontWeight": "bold", "color": color, "fontSize": "13px"}),
                    html.Span(" · " + ", ".join(v["cities"]), style={"color": "#666", "fontSize": "12px"}),
                ], style={"flex": "1", "minWidth": "0", "overflow": "hidden", "textOverflow": "ellipsis"}),
                html.Button("📍", id={"type": "vol-focus", "index": i},
                            n_clicks=0, title="Показать на карте", className="btn-icon"),
                html.Button("✏️", id={"type": "btn-edit", "index": i},
                            n_clicks=0, title="Редактировать", className="btn-icon"),
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
        photo_el = (html.Img(src=photo, className="vol-photo") if photo
                    else html.Div("📷", className="vol-photo-placeholder"))
        del_btn = ([html.Button("Удалить", id={"type": "btn-del-photo", "index": i},
                                n_clicks=0, className="btn-photo-sm btn-photo-del")] if photo else [])
        items.append(html.Div([
            html.Div(photo_el, style={"marginRight": "10px", "flexShrink": "0"}),
            html.Div([
                html.Div([
                    html.Span(v["handle"], style={"fontWeight": "bold", "color": color, "fontSize": "13px"}),
                    (html.Span(" " + v["name"], style={"color": "#777", "fontSize": "12px"}) if v.get("name") else ""),
                ]),
                html.Div(", ".join(v["cities"]), style={"color": "#999", "fontSize": "11px", "marginBottom": "4px"}),
                html.Div([
                    dcc.Upload(id={"type": "upload-photo", "index": i},
                               children=html.Button("Изменить" if photo else "+ фото", className="btn-photo-sm"),
                               accept="image/*",
                               style={"display": "inline-block", "marginRight": "4px"}),
                ] + del_btn, style={"display": "flex", "alignItems": "center", "gap": "4px"}),
            ], style={"flex": "1"}),
        ], style={"display": "flex", "alignItems": "center", "padding": "8px 0", "borderBottom": "1px solid #f0f0f0"}))
    return items


def validate_and_geocode(cities):
    """Returns list of failed cities."""
    failed = []
    for city in cities:
        if city not in CITY_COORDS:
            if geocode(city) is None:
                failed.append(city)
    return failed


def build_staff_section():
    cards = []
    for dept in ORG_STRUCTURE:
        color = dept["color"]
        rows = []
        for i, p in enumerate(dept["people"]):
            is_head = (i == 0)
            phone_el = (html.A(
                f"📞 {p['phone']}",
                href=f"tel:{p['phone'].replace(' ', '')}",
                className="staff-phone",
            ) if p["phone"] else None)
            meta = " · ".join(filter(None, [p["channel"]] + (
                [p["tags"]] if p["tags"] and is_head else []
            )))
            rows.append(html.Div([
                html.Div([
                    html.Span(p["name"], className="staff-name" + (" staff-head" if is_head else ""),
                              style={"color": color if is_head else "#333"}),
                    (html.Span(f" — {p['role']}", className="staff-role") if p["role"] else ""),
                ]),
                html.Div([
                    phone_el,
                    (html.Span(meta, className="staff-meta") if meta else None),
                ], className="staff-contact") if (phone_el or meta) else None,
                (html.Div(p["tags"], className="staff-tags") if p["tags"] and not is_head else None),
            ], className="staff-row"))

        cards.append(html.Div([
            html.Div(dept["dept"], className="dept-header", style={"background": color}),
            html.Div(rows, className="dept-body"),
        ], className="dept-card"))

    return html.Div([
        html.H2("Штаб Форума ШУМ 2026", className="staff-title"),
        html.Div(cards, className="dept-grid"),
    ], className="staff-section")


def parse_import(text):
    """Parse pasted text into volunteer dicts. Returns (volunteers, errors)."""
    volunteers, errors = [], []
    for i, line in enumerate(text.strip().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sep = "|" if "|" in line else ","
        parts = [p.strip() for p in line.split(sep)]
        if len(parts) == 3:
            handle, cities_str, service = parts
            name = ""
        elif len(parts) >= 4:
            handle, name, cities_str, service = parts[0], parts[1], parts[2], parts[3]
        else:
            errors.append(f"Строка {i}: нужно handle | город | служба")
            continue
        if not handle.startswith("@"):
            handle = "@" + handle
        cities = [c.strip() for c in cities_str.split(",") if c.strip()]
        if not cities:
            errors.append(f"Строка {i}: не указаны города")
            continue
        volunteers.append({"handle": handle, "name": name, "cities": cities,
                           "service": service, "photo": None})
    return volunteers, errors


# ── приложение ────────────────────────────────────────────────────────────────

app = dash.Dash(__name__, title="Форум ШУМ 2026 — Карта команды",
                suppress_callback_exceptions=True)
server = app.server

app.layout = html.Div(className="page-wrap", children=[
    dcc.Store(id="data-store", data=INITIAL_DATA),
    dcc.Store(id="selected-city", data=None),
    dcc.Store(id="editing-idx", data=None),

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

            # ── карточка города ──
            html.Div(id="city-detail", className="card city-detail", style={"display": "none"}, children=[
                html.Div([
                    html.Span(id="city-detail-title",
                              style={"fontWeight": "700", "fontSize": "15px", "color": "#4a4a6a"}),
                    html.Button("×", id="btn-close-detail", className="btn-delete"),
                ], style={"display": "flex", "justifyContent": "space-between",
                          "alignItems": "center", "marginBottom": "8px"}),
                html.Div(id="city-detail-content"),
            ]),

            # ── поиск ──
            dcc.Input(id="search-query", placeholder="🔍 Поиск по имени / @handle",
                      className="field search-field",
                      debounce=True,
                      style={"width": "100%", "marginBottom": "6px"}),

            # ── фильтр по службам ──
            html.Div(className="card filter-card", children=[
                html.P("Фильтр", style={"margin": "0 0 6px", "fontSize": "12px",
                                         "color": "#4a4a6a", "fontWeight": "600"}),
                dcc.Checklist(
                    id="filter-chips",
                    options=[{"label": s, "value": s} for s in SERVICES],
                    value=list(SERVICES),
                    className="filter-chips",
                    labelStyle={"display": "inline-flex", "alignItems": "center",
                                "marginRight": "6px", "marginBottom": "4px",
                                "cursor": "pointer", "fontSize": "11px"},
                    inputStyle={"marginRight": "3px"},
                ),
            ]),

            # ── список участников ──
            html.Div(style={"marginBottom": "14px"}, children=[
                html.P("Участники", className="vol-section-title"),
                html.Div(id="volunteer-list"),
            ]),

            # ── редактирование ──
            html.Div(id="edit-panel", className="card", style={"display": "none"}, children=[
                html.H3("Редактировать"),
                dcc.Input(id="edit-handle", placeholder="@telegram",
                          className="field", style={"width": "100%"}),
                dcc.Input(id="edit-name", placeholder="Имя (необязательно)",
                          className="field", style={"width": "100%"}),
                dcc.Input(id="edit-city-1", placeholder="Город 1",
                          className="field",
                          style={"width": "100%", "marginBottom": "8px"}),
                dcc.Input(id="edit-city-2", placeholder="Город 2",
                          className="field",
                          style={"width": "100%", "marginBottom": "8px"}),
                dcc.Input(id="edit-city-3", placeholder="Город 3",
                          className="field",
                          style={"width": "100%", "marginBottom": "8px"}),
                dcc.Dropdown(id="edit-service", placeholder="Служба",
                             style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Div([
                    html.Button("Сохранить", id="btn-save-edit", n_clicks=0,
                                className="btn btn-primary", style={"width": "48%", "marginRight": "4%"}),
                    html.Button("Отмена", id="btn-cancel-edit", n_clicks=0,
                                className="btn btn-green", style={"width": "48%"}),
                ], style={"display": "flex"}),
                html.Div(id="msg-edit", className="msg"),
            ]),

            # ── добавление ──
            html.Div(id="add-panel", className="card", children=[
                html.H3("Добавить участника"),
                dcc.Input(id="in-handle", placeholder="@telegram",
                          className="field", style={"width": "100%"}),
                dcc.Input(id="in-name", placeholder="Имя (необязательно)",
                          className="field", style={"width": "100%"}),
                dcc.Input(id="in-city-1", placeholder="Город 1 (обязательно)",
                          className="field",
                          style={"width": "100%", "marginBottom": "8px"}),
                dcc.Input(id="in-city-2", placeholder="Город 2",
                          className="field",
                          style={"width": "100%", "marginBottom": "8px"}),
                dcc.Input(id="in-city-3", placeholder="Город 3",
                          className="field",
                          style={"width": "100%", "marginBottom": "8px"}),
                dcc.Dropdown(id="in-service", placeholder="Служба",
                             style={"marginBottom": "8px", "fontSize": "13px"}),
                dcc.Upload(id="in-photo",
                           children=html.Div(id="in-photo-label", children="📷 Прикрепить фото"),
                           accept="image/*", className="upload-photo-input"),
                html.Button("Добавить", id="btn-add-volunteer",
                            n_clicks=0, className="btn btn-primary"),
                html.Div(id="msg-volunteer", className="msg"),
            ]),

            # ── добавить службу ──
            html.Div(className="card", children=[
                html.H3("Добавить службу"),
                dcc.Input(id="in-service-name", placeholder="Название службы",
                          className="field", style={"width": "100%"}),
                html.Button("Добавить службу", id="btn-add-service",
                            n_clicks=0, className="btn btn-green"),
                html.Div(id="msg-service", className="msg"),
            ]),

            # ── импорт ──
            html.Details(className="card import-details", children=[
                html.Summary("📥 Импорт участников"),
                html.Div([
                    html.P("Формат — по одному на строку:", className="import-hint"),
                    html.Code("@handle | Имя | Город1, Город2 | Служба",
                              className="import-hint-code"),
                    html.P("Имя необязательно, тогда 3 поля через |", className="import-hint"),
                    dcc.Textarea(id="import-text", placeholder="Вставьте данные...",
                                 style={"width": "100%", "height": "90px", "fontSize": "12px",
                                        "border": "1px solid #ddd", "borderRadius": "8px",
                                        "padding": "6px", "resize": "vertical",
                                        "marginTop": "4px"}),
                    html.Button("Импортировать", id="btn-import",
                                n_clicks=0, className="btn btn-primary",
                                style={"marginTop": "6px"}),
                    html.Div(id="msg-import", className="msg"),
                ], style={"marginTop": "8px"}),
            ]),
        ]),
    ]),

    build_staff_section(),
])


# ── callbacks ─────────────────────────────────────────────────────────────────

@app.callback(
    Output("in-service", "options"),
    Output("edit-service", "options"),
    Input("data-store", "data"),
)
def update_service_options(data):
    opts = [{"label": s, "value": s} for s in data["services"]]
    return opts, opts


@app.callback(
    Output("filter-chips", "options"),
    Output("filter-chips", "value"),
    Input("data-store", "data"),
    State("filter-chips", "value"),
)
def update_filter_chips(data, current_value):
    services = data["services"]
    opts = [{"label": s, "value": s} for s in services]
    if current_value is None:
        return opts, services
    existing = set(current_value)
    new_value = list(current_value) + [s for s in services if s not in existing]
    return opts, new_value


@app.callback(
    Output("map-graph", "figure"),
    Input("data-store", "data"),
    Input("filter-chips", "value"),
)
def refresh_map(data, visible_services):
    return build_figure(data, visible_services)


@app.callback(
    Output("volunteer-list", "children"),
    Input("data-store", "data"),
    Input("search-query", "value"),
    Input("filter-chips", "value"),
)
def refresh_list(data, query, visible_services):
    return build_volunteer_list(data, query, visible_services)


# ── добавить службу ───────────────────────────────────────────────────────────

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


# ── удалить участника ─────────────────────────────────────────────────────────

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


# ── добавить участника ────────────────────────────────────────────────────────

@app.callback(
    Output("in-photo-label", "children"),
    Input("in-photo", "contents"),
    Input("in-photo", "filename"),
    prevent_initial_call=True,
)
def update_photo_label(contents, filename):
    return f"✓ {filename}" if contents else "📷 Прикрепить фото"


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
    failed = validate_and_geocode(cities)
    if failed:
        return (data, f"Не удалось найти на карте: {', '.join(failed)}",
                handle, name, city1, city2, city3, service, photo)
    entry = {"handle": handle, "name": (name or "").strip(),
             "cities": cities, "service": service, "photo": photo}
    data = dict(data)
    data["volunteers"] = data["volunteers"] + [entry]
    return data, "", "", "", "", "", "", None, None


# ── редактирование ────────────────────────────────────────────────────────────

@app.callback(
    Output("editing-idx", "data"),
    Output("data-store", "data", allow_duplicate=True),
    Output("msg-edit", "children"),
    Input({"type": "btn-edit", "index": ALL}, "n_clicks"),
    Input("btn-cancel-edit", "n_clicks"),
    Input("btn-save-edit", "n_clicks"),
    State("edit-handle", "value"),
    State("edit-name", "value"),
    State("edit-city-1", "value"),
    State("edit-city-2", "value"),
    State("edit-city-3", "value"),
    State("edit-service", "value"),
    State("editing-idx", "data"),
    State("data-store", "data"),
    prevent_initial_call=True,
)
def handle_edit(edit_clicks, _cancel, _save,
                handle, name, city1, city2, city3, service, idx, data):
    triggered = dash.callback_context.triggered[0]["prop_id"]

    if "btn-cancel-edit" in triggered:
        return None, data, ""

    if "btn-save-edit" in triggered:
        if idx is None or not handle or not city1 or not service:
            return idx, data, "Заполните обязательные поля"
        handle = handle.strip()
        cities = [c.strip() for c in [city1, city2 or "", city3 or ""] if c.strip()]
        failed = validate_and_geocode(cities)
        if failed:
            return idx, data, f"Не удалось найти: {', '.join(failed)}"
        data = dict(data)
        vols = list(data["volunteers"])
        vols[idx] = {**vols[idx], "handle": handle, "name": (name or "").strip(),
                     "cities": cities, "service": service}
        data["volunteers"] = vols
        return None, data, ""

    if "btn-edit" in triggered:
        if not any(edit_clicks):
            return dash.no_update, dash.no_update, dash.no_update
        edit_idx = json.loads(triggered.split(".")[0])["index"]
        return edit_idx, data, ""

    return dash.no_update, dash.no_update, dash.no_update


@app.callback(
    Output("edit-panel", "style"),
    Output("add-panel", "style"),
    Output("edit-handle", "value"),
    Output("edit-name", "value"),
    Output("edit-city-1", "value"),
    Output("edit-city-2", "value"),
    Output("edit-city-3", "value"),
    Output("edit-service", "value"),
    Input("editing-idx", "data"),
    State("data-store", "data"),
)
def show_edit_panel(idx, data):
    if idx is None:
        return {"display": "none"}, {"display": "block"}, "", "", "", "", "", None
    v = data["volunteers"][idx]
    cities = v.get("cities", [])
    return (
        {"display": "block"}, {"display": "none"},
        v["handle"], v.get("name", ""),
        cities[0] if len(cities) > 0 else "",
        cities[1] if len(cities) > 1 else "",
        cities[2] if len(cities) > 2 else "",
        v["service"],
    )


# ── карточка города ───────────────────────────────────────────────────────────

@app.callback(
    Output("selected-city", "data"),
    Input("map-graph", "clickData"),
    Input("btn-close-detail", "n_clicks"),
    Input({"type": "vol-focus", "index": ALL}, "n_clicks"),
    State("data-store", "data"),
    prevent_initial_call=True,
)
def update_selected_city(click_data, _close, focus_clicks, data):
    triggered = dash.callback_context.triggered[0]["prop_id"]
    if "btn-close-detail" in triggered:
        return None
    if "vol-focus" in triggered:
        if not any(focus_clicks):
            return dash.no_update
        idx = json.loads(triggered.split(".")[0])["index"]
        cities = data["volunteers"][idx].get("cities", []) if idx < len(data["volunteers"]) else []
        return cities[0] if cities else None
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


# ── импорт ────────────────────────────────────────────────────────────────────

@app.callback(
    Output("data-store", "data", allow_duplicate=True),
    Output("msg-import", "children"),
    Output("import-text", "value"),
    Input("btn-import", "n_clicks"),
    State("import-text", "value"),
    State("data-store", "data"),
    prevent_initial_call=True,
)
def import_volunteers(n, text, data):
    if not text or not text.strip():
        return data, "Вставьте данные", text

    volunteers, errors = parse_import(text)
    if not volunteers:
        return data, "Не удалось распознать ни одной записи. " + "; ".join(errors), text

    # geocode all cities, collect failures
    all_failed = []
    valid = []
    for v in volunteers:
        failed = validate_and_geocode(v["cities"])
        if failed:
            all_failed.append(f"{v['handle']}: {', '.join(failed)}")
        else:
            valid.append(v)

    # auto-add new services
    data = dict(data)
    existing_services = set(data["services"])
    new_services = [v["service"] for v in valid if v["service"] not in existing_services]
    if new_services:
        data["services"] = data["services"] + list(dict.fromkeys(new_services))

    data["volunteers"] = data["volunteers"] + valid

    parts = [f"Добавлено: {len(valid)}"]
    if errors:
        parts.append(f"Ошибки формата: {len(errors)}")
    if all_failed:
        parts.append(f"Не найдены города: {'; '.join(all_failed)}")
    msg = " · ".join(parts)
    return data, msg, ""


if __name__ == "__main__":
    app.run(debug=True, port=8051)
