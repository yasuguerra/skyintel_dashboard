# callbacks_social.py
# -------------------------------------------------
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from dash import dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc

# --- Dependencias de tu proyecto -----------------
from config import FACEBOOK_ID, INSTAGRAM_ID
from ai import get_openai_response
from layout_components import (
    create_ai_insight_card,
    create_ai_chat_interface,
    add_trendline,
    generate_wordcloud,
)
from data_processing import (
    get_facebook_posts,
    get_instagram_posts,
    process_facebook_posts,
    process_instagram_posts,
)

# -------------------------------------------------
def register_callbacks(app):
    """Registra todos los callbacks de la sección Redes Sociales."""

    # ------------------------------------------------------------------
    #  SUB-TABS: GENERAL, ENGAGEMENT, WORDMAP, TOP POSTS
    # ------------------------------------------------------------------
    @app.callback(
        Output("social-subtabs-content", "children"),
        Input("social-subtabs", "value"),
        State("date-picker", "start_date"),
        State("date-picker", "end_date"),
    )
    def render_social_subtab_content(subtab_sm, start_date, end_date):
        # ---------------- Validación fechas ----------------
        if not start_date or not end_date:
            return html.P("Selecciona un rango de fechas.", className="text-center mt-5")

        sd = pd.to_datetime(start_date).tz_localize(None)
        ed = pd.to_datetime(end_date).tz_localize(None)

        # ---------------- Carga de datos -------------------
        fb_posts_raw = get_facebook_posts(FACEBOOK_ID)
        ig_posts_raw = get_instagram_posts(INSTAGRAM_ID)

        df_fb = process_facebook_posts(fb_posts_raw)
        df_ig = process_instagram_posts(ig_posts_raw)

        # ---------------- Filtro por rango -----------------
        if not df_fb.empty:
            df_fb_f = df_fb[(df_fb["created_time"] >= sd) & (df_fb["created_time"] <= ed)]
            if df_fb_f.empty:  # Si no hay posts en rango, usa todo
                df_fb_f = df_fb.copy()
        else:
            df_fb_f = df_fb

        if not df_ig.empty:
            df_ig_f = df_ig[(df_ig["timestamp"] >= sd) & (df_ig["timestamp"] <= ed)]
            if df_ig_f.empty:
                df_ig_f = df_ig.copy()
        else:
            df_ig_f = df_ig

        # ---------------- Mensaje sin datos ----------------
        default_no_ai = "No hay suficientes datos para un análisis IA."
        no_data_msg = html.Div(
            [
                html.P("No hay datos de redes sociales para el período seleccionado."),
                create_ai_insight_card(f"{subtab_sm}-ai-insight-visible"),
                html.Div(default_no_ai, id=f"{subtab_sm}-ai-insight-data", style={"display": "none"}),
            ]
        )

        # ------------------------------------------------------------------
        #  SUB-TAB 1 · GENERAL
        # ------------------------------------------------------------------
        if subtab_sm == "general_sm":
            if df_fb_f.empty and df_ig_f.empty:
                return no_data_msg

            # compatibilidad con likes_count / comments_count legacy
            likes_fb_col = "likes" if "likes" in df_fb_f.columns else "likes_count"
            comm_fb_col = "comments" if "comments" in df_fb_f.columns else "comments_count"

            metrics_sm = {
                "FB Impresiones": int(df_fb_f["impressions"].sum()) if not df_fb_f.empty else 0,
                "IG Impresiones": int(df_ig_f["impressions"].sum()) if not df_ig_f.empty else 0,
                "IG Alcance": int(df_ig_f["reach"].sum()) if not df_ig_f.empty else 0,
                "IG Interacciones": int(df_ig_f["engagement"].sum()) if not df_ig_f.empty else 0,
                "FB Likes": int(df_fb_f[likes_fb_col].sum()) if not df_fb_f.empty else 0,
                "IG Likes": int(df_ig_f["like_count"].sum()) if not df_ig_f.empty else 0,
                "IG Video Views": int(df_ig_f["video_views"].sum()) if not df_ig_f.empty else 0,
            }

            # ---------- Tendencia impresiones IG ----------
            fig_ig_trend = go.Figure().update_layout(
                title="Tendencia Impresiones Instagram (sin datos suficientes)"
            )
            if not df_ig_f.empty:
                df_tr = (
                    df_ig_f.sort_values("timestamp")
                    .set_index("timestamp")["impressions"]
                    .resample("D")
                    .sum()
                    .reset_index()
                )
                if len(df_tr) > 1:
                    fig_ig_trend = px.line(
                        df_tr,
                        x="timestamp",
                        y="impressions",
                        markers=True,
                        title="Tendencia Impresiones Diarias (Instagram)",
                    )
                    fig_ig_trend = add_trendline(fig_ig_trend, df_tr, "timestamp", "impressions")

            # ---------- Insight IA ----------
            context_gen = f"Métricas generales SM: {metrics_sm}. Tendencia de impresiones IG incluida."
            prompt_gen = (
                "Analiza las métricas generales de Facebook e Instagram. "
                "¿Qué plataforma destaca y en qué métrica? "
                "Diagnostica el rendimiento y sugiere una acción poderosa."
            )
            ai_insight_text = get_openai_response(prompt_gen, context_gen)

            # ---------- Layout ----------
            cards = [
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H5("Facebook", className="card-title text-primary"),
                            html.P(f"Impresiones: {metrics_sm['FB Impresiones']:,}"),
                            html.P(f"Likes: {metrics_sm['FB Likes']:,}"),
                        ]
                    ),
                    className="shadow-sm",
                ),
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H5("Instagram", className="card-title text-danger"),
                            html.P(f"Impresiones: {metrics_sm['IG Impresiones']:,}"),
                            html.P(f"Alcance: {metrics_sm['IG Alcance']:,}"),
                            html.P(f"Interacciones: {metrics_sm['IG Interacciones']:,}"),
                            html.P(f"Likes: {metrics_sm['IG Likes']:,}"),
                            html.P(f"Video Views: {metrics_sm['IG Video Views']:,}"),
                        ]
                    ),
                    className="shadow-sm",
                ),
            ]

            return html.Div(
                [
                    dbc.Row([dbc.Col(c, md=6) for c in cards]),
                    dbc.Row(dbc.Col(dcc.Graph(figure=fig_ig_trend), width=12), className="mt-4"),
                    create_ai_insight_card(
                        "general-sm-ai-insight-visible", title="💡 Diagnóstico y Acción (SM General)"
                    ),
                    html.Div(
                        ai_insight_text,
                        id="general-sm-ai-insight-data",
                        style={"display": "none"},
                    ),
                    create_ai_chat_interface("general_sm"),
                ],
                className="p-3",
            )

        # ------------------------------------------------------------------
        #  SUB-TAB 2 · ENGAGEMENT
        # ------------------------------------------------------------------
        elif subtab_sm == "engagement_sm":
            if df_ig_f.empty or not {"engagement", "reach", "media_type"}.issubset(df_ig_f.columns):
                return no_data_msg

            df_e = df_ig_f.copy()
            df_e["engagement_rate"] = (
                df_e["engagement"] / df_e["reach"].replace(0, np.nan).fillna(1) * 100
            ).fillna(0)

            eng_by_type = (
                df_e.groupby("media_type", as_index=False)
                .agg(
                    total_engagement=("engagement", "sum"),
                    avg_engagement_rate=("engagement_rate", "mean"),
                )
                .sort_values("total_engagement", ascending=False)
            )

            fig_sum = (
                px.bar(
                    eng_by_type,
                    x="media_type",
                    y="total_engagement",
                    color="media_type",
                    text_auto=True,
                    title="Interacciones Totales por Formato (IG)",
                )
                if not eng_by_type.empty
                else go.Figure().update_layout(
                    title="Interacciones Totales por Formato (IG) – Sin datos"
                )
            )

            fig_rate = (
                px.bar(
                    eng_by_type,
                    x="media_type",
                    y="avg_engagement_rate",
                    color="media_type",
                    text_auto=".2f",
                    title="Tasa de Engagement Promedio (%) por Formato (IG)",
                )
                if not eng_by_type.empty
                else go.Figure().update_layout(
                    title="Tasa de Engagement Promedio (IG) – Sin datos"
                )
            )
            if not eng_by_type.empty:
                fig_rate.update_yaxes(ticksuffix="%")

            context_eng = f"Engagement IG por formato:\n{eng_by_type.head().to_string()}"
            prompt_eng = (
                "Analiza el engagement total y la tasa de engagement por formato en Instagram. "
                "¿Qué formato es más efectivo? Diagnostica y sugiere una acción poderosa."
            )
            ai_insight_text = (
                get_openai_response(prompt_eng, context_eng) if not eng_by_type.empty else default_no_ai
            )

            return html.Div(
                [
                    dbc.Row([dbc.Col(dcc.Graph(figure=fig_sum), md=6), dbc.Col(dcc.Graph(figure=fig_rate), md=6)]),
                    create_ai_insight_card(
                        "engagement-sm-ai-insight-visible", title="💡 Diagnóstico y Acción (Engagement IG)"
                    ),
                    html.Div(ai_insight_text, id="engagement-sm-ai-insight-data", style={"display": "none"}),
                    create_ai_chat_interface("engagement_sm"),
                ],
                className="p-3",
            )

        # ------------------------------------------------------------------
        #  SUB-TAB 3 · WORDMAP
        # ------------------------------------------------------------------
        elif subtab_sm == "wordmap_sm":
            if df_fb_f.empty and df_ig_f.empty:
                return no_data_msg

            text_fb = " ".join(df_fb_f["message"].dropna().astype(str)) if "message" in df_fb_f else ""
            text_ig = " ".join(df_ig_f["caption"].dropna().astype(str)) if "caption" in df_ig_f else ""
            combined_text = (text_fb + " " + text_ig).strip()

            wordcloud_src = generate_wordcloud(combined_text)
            ai_insight_text = (
                get_openai_response(
                    "Observando un wordmap de las publicaciones, ¿qué temas general destacan y qué acción tomar?",
                    "Wordmap generado con textos de FB e IG.",
                )
                if wordcloud_src
                else default_no_ai
            )

            return html.Div(
                [
                    html.Img(
                        src=wordcloud_src,
                        style={"width": "100%", "maxWidth": "800px", "display": "block", "margin": "auto"},
                    )
                    if wordcloud_src
                    else html.P("No se pudo generar el Wordmap."),
                    create_ai_insight_card(
                        "wordmap-sm-ai-insight-visible", title="💡 Diagnóstico y Acción (Wordmap)"
                    ),
                    html.Div(ai_insight_text, id="wordmap-sm-ai-insight-data", style={"display": "none"}),
                    create_ai_chat_interface("wordmap_sm"),
                ],
                className="p-3",
            )

        # ------------------------------------------------------------------
        #  SUB-TAB 4 · TOP POSTS
        # ------------------------------------------------------------------
        elif subtab_sm == "top_posts_sm":
            if df_fb_f.empty and df_ig_f.empty:
                return no_data_msg

            # Homogeneizar columnas
            fb_cols = ["id", "message", "created_time", "likes", "comments", "impressions"]
            if "likes_count" in df_fb_f.columns:  # legacy
                df_fb_tmp = df_fb_f.rename(columns={"likes_count": "likes", "comments_count": "comments"})
            else:
                df_fb_tmp = df_fb_f.copy()
            df_fb_std = (
                df_fb_tmp[fb_cols]
                .rename(columns={"message": "content", "created_time": "time"})
                if not df_fb_tmp.empty
                else pd.DataFrame(columns=["id", "content", "time", "likes", "comments", "impressions"])
            )
            df_fb_std["platform"] = "Facebook"

            ig_cols = [
                "id",
                "caption",
                "timestamp",
                "like_count",
                "comments_count",
                "impressions",
                "permalink",
                "media_type",
            ]
            df_ig_std = (
                df_ig_f[ig_cols]
                .rename(
                    columns={
                        "caption": "content",
                        "timestamp": "time",
                        "like_count": "likes",
                        "comments_count": "comments",
                    }
                )
                if not df_ig_f.empty
                else pd.DataFrame(columns=["id", "content", "time", "likes", "comments", "impressions", "permalink", "media_type"])
            )
            df_ig_std["platform"] = "Instagram"

            df_combined = pd.concat([df_fb_std, df_ig_std], ignore_index=True)
            if df_combined.empty:
                return no_data_msg

            df_combined["total_impact"] = (
                df_combined["likes"].fillna(0) + df_combined["comments"].fillna(0) + df_combined["impressions"].fillna(0)
            )
            top_posts = df_combined.sort_values("total_impact", ascending=False).head(10)

            table_rows = []
            for _, r in top_posts.iterrows():
                txt = r["content"] or ""
                txt_short = (txt[:75] + "...") if len(txt) > 75 else txt
                if r["platform"] == "Instagram" and pd.notna(r.get("permalink")):
                    txt_short = f"[{txt_short}]({r['permalink']})"
                table_rows.append(
                    {
                        "Plataforma": r["platform"],
                        "Contenido": txt_short,
                        "Fecha": pd.to_datetime(r["time"]).strftime("%Y-%m-%d") if pd.notna(r["time"]) else "N/A",
                        "Likes": f"{int(r['likes']):,}",
                        "Comentarios": f"{int(r['comments']):,}",
                        "Impresiones": f"{int(r['impressions']):,}",
                        "Impacto": f"{int(r['total_impact']):,}",
                    }
                )

            ai_text_tp = get_openai_response(
                "Analiza las características comunes de los posts con mayor impacto y da una acción concreta.",
                top_posts[["platform", "total_impact"]].head(3).to_string(),
            )

            return html.Div(
                [
                    dash_table.DataTable(
                        data=table_rows,
                        columns=[
                            {"name": c, "id": c, "presentation": "markdown" if c == "Contenido" else "input"}
                            for c in table_rows[0].keys()
                        ],
                        style_table={"overflowX": "auto"},
                        style_cell={
                            "textAlign": "left",
                            "padding": "10px",
                            "whiteSpace": "normal",
                            "height": "auto",
                        },
                        sort_action="native",
                        filter_action="native",
                        page_size=10,
                    ),
                    create_ai_insight_card(
                        "top-posts-sm-ai-insight-visible", title="💡 Diagnóstico y Acción (Top Posts)"
                    ),
                    html.Div(ai_text_tp, id="top-posts-sm-ai-insight-data", style={"display": "none"}),
                    create_ai_chat_interface("top_posts_sm"),
                ],
                className="p-3",
            )

        # ------------------------------------------------------------------
        #  Fallback pestaña no implementada
        # ------------------------------------------------------------------
        return html.P(f"Pestaña SM '{subtab_sm}' no implementada.")

    # ------------------------------------------------------------------
    #  CALLBACKS · Tarjetas de Insight IA (mismo patrón para todas)
    # ------------------------------------------------------------------
    vis_ids = [
        "general-sm-ai-insight-visible",
        "engagement-sm-ai-insight-visible",
        "wordmap-sm-ai-insight-visible",
        "top-posts-sm-ai-insight-visible",
    ]
    data_ids = [
        "general-sm-ai-insight-data",
        "engagement-sm-ai-insight-data",
        "wordmap-sm-ai-insight-data",
        "top-posts-sm-ai-insight-data",
    ]

    for vis, dat in zip(vis_ids, data_ids):

        @app.callback(Output(vis, "children"), Input(dat, "children"))
        def update_ai_card(ai_txt):
            default_msg = "Análisis IA no disponible o datos insuficientes."
            if not ai_txt or not ai_txt.strip():
                return html.P(default_msg)
            generic_insuff = [
                "No hay suficientes datos",
                "No hay datos de engagement",
                "No hay texto en las publicaciones",
            ]
            return html.P(default_msg) if any(msg in ai_txt for msg in generic_insuff) else html.P(ai_txt)

    # ------------------------------------------------------------------
    #  CALLBACKS · AI CHAT por sub-tab
    # ------------------------------------------------------------------
    for tab in ["general_sm", "engagement_sm", "wordmap_sm", "top_posts_sm"]:

        @app.callback(
            Output(f"{tab}-chat-history", "children"),
            Input(f"{tab}-chat-submit", "n_clicks"),
            State(f"{tab}-chat-input", "value"),
            State(f"{tab}-chat-history", "children"),
            State("social-subtabs", "value"),
            prevent_initial_call=True,
        )
        def update_chat(n_clicks, user_input, history, current_tab, tab=tab):
            if not n_clicks or not user_input:
                return history

            if history is None:
                history = []
            elif not isinstance(history, list):
                history = [history]

            context = f"Sub-pestaña SM actual: '{current_tab}'."
            ai_resp = get_openai_response(user_input, context)

            history.extend(
                [
                    html.P([html.B("Tú: ", style={"color": "#007bff"}), user_input]),
                    html.P(
                        [html.B("SkyIntel AI: ", style={"color": "#28a745"}), ai_resp],
                        style={"background": "#f0f0f0", "padding": "8px", "borderRadius": "5px"},
                    ),
                ]
            )
            return history
