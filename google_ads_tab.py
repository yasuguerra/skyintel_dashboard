# google_ads_tab.py  – versión multi-subtab (corregido)

from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import datetime as _dt
import dash, dash_bootstrap_components as dbc
import pandas as pd, plotly.express as px, plotly.graph_objects as go
from dash import dcc, html, Input, Output, State, dash_table
from dash.dash_table import FormatTemplate               # solo templates
import google_ads_api as gads
from layout_components import create_ai_insight_card


# ─────────── Helpers ───────────
def _kpi_card(title, value, delta, icon="") -> dbc.Card:
    color  = "success" if isinstance(delta,(int,float)) and delta>=0 else "danger"
    prefix = "+" if isinstance(delta,(int,float)) and delta>=0 else ""
    return dbc.Card(
        dbc.CardBody([
            html.Div([
                html.Span(title, className="text-muted small me-1"),
                html.I(className=f"{icon} text-muted") if icon else None,
            ], className="d-flex align-items-center"),
            html.H3(value, className="mb-0 fw-bold"),
            html.Small(f"{prefix}{delta:.1f}% vs. periodo previo",
                       className=f"text-{color}"),
        ]), className="shadow-sm rounded-3")


def _date_picker() -> dcc.DatePickerRange:
    today = _dt.date.today()
    return dcc.DatePickerRange(
        id="gads-date-range",
        min_date_allowed=today - _dt.timedelta(days=365),
        max_date_allowed=today,
        start_date=today - _dt.timedelta(days=30),
        end_date=today,
        display_format="YYYY-MM-DD",
        className="me-2",
    )


# ─────────── Layout factory ───────────
def get_google_ads_tab(app: dash.Dash) -> dbc.Container:
    return dbc.Container(
        [
            dcc.Store(id="gads-store"),
            dbc.Row(
                [
                    dbc.Col(_date_picker(), width="auto"),
                    dbc.Col(dbc.Button("Actualizar 🔄", id="gads-refresh",
                                       color="primary"), width="auto"),
                    dbc.Col(html.Div(id="gads-last-updated",
                                     className="small text-muted"), width="auto"),
                ],
                className="gy-2 my-2",
            ),
            dcc.Tabs(
                id="gads-subtabs", value="overview", children=[
                    dcc.Tab(label="Desempeño General 🚀", value="overview"),
                    dcc.Tab(label="Segmentación & Geo 🌍", value="geo"),
                    dcc.Tab(label="Keywords & Campañas 🔑", value="kw"),
                ],
                className="mb-3",
            ),
            html.Div(id="gads-subtab-content"),
        ],
        fluid=True, className="pt-3",
    )

# ─────────── Callbacks ───────────

# 1) Descarga de datos
@dash.callback(
    Output("gads-store", "data"),
    Output("gads-last-updated", "children"),
    Input("gads-refresh", "n_clicks"),
    State("gads-date-range", "start_date"),
    State("gads-date-range", "end_date"),
    prevent_initial_call=True,
)
def _fetch_ads_data(_, start_date, end_date):
    start, end = map(_dt.date.fromisoformat, (start_date, end_date))

    # Empaquetamos cada función con sus args
    jobs = {
        "overview":  partial(gads.fetch_overview,  start, end),
        "daily":     partial(gads.fetch_daily_performance, start, end),
        "campaigns": partial(gads.fetch_campaign_performance, start, end),
        "geo":       partial(gads.fetch_geo_performance, start, end),
        "devices":   partial(gads.fetch_device_performance, start, end),
        "ages":      partial(gads.fetch_age_performance, start, end),
        "genders":   partial(gads.fetch_gender_performance, start, end),
        "adgroups":  partial(gads.fetch_adgroup_performance, start, end),
        "keywords":  partial(gads.fetch_keyword_performance, start, end),
    }

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = {k: pool.submit(f).result() for k, f in jobs.items()}

    # Serializa sólo los grandes
    data = {
        "overview": results["overview"],
        "daily":     results["daily"].to_dict("records"),
        "campaigns": results["campaigns"].to_dict("records"),
        "geo":       results["geo"].to_dict("records"),
        "devices":   results["devices"].to_dict("records"),
        "ages":      results["ages"].to_dict("records"),
        "genders":   results["genders"].to_dict("records"),
        "adgroups":  results["adgroups"].to_dict("records"),
        "keywords":  results["keywords"].to_dict("records"),
    }
    return data, _dt.datetime.now().strftime("Actualizado %Y-%m-%d %H:%M:%S")


