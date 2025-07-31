import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State
import pandas as pd

# Dependencias de tu proyecto
from utils import query_ga
from ai import get_openai_response
from config import FACEBOOK_ID, INSTAGRAM_ID
from data_processing import get_facebook_posts, get_instagram_posts, process_facebook_posts, process_instagram_posts
from layout_components import create_ai_insight_card, create_ai_chat_interface
from google_ads_tab import get_google_ads_tab
# Importar los registradores de callbacks específicos
from callbacks_ga import register_callbacks as register_ga_callbacks
from callbacks_social import register_callbacks as register_social_callbacks


def register_web_social_callbacks(app):
    """Registra los callbacks para la sección Web y Redes Sociales."""

    # Create the Google Ads tab layout and register its callbacks once
    google_ads_layout = get_google_ads_tab(app)

    @app.callback(
        Output('main-tabs-content-ws', 'children'),
        Input('main-tabs-selector-ws', 'value'),
        Input('date-picker', 'start_date'),
        Input('date-picker', 'end_date')
    )
    def render_main_tab_content_ws(tab_ws, start_date, end_date):
        if not start_date or not end_date:
            return html.P("Selecciona un rango de fechas.", className="text-center mt-5")
        sd_str, ed_str = pd.to_datetime(start_date).strftime('%Y-%m-%d'), pd.to_datetime(end_date).strftime('%Y-%m-%d')
        start_date_dt = pd.to_datetime(start_date).tz_localize(None)
        end_date_dt = pd.to_datetime(end_date).tz_localize(None)

        default_no_data_ai_text = "No hay suficientes datos para un análisis detallado."

        if tab_ws == 'overview_ws':
            df_acq = query_ga(metrics=['sessions', 'activeUsers', 'conversions'], dimensions=['date'], start_date=sd_str, end_date=ed_str)
            df_acq_src = query_ga(metrics=['conversions'], dimensions=['sessionSourceMedium'], start_date=sd_str, end_date=ed_str)

            summary_data = {"sessions": 0, "users": 0, "conversions": 0, "top_channel": "N/A", "variation": "N/A"}
            if not df_acq.empty:
                summary_data["sessions"] = df_acq['sessions'].sum()
                summary_data["users"] = df_acq['activeUsers'].sum()
                summary_data["conversions"] = df_acq['conversions'].sum()
                if not df_acq_src.empty:
                    summary_data["top_channel"] = df_acq_src.sort_values('conversions', ascending=False).iloc[0]['sessionSourceMedium']
                if len(df_acq) > 1:
                    max_diff = df_acq['sessions'].diff().max()
                    min_diff = df_acq['sessions'].diff().min()
                    if pd.notna(max_diff) and pd.notna(min_diff):
                        summary_data["variation"] = f"Aumento máx. de {max_diff:.0f}" if abs(max_diff) > abs(min_diff) else f"Disminución máx. de {abs(min_diff):.0f}"

            fb_posts = get_facebook_posts(FACEBOOK_ID); ig_posts = get_instagram_posts(INSTAGRAM_ID)
            df_fb = process_facebook_posts(fb_posts); df_ig = process_instagram_posts(ig_posts)
            if not df_fb.empty: df_fb = df_fb[(df_fb['created_time'] >= start_date_dt) & (df_fb['created_time'] <= end_date_dt)]
            if not df_ig.empty: df_ig = df_ig[(df_ig['timestamp'] >= start_date_dt) & (df_ig['timestamp'] <= end_date_dt)]

            summary_data["total_fb_likes"] = df_fb['likes_count'].sum() if not df_fb.empty else 0
            summary_data["total_ig_likes"] = df_ig['like_count'].sum() if not df_ig.empty else 0
            summary_data["total_fb_impressions"] = df_fb['impressions'].sum() if not df_fb.empty else 0
            summary_data["total_ig_impressions"] = df_ig['impressions'].sum() if not df_ig.empty else 0

            context_overview = f"Resumen Negocio: GA(Sesiones={summary_data['sessions']:,}, Conv={summary_data['conversions']:,}, Canal Top={summary_data['top_channel']}). Redes(Likes FB={summary_data['total_fb_likes']:,}, Likes IG={summary_data['total_ig_likes']:,}, Impr. FB={summary_data['total_fb_impressions']:,}, Impr. IG={summary_data['total_ig_impressions']:,})."
            prompt_overview = "Basado en este resumen, ¿cuál es el diagnóstico principal y qué acción poderosa recomiendas para mejorar el panorama general?"
            ai_overview_insight_text = get_openai_response(prompt_overview, context_overview) if summary_data['sessions'] > 0 or summary_data['total_fb_impressions'] > 0 else default_no_data_ai_text

            return html.Div([
                html.H4("Visión General del Negocio 🌐", className="text-center mt-4 mb-4"),
                dbc.Row([
                    dbc.Col(dbc.Card(dbc.CardBody([
                        html.H5("Google Analytics", className="card-title"),
                        html.P(f"Sesiones: {summary_data['sessions']:,.0f}"), html.P(f"Usuarios: {summary_data['users']:,.0f}"),
                        html.P(f"Conversiones: {summary_data['conversions']:,.0f}"), html.P(f"Canal Top: {summary_data['top_channel']}"),
                        html.P(f"Variación Sesiones: {summary_data['variation']}")
                    ]), className="shadow-sm h-100"), md=6, className="mb-3"),
                    dbc.Col(dbc.Card(dbc.CardBody([
                        html.H5("Redes Sociales", className="card-title"),
                        html.P(f"Likes en Facebook: {summary_data['total_fb_likes']:,.0f}"), html.P(f"Likes en Instagram: {summary_data['total_ig_likes']:,.0f}"),
                        html.P(f"Impresiones en Facebook: {summary_data['total_fb_impressions']:,.0f}"), html.P(f"Impresiones en Instagram: {summary_data['total_ig_impressions']:,.0f}"),
                    ]), className="shadow-sm h-100"), md=6, className="mb-3"),
                ]),
                create_ai_insight_card('overview-ws-ai-insight-visible', title="💡 Diagnóstico y Acción Clave (General)"),
                html.Div(ai_overview_insight_text, id='overview-ws-ai-insight-data', style={'display': 'none'})
            ])

        elif tab_ws == 'google_ws':
            return html.Div([
                dcc.Tabs(id='google-subtabs', value='overview_ga', children=[
                    dcc.Tab(label='Visión General GA 🚀', value='overview_ga'), dcc.Tab(label='Demografía & Geo 🌍📍', value='demography_ga'),
                    dcc.Tab(label='Funnels & Rutas 📊🌊', value='funnels_ga'), dcc.Tab(label='Análisis Temporal 📈', value='temporal_ga'),
                    dcc.Tab(label='Correlaciones & Boxplots 🔗', value='correlations_ga'), dcc.Tab(label='Cohort Analysis 👥', value='cohort_ga'),
                    dcc.Tab(label='Simulador "What If" 🧪', value='what_if_ga'),
                ], className='mb-4'),
                dcc.Loading(id="loading-google-subtabs", type="circle", children=html.Div(id='google-subtabs-content')),
            ])
        
        elif tab_ws == 'google_ads_ws':
            return google_ads_layout

        elif tab_ws == 'social_media_ws':
            return html.Div([
                dcc.Tabs(id='social-subtabs', value='general_sm', children=[
                    dcc.Tab(label='Métricas Generales SM 📊', value='general_sm'), dcc.Tab(label='Engagement por Formato (IG) 🎯', value='engagement_sm'),
                    dcc.Tab(label='Wordmap 💬', value='wordmap_sm'), dcc.Tab(label='Top Publicaciones 🏆', value='top_posts_sm'),
                ], className='mb-4'),
                dcc.Loading(id="loading-social-subtabs", type="circle", children=html.Div(id='social-subtabs-content')),
            ])
        return html.P("Selecciona una pestaña.")

    @app.callback(
        Output('overview-ws-ai-insight-visible', 'children'),
        Input('overview-ws-ai-insight-data', 'children')
    )
    def update_overview_ws_ai_card_content(ai_text):
        default_no_data_ai_text = "No hay suficientes datos para un análisis detallado."
        return html.P(ai_text if ai_text and ai_text.strip() != default_no_data_ai_text else "Análisis IA no disponible o datos insuficientes.")

    # Registrar los callbacks de los módulos especializados
    register_ga_callbacks(app)
    register_social_callbacks(app)