# 2) Render del sub-tab
@dash.callback(
    Output("gads-subtab-content", "children"),
    Input("gads-subtabs", "value"),
    Input("gads-store",   "data"),
)
def _render_subtab(tab, data):
    if not data:
        return dbc.Alert("Haz clic en «Actualizar» para cargar datos.", color="info")

    # 2.1 Desempeño General
    if tab == "overview":
        o = data["overview"]
        cards = dbc.Row([
            dbc.Col(_kpi_card("Impresiones", f"{o['impr']:,}",  o['delta_impr'],   "bi bi-eye"), md=2),
            dbc.Col(_kpi_card("Clicks",      f"{o['clicks']:,}",o['delta_clicks'], "bi bi-mouse"), md=2),
            dbc.Col(_kpi_card("CTR",         f"{o['ctr']:.2f}%",o['delta_ctr'],    "bi bi-activity"), md=2),
            dbc.Col(_kpi_card("Conv.",       f"{o['conv']:.2f}",o['delta_conv'],   "bi bi-check2-circle"), md=2),
            dbc.Col(_kpi_card("CPC medio",   f"${o['cpc']:.2f}",o['delta_cpc'],    "bi bi-currency-dollar"), md=2),
            dbc.Col(_kpi_card("ROAS",        f"{o['roas']:.2f}×",o['delta_roas'],  "bi bi-graph-up"), md=2),
        ], className="g-3 mb-4")

        trend = dcc.Graph(
            figure=px.bar(
                pd.DataFrame(data["daily"]), x="date",
                y=["spend","clicks","conversions"],
                barmode="group", title="Tendencia diaria – Spend / Clicks / Conv."
            ), config={"displayModeBar": False}
        )

        funnel = go.Figure(go.Funnel(
            y=["Impresiones","Clicks","Conversión"],
            x=[o["impr"], o["clicks"], o["conv"]],
            textinfo="value+percent previous"
        )).update_layout(title_text="Embudo – Ad Delivery")

        camp_df = pd.DataFrame(data["campaigns"]).sort_values("spend", ascending=False)
        table = dash_table.DataTable(
            data=camp_df.to_dict("records"),
            columns=[{"name": c.capitalize(), "id": c} for c in camp_df.columns],
            page_size=15, sort_action="native",
            style_table={"overflowX":"auto"},
            style_header={"fontWeight":"bold"},
        )

        ia_btn = dbc.Button("Generar reporte IA 🔮", id="gads-ai-btn",
                            color="secondary", className="mt-3")

        return [cards, trend, dcc.Graph(figure=funnel, className="my-4"), table, ia_btn]

    # 2.2 Segmentación & Geo
    if tab == "geo":
        geo_df    = pd.DataFrame(data["geo"])
        device_df = pd.DataFrame(data["devices"])
        age_df    = pd.DataFrame(data["ages"])
        gender_df = pd.DataFrame(data["genders"])

        if geo_df.empty:
            return dbc.Alert("Sin datos geográficos para el rango seleccionado.")

        fig_cities  = px.bar(geo_df.groupby("city", as_index=False)["clicks"]
                             .sum().sort_values("clicks", ascending=False).head(12),
                             x="city", y="clicks", title="Clicks por Ciudad (Top 12)")
        fig_device  = px.pie(device_df, names="device", values="clicks",
                             title="Distribución de Clicks por Dispositivo")
        fig_age     = px.bar(age_df.sort_values("clicks", ascending=False),
                             x="age_range", y="clicks", title="Clicks por Edad")
        fig_gender  = px.pie(gender_df, names="gender", values="clicks",
                             title="Clicks por Género")

        return dbc.Container([
            dbc.Row([
                dbc.Col(dcc.Graph(figure=fig_cities), md=6),
                dbc.Col(dcc.Graph(figure=fig_device), md=6),
            ], className="gy-4"),
            dbc.Row([
                dbc.Col(dcc.Graph(figure=fig_age),    md=6),
                dbc.Col(dcc.Graph(figure=fig_gender), md=6),
            ], className="gy-4"),
        ], fluid=True)

    # 2.3 Keywords & AdGroups
    if tab == "kw":
        kw_df = pd.DataFrame(data["keywords"])
        if kw_df.empty:
            return dbc.Alert("No se hallaron métricas de keywords.")

        agg_kw = (kw_df.groupby("keyword", as_index=False)
                    .agg(clicks=("clicks","sum"), cost=("cost","sum"),
                         conv=("conversions","sum"))
                    .sort_values("clicks", ascending=False).head(20))
        agg_kw["cpc"] = agg_kw.cost / agg_kw.clicks.replace({0: None})

        fig_kw = px.bar(agg_kw, x="keyword", y="clicks",
                        hover_data=["cost","conv","cpc"],
                        title="Top 20 Keywords por Clicks")

        ag_df = pd.DataFrame(data["adgroups"])
        if ag_df.empty:
            table_ag = dbc.Alert("Sin datos de grupos de anuncio.")
            pie_ag   = dbc.Alert("Sin datos.")
        else:
            table_ag = dash_table.DataTable(
                data   = ag_df.to_dict("records"),
                columns=[
                    {"name": "Ad Group",      "id": "ad_group"},
                    {"name": "Clicks",        "id": "clicks",   "type":"numeric"},
                    {"name": "Impr.",         "id": "impr",     "type":"numeric"},
                    {"name": "CTR %",         "id": "ctr",
                     "type":"numeric", "format": FormatTemplate.percentage(2)},
                    {"name": "Avg CPC US$",   "id": "avg_cpc",
                     "type":"numeric", "format": FormatTemplate.money(2)},
                    {"name": "Conv.",         "id": "conv",     "type":"numeric"},
                ],
                page_size=10, sort_action="native",
                style_table={"maxHeight":"300px","overflowY":"auto"},
                style_header={"fontWeight":"bold"},
            )
            pie_ag = px.pie(ag_df.head(10), names="ad_group", values="clicks",
                            title="Participación de Clicks (Top 10 Ad Groups)")

        return [dcc.Graph(figure=fig_kw, className="mb-4"),
                table_ag,
                dcc.Graph(figure=pie_ag, className="mt-4")]


# 3) Agregar tarjeta-IA sin borrar la vista
@dash.callback(
    Output("gads-subtab-content", "children", allow_duplicate=True),
    Input("gads-ai-btn", "n_clicks"),
    State("gads-subtab-content", "children"),
    prevent_initial_call=True,
)
def _inject_ai_report(n_clicks, children):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    return children + [create_ai_insight_card("google_ads", max_tokens=500)]
