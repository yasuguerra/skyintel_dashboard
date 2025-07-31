import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from dash import dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
from statsmodels.tsa.seasonal import seasonal_decompose
from sklearn.preprocessing import MinMaxScaler
import logging

# Dependencias de tu proyecto
from utils import query_ga
from ai import get_openai_response
from layout_components import create_ai_insight_card, create_ai_chat_interface, add_trendline
from data_processing import get_funnel_data

# Definiciones de funnels y eventos (se mantienen aquí por especificidad a GA)
funnel_base_steps = [{"label": "Visita (page_view)", "type": "event", "dimension": "eventName", "value": "page_view"}]
funnel_whatsapp = funnel_base_steps + [{"label": "Click WhatsApp", "type": "event", "dimension": "eventName", "value": "Clic_Whatsapp"}]
funnel_formulario = funnel_base_steps + [
    {"label": "Formulario Iniciado", "type": "event", "dimension": "eventName", "value": "form_start"},
    {"label": "Formulario Enviado", "type": "event", "dimension": "eventName", "value": "Lleno Formulario"}
]
funnel_llamadas = funnel_base_steps + [{"label": "Click Llamar", "type": "event", "dimension": "eventName", "value": "Clic_Boton_Llamanos"}]
eventos_kpi = ['Clic_Whatsapp', 'Lleno Formulario', 'Clic_Boton_Llamanos']


def register_callbacks(app):
    """Registra todos los callbacks de la sección Google Analytics."""

    @app.callback(
        Output('google-subtabs-content', 'children'),
        Input('google-subtabs', 'value'),
        State('date-picker', 'start_date'),
        State('date-picker', 'end_date')
    )
    def render_google_subtab_content(subtab_ga, start_date, end_date):
        if not start_date or not end_date:
            return html.P("Selecciona un rango de fechas.", className="text-center mt-5")
        sd_str, ed_str = pd.to_datetime(start_date).strftime('%Y-%m-%d'), pd.to_datetime(end_date).strftime('%Y-%m-%d')

        ai_insight_text = "No hay suficientes datos para un análisis detallado."
        default_no_data_ai_text = "No hay suficientes datos para un análisis detallado."


        if subtab_ga == 'overview_ga':
            df_acq = query_ga(metrics=['sessions', 'activeUsers', 'conversions'], dimensions=['date'], start_date=sd_str, end_date=ed_str)
            if df_acq.empty: return html.Div([html.P("No hay datos para la Visión General de GA."), create_ai_insight_card('overview-ga-ai-insight-visible'), html.Div(default_no_data_ai_text, id='overview-ga-ai-insight-data', style={'display':'none'})])
            df_acq.rename(columns={'date': 'Fecha', 'activeUsers': 'Usuarios'}, inplace=True)
            df_acq['Tasa Conversion'] = (df_acq['conversions'].fillna(0) / df_acq['sessions'].replace(0, np.nan).fillna(1) * 100).fillna(0)
            df_acq = df_acq.sort_values('Fecha')

            fig_ses = px.line(df_acq, x='Fecha', y='sessions', title='Sesiones', markers=True); add_trendline(fig_ses, df_acq, 'Fecha', 'sessions')
            fig_usu = px.line(df_acq, x='Fecha', y='Usuarios', title='Usuarios', markers=True); add_trendline(fig_usu, df_acq, 'Fecha', 'Usuarios')
            fig_con = px.line(df_acq, x='Fecha', y='conversions', title='Conversiones', markers=True); add_trendline(fig_con, df_acq, 'Fecha', 'conversions')
            fig_tasa = px.line(df_acq, x='Fecha', y='Tasa Conversion', title='Tasa de Conversión (%)', markers=True); add_trendline(fig_tasa, df_acq, 'Fecha', 'Tasa Conversion')

            df_norm_src = df_acq[['sessions', 'Usuarios', 'conversions']].copy().fillna(0)
            fig_sup = go.Figure().update_layout(title='Tendencias Normalizadas (Datos insuficientes)')
            if not df_norm_src.empty and not df_norm_src.isnull().all().all():
                 scaler = MinMaxScaler(); df_norm_values = scaler.fit_transform(df_norm_src)
                 df_norm = pd.DataFrame(df_norm_values, columns=df_norm_src.columns, index=df_acq['Fecha'])
                 fig_sup = px.line(df_norm, title='Tendencias Normalizadas (Sesiones, Usuarios, Conversiones)'); fig_sup.update_layout(yaxis_title="Valor Normalizado (0 a 1)")

            context_overview_ga = f"Resumen Visión General GA: Sesiones totales: {df_acq['sessions'].sum():,}. Usuarios totales: {df_acq['Usuarios'].sum():,}. Conversiones totales: {df_acq['conversions'].sum():,}. Tasa de conversión promedio: {df_acq['Tasa Conversion'].mean():.2f}%."
            prompt_overview_ga = "Analiza las tendencias de sesiones, usuarios, conversiones y tasa de conversión. Proporciona un diagnóstico y una acción poderosa."
            ai_insight_text = get_openai_response(prompt_overview_ga, context_overview_ga)

            return html.Div([
                dbc.Row([dbc.Col(dcc.Graph(figure=fig_ses), md=6), dbc.Col(dcc.Graph(figure=fig_usu), md=6)]),
                dbc.Row([dbc.Col(dcc.Graph(figure=fig_con), md=6), dbc.Col(dcc.Graph(figure=fig_tasa), md=6)], className="mt-3"),
                dbc.Row([dbc.Col(dcc.Graph(figure=fig_sup), md=12)], className="mt-3"),
                create_ai_insight_card('overview-ga-ai-insight-visible', title="💡 Diagnóstico y Acción (Visión General GA)"),
                html.Div(ai_insight_text, id='overview-ga-ai-insight-data', style={'display': 'none'}),
                create_ai_chat_interface('overview_ga')
            ])

        elif subtab_ga == 'demography_ga':
            # Demographics part
            df_g = query_ga(metrics=['activeUsers', 'conversions'], dimensions=['userGender'], start_date=sd_str, end_date=ed_str)
            df_a = query_ga(metrics=['activeUsers', 'conversions'], dimensions=['userAgeBracket'], start_date=sd_str, end_date=ed_str)
            df_c = query_ga(metrics=['activeUsers', 'conversions'], dimensions=['country'], start_date=sd_str, end_date=ed_str)
            df_city = query_ga(metrics=['activeUsers', 'conversions'], dimensions=['city'], start_date=sd_str, end_date=ed_str)

            demographics_graphs_content = []
            demographics_context_parts = []

            if not df_g.empty:
                df_g.rename(columns={'userGender': 'Sexo', 'activeUsers': 'Usuarios'}, inplace=True)
                df_g_f = df_g[~df_g['Sexo'].isin(['unknown', 'Others', None, '', '(not set)'])].copy()
                if not df_g_f.empty:
                    demographics_graphs_content.append(dbc.Col(dcc.Graph(figure=px.pie(df_g_f, names='Sexo', values='Usuarios', title='Usuarios por Género')), md=6))
                    demographics_context_parts.append(f"Usuarios por Género: {df_g_f.to_string()}")
            if not df_a.empty:
                df_a.rename(columns={'userAgeBracket': 'Edad', 'activeUsers': 'Usuarios'}, inplace=True)
                df_a_f = df_a[~df_a['Edad'].isin(['unknown', 'Others', None, '', '(not set)'])].copy()
                if not df_a_f.empty:
                    demographics_graphs_content.append(dbc.Col(dcc.Graph(figure=px.bar(df_a_f.sort_values('Edad'), x='Edad', y='Usuarios', title='Usuarios por Edad')), md=6))
                    demographics_context_parts.append(f"Usuarios por Edad: {df_a_f.to_string()}")
            if not df_c.empty:
                df_c.rename(columns={'country': 'País', 'activeUsers': 'Usuarios'}, inplace=True)
                df_c_f = df_c[~df_c['País'].isin(['unknown', 'Others', None, '', '(not set)'])].copy()
                if not df_c_f.empty:
                    top_countries = (df_c_f.groupby('País', as_index=False)['Usuarios'].sum().sort_values('Usuarios', ascending=False).head(10))
                    demographics_graphs_content.append(dbc.Col(dcc.Graph(figure=px.bar(top_countries, x='País', y='Usuarios', title='Top 10 Países por Usuarios')),md=6))
                    demographics_context_parts.append(f"Usuarios por País (Top 10): {top_countries.to_string(index=False)}")
            if not df_city.empty:
                df_city.rename(columns={'city': 'Ciudad', 'activeUsers': 'Usuarios'}, inplace=True)
                df_city_f = df_city[~df_city['Ciudad'].isin(['unknown', 'Others', None, '', '(not set)'])].copy()
                if not df_city_f.empty:
                    top_cities = (df_city_f.groupby('Ciudad', as_index=False)['Usuarios'].sum().sort_values('Usuarios', ascending=False).head(10))
                    demographics_graphs_content.append(dbc.Col(dcc.Graph(figure=px.bar(top_cities, x='Ciudad', y='Usuarios', title='Top 10 Ciudades por Usuarios')),md=6))
                    demographics_context_parts.append(f"Usuarios por Ciudad (Top 10): {top_cities.to_string(index=False)}")

            # Geo-Opportunities part
            df_geo = query_ga(metrics=['sessions', 'conversions'], dimensions=['country', 'city'], start_date=sd_str, end_date=ed_str)
            geo_opportunities_content = [html.H4("Geo-Oportunidades", className="mt-5 text-center")]

            if df_geo.empty:
                geo_opportunities_content.append(html.P("No hay datos geográficos."))
            else:
                session_threshold = max(10, df_geo['sessions'].quantile(0.70) if not df_geo.empty and 'sessions' in df_geo and df_geo['sessions'].notna().any() else 10)
                df_geo_opportunity = df_geo[(df_geo['sessions'].fillna(0) >= session_threshold) & (df_geo['conversions'].fillna(0) == 0)].copy()

                fig_geo_country = go.Figure().update_layout(title="Países con Sesiones Significativas y Cero Conversiones Registradas")
                top_cities_opportunity_table_content = html.P(f"No se encontraron oportunidades geográficas claras (ciudades/países con >={session_threshold:.0f} sesiones y 0 conversiones).")

                if not df_geo_opportunity.empty:
                    df_geo_opportunity = df_geo_opportunity.sort_values(by='sessions', ascending=False)
                    country_opportunities = df_geo_opportunity.groupby('country', as_index=False)['sessions'].sum().sort_values(by='sessions', ascending=False)
                    if not country_opportunities.empty:
                         fig_geo_country = px.choropleth(country_opportunities, locations="country", locationmode="country names", color="sessions", hover_name="country", color_continuous_scale=px.colors.sequential.OrRd, title="Países con Sesiones Significativas y Cero Conversiones")

                    top_cities_opportunity_table_content = dash_table.DataTable(
                        data=df_geo_opportunity.head(15).to_dict('records'),
                        columns=[{'name': 'País', 'id': 'country'}, {'name': 'Ciudad', 'id': 'city'}, {'name': 'Sesiones (0 conv.)', 'id': 'sessions'}],
                        style_table={'overflowX': 'auto', 'marginTop': '20px', 'marginBottom': '20px'}, page_size=10, sort_action='native', filter_action='native')

                    demographics_context_parts.append(f"Geo-Oportunidades: Países (sesiones, 0 conv): {country_opportunities.head(3).to_string() if not country_opportunities.empty else 'N/A'}. Ciudades (sesiones, 0 conv): {df_geo_opportunity.head(3).to_string()}.")

                geo_explanation_md = """
                **¿Qué es este Mapa/Tabla de Geo-Oportunidades?** Identifica países y ciudades que generan un volumen considerable de tráfico (sesiones)
                pero no resultan en conversiones.
                **Acciones Potenciales:** Investigar campañas de remarketing, revisar localización del contenido, analizar adecuación del producto/servicio.
                """
                geo_opportunities_content.extend([
                    dbc.Card(dbc.CardBody(dcc.Markdown(geo_explanation_md)), color="info", outline=True, className="mb-3 mt-3"),
                    dcc.Graph(id='geo-opportunity-map', figure=fig_geo_country),
                    html.H5(f"Top Ciudades con Oportunidades (Sesiones >= {session_threshold:.0f}, Conversiones = 0)", className="mt-4"),
                    top_cities_opportunity_table_content
                ])

            # Combined AI Insight
            if demographics_context_parts:
                context_demog_geo = "\n".join(demographics_context_parts)
                prompt_demog_geo = "Analiza los datos demográficos (género, edad) Y las geo-oportunidades (tráfico sin conversión por país/ciudad). ¿Qué segmentos destacan o cuáles podrían ser desatendidos o mal enfocados? Proporciona un diagnóstico combinado y una acción poderosa."
                ai_insight_text = get_openai_response(prompt_demog_geo, context_demog_geo)

            return html.Div([
                html.H4("Análisis Demográfico y Segmentación 🌍📍", className="text-center mt-4"),
                dbc.Row(demographics_graphs_content) if demographics_graphs_content else html.P("No hay datos demográficos suficientes.", className="text-center"),
                html.Hr(className="my-4"),
                html.Div(geo_opportunities_content),
                create_ai_insight_card('demography-ga-ai-insight-visible', title="💡 Diagnóstico y Acción (Demografía & Geo)"),
                html.Div(ai_insight_text, id='demography-ga-ai-insight-data', style={'display': 'none'}),
                create_ai_chat_interface('demography_ga')
            ])

        elif subtab_ga == 'funnels_ga':
            # Funnels part
            df_ev = query_ga(metrics=['eventCount'], dimensions=['date', 'eventName'], start_date=sd_str, end_date=ed_str)
            kpi_content = html.P("No hay datos de eventos.")
            fig_evol = go.Figure().update_layout(title="Evolución Conversiones")
            if not df_ev.empty:
                df_ev.rename(columns={'date': 'Fecha', 'eventName': 'Evento', 'eventCount': 'Conteo'}, inplace=True)
                df_ev_p = df_ev.pivot_table(index="Fecha", columns="Evento", values="Conteo", aggfunc='sum').fillna(0).reset_index()
                for col in eventos_kpi:
                    if col not in df_ev_p.columns:
                        df_ev_p[col] = 0
                totals = {col: int(df_ev_p[col].sum()) for col in eventos_kpi}
                kpi_table = dbc.Table([html.Thead(html.Tr([html.Th("Canal"), html.Th("Conversiones")])),
                                       html.Tbody([html.Tr([html.Td(k), html.Td(f"{v:,.0f}")]) for k, v in totals.items()])],
                                      bordered=True, hover=True, striped=True)
                fig_evol = px.line(df_ev_p.sort_values('Fecha'), x='Fecha', y=eventos_kpi, title="Evolución Conversiones por Canal")
                kpi_content = kpi_table

            df_acq_src = query_ga(metrics=['sessions', 'conversions'], dimensions=['sessionSourceMedium'], start_date=sd_str, end_date=ed_str)
            fig_acq = go.Figure().update_layout(title="Adquisición y Conversión por Canal")
            if not df_acq_src.empty:
                df_acq_src.rename(columns={'sessionSourceMedium': 'Fuente/Medio'}, inplace=True)
                df_acq_src['Tasa Conv.'] = (df_acq_src['conversions'] / df_acq_src['sessions'].replace(0, np.nan) * 100).fillna(0)
                df_acq_src = df_acq_src.sort_values('sessions', ascending=False).head(10)
                fig_acq = px.bar(df_acq_src, x='Fuente/Medio', y=['sessions', 'conversions'], title="Adquisición y Conversión por Canal", barmode='group', text_auto=True)

            df_pg = query_ga(metrics=['sessions', 'bounceRate'], dimensions=['pagePath'], start_date=sd_str, end_date=ed_str)
            fig_visitas, fig_rebote = go.Figure().update_layout(title="Top 10 Páginas Visitadas"), go.Figure().update_layout(title="Top 10 Páginas con Mayor Rebote")
            if not df_pg.empty:
                df_pg.rename(columns={'pagePath': 'Página', 'sessions': 'Sesiones', 'bounceRate': 'Tasa de Rebote'}, inplace=True)
                df_pg['Tasa de Rebote'] = df_pg['Tasa de Rebote'] * 100
                fig_visitas = px.bar(df_pg.sort_values('Sesiones', ascending=False).head(10), x='Página', y='Sesiones', title='Top 10 Páginas Visitadas', text_auto=True, height=700)
                fig_rebote = px.bar(df_pg.sort_values('Tasa de Rebote', ascending=False).head(10), x='Página', y='Tasa de Rebote', title='Top 10 Páginas con Mayor Rebote (%)', text_auto='.1f', height=700)

            df_pg_dur = query_ga(metrics=['sessions', 'averageSessionDuration'], dimensions=['pagePath'], start_date=sd_str, end_date=ed_str)
            fig_duracion = go.Figure().update_layout(title="Top 10 Páginas por Duración")
            if not df_pg_dur.empty:
                df_pg_dur.rename(columns={'pagePath': 'Página', 'sessions': 'Sesiones', 'averageSessionDuration': 'Duración Promedio'}, inplace=True)
                top_duracion = df_pg_dur.sort_values('Duración Promedio', ascending=False).head(10)
                fig_duracion = px.bar(top_duracion, x='Página', y='Duración Promedio', title='Top 10 Páginas por Duración', text_auto='.2f', height=700)
                fig_visitas.update_xaxes(tickangle=45)
                fig_rebote.update_xaxes(tickangle=45)
                fig_duracion.update_xaxes(tickangle=45)

            labels_w, counts_w = get_funnel_data(funnel_whatsapp, sd_str, ed_str)
            labels_f, counts_f = get_funnel_data(funnel_formulario, sd_str, ed_str)
            labels_l, counts_l = get_funnel_data(funnel_llamadas, sd_str, ed_str)

            fig_w = go.Figure(go.Funnel(y=labels_w, x=counts_w, textinfo="value+percent previous")).update_layout(title="Funnel WhatsApp") if counts_w and counts_w[0]>0 else go.Figure().update_layout(title="Funnel WhatsApp (No data)")
            fig_f = go.Figure(go.Funnel(y=labels_f, x=counts_f, textinfo="value+percent previous")).update_layout(title="Funnel Formulario") if counts_f and counts_f[0]>0 else go.Figure().update_layout(title="Funnel Formulario (No data)")
            fig_l = go.Figure(go.Funnel(y=labels_l, x=counts_l, textinfo="value+percent previous")).update_layout(title="Funnel Llamadas") if counts_l and counts_l[0]>0 else go.Figure().update_layout(title="Funnel Llamadas (No data)")

            total_visits_funnel = counts_w[0] if counts_w else 0
            total_conv_funnel = (counts_w[-1] if len(counts_w) == len(funnel_whatsapp) and counts_w else 0) + \
                                (counts_f[-1] if len(counts_f) == len(funnel_formulario) and counts_f else 0) + \
                                (counts_l[-1] if len(counts_l) == len(funnel_llamadas) and counts_l else 0)
            fig_total_funnel = go.Figure(go.Funnel(y=["Visitas Totales (Inicio Funnel)", "Conversiones Totales (Final Funnel)"], x=[total_visits_funnel, total_conv_funnel], textinfo="value+percent initial")).update_layout(title="Conversión Global de Funnels") if total_visits_funnel > 0 else go.Figure().update_layout(title="Conversión Global de Funnels (No data)")

            funnels_section = html.Div([
                html.H4("Adquisición, KPIs y Evolución", className="mt-4"),
                dbc.Row([dbc.Col(kpi_content, width=12, lg=4), dbc.Col(dcc.Graph(figure=fig_evol), width=12, lg=8)]),
                dbc.Row([dbc.Col(dcc.Graph(figure=fig_acq), width=12, lg=8)], className="mt-4", justify="center"),
                html.Hr(), html.H4("Comportamiento en Páginas", className="mt-4"),
                dbc.Row([dbc.Col(dcc.Graph(figure=fig_visitas), width=12, lg=6), dbc.Col(dcc.Graph(figure=fig_duracion), width=12, lg=6), dbc.Col(dcc.Graph(figure=fig_rebote), width=12, lg=6)]),
                html.Hr(), html.H4("Funnels Específicos y General", className="mt-4"),
                dbc.Row([dbc.Col(dcc.Graph(figure=fig_w), width=12, lg=4), dbc.Col(dcc.Graph(figure=fig_f), width=12, lg=4), dbc.Col(dcc.Graph(figure=fig_l), width=12, lg=4)]),
                dbc.Row([dbc.Col(dcc.Graph(figure=fig_total_funnel), width=12, lg=8, className="mx-auto mt-3")])
            ])

            # Sankey part
            key_events_sankey = ['page_view', 'form_start', 'Clic_Whatsapp', 'Lleno Formulario', 'Clic_Boton_Llamanos']
            df_source_event = query_ga(metrics=['sessions', 'eventCount'], dimensions=['sessionSourceMedium', 'eventName'], start_date=sd_str, end_date=ed_str)

            sankey_content = [html.H4("Análisis de Rutas (Sankey)", className="mt-5 text-center")]
            fig_sankey = go.Figure().update_layout(title_text="Análisis de Rutas (Fuente -> Evento) - No hay datos")
            sankey_explanation = "No hay datos suficientes para el diagrama de Sankey."
            sankey_ai_context_part = "Datos de Sankey no disponibles."
            df_sankey_data = pd.DataFrame() # Initialize
            source_nodes = [] # Initialize

            if not df_source_event.empty:
                df_sankey_data = df_source_event[df_source_event['eventName'].isin(key_events_sankey)].copy()
                if not df_sankey_data.empty:
                    all_labels = list(pd.concat([df_sankey_data['sessionSourceMedium'], df_sankey_data['eventName']]).unique())
                    label_map = {label: i for i, label in enumerate(all_labels)}
                    source_nodes = df_sankey_data['sessionSourceMedium'].map(label_map).tolist()
                    target_nodes = df_sankey_data['eventName'].map(label_map).tolist()
                    values = df_sankey_data['sessions'].apply(lambda x: max(x, 0.1)).tolist()

                    if source_nodes:
                        fig_sankey = go.Figure(data=[go.Sankey(
                            node=dict(pad=25, thickness=20, line=dict(color="black", width=0.5), label=all_labels, color="blue"),
                            link=dict(source=source_nodes, target=target_nodes, value=values)
                        )])
                        fig_sankey.update_layout(title_text="Análisis de Rutas de Usuario (Fuente/Medio -> Evento Clave)", font_size=12, height=700)
                        sankey_explanation = "**Interpretación del Sankey:** Muestra flujos de usuarios desde fuentes/medios hacia eventos clave. Líneas gruesas = rutas comunes. Ayuda a ver qué canales impulsan acciones. **Limitación:** Modelo simplificado; no es un pathing secuencial estricto."
                        sankey_ai_context_part = f"Diagrama de Sankey muestra flujos de '{df_sankey_data['sessionSourceMedium'].nunique()}' fuentes/medios a '{df_sankey_data['eventName'].nunique()}' eventos clave. Principales fuentes: {df_sankey_data.groupby('sessionSourceMedium')['sessions'].sum().nlargest(3).to_string()}."

            sankey_content.extend([
                dbc.Card(dbc.CardBody(dcc.Markdown(sankey_explanation)), color="info", outline=True, className="mb-3 mt-3"),
                dcc.Graph(id='sankey-graph-funnels-tab', figure=fig_sankey),
            ])

            # Combined AI Insight
            if total_visits_funnel > 0 or (not df_source_event.empty and not df_sankey_data.empty and source_nodes):
                context_funnels_sankey = f"Datos de Funnels: WhatsApp ({counts_w}), Formulario ({counts_f}), Llamadas ({counts_l}). Conversión Global: Visitas={total_visits_funnel}, Conversiones={total_conv_funnel}. {sankey_ai_context_part}"
                prompt_funnels_sankey = "Analiza el rendimiento de los funnels de conversión Y las rutas de usuario del diagrama de Sankey. Identifica el principal cuello de botella en los funnels y las rutas de usuario más importantes (o ineficientes) del Sankey. Proporciona un diagnóstico combinado y una acción poderosa para mejorar la conversión general y la eficiencia de las rutas."
                ai_insight_text = get_openai_response(prompt_funnels_sankey, context_funnels_sankey)
            else:
                ai_insight_text = "No hay datos suficientes para analizar los funnels o las rutas Sankey."

            return html.Div([
                funnels_section,
                html.Hr(className="my-4"),
                html.Div(sankey_content),
                create_ai_insight_card('funnels-ga-ai-insight-visible', title="💡 Diagnóstico y Acción (Funnels & Rutas)"),
                html.Div(ai_insight_text, id='funnels-ga-ai-insight-data', style={'display': 'none'}),
                create_ai_chat_interface('funnels_ga')
            ])

        elif subtab_ga == 'what_if_ga':
            what_if_ai_text = "Ajusta los sliders para simular escenarios y ver el análisis."
            return html.Div([
                html.H4('Simulador de Escenarios "What If" 🧪', className="mt-4 text-center"),
                dbc.Row([
                    dbc.Col([html.Label("Aumento % en Sesiones Totales:", className="form-label"), dcc.Slider(id='what-if-sessions-slider', min=0, max=100, step=5, value=0, marks={i: f'{i}%' for i in range(0, 101, 20)}, tooltip={"placement": "bottom", "always_visible": True}),], md=6, className="mb-3"),
                    dbc.Col([html.Label("Cambio % en Tasa de Conversión General:", className="form-label"), dcc.Slider(id='what-if-cr-slider', min=-50, max=50, step=5, value=0, marks={i: f'{i}%' for i in range(-50, 51, 25)}, tooltip={"placement": "bottom", "always_visible": True}),], md=6, className="mb-3"),
                ]),
                dbc.Button("Simular Escenario", id="what-if-simulate-button", color="primary", className="mt-3 mb-3"),
                html.Div(id='what-if-results-display'),
                create_ai_insight_card('what-if-ga-ai-insight-visible', title="💡 Interpretación y Sugerencias del Escenario"),
                html.Div(what_if_ai_text, id='what-if-ga-ai-insight-data', style={'display': 'none'}),
                create_ai_chat_interface('what_if_ga')
            ])

        elif subtab_ga == 'temporal_ga':
            df_acq_ts = query_ga(metrics=['sessions'], dimensions=['date'], start_date=sd_str, end_date=ed_str)
            fig_temporal = go.Figure().update_layout(title='Descomposición Temporal y Anomalías (No hay suficientes datos)')
            if df_acq_ts.empty or len(df_acq_ts) < 14:
                ai_insight_text = "Se necesitan al menos 14 días de datos para el análisis temporal."
            else:
                df_acq_ts.rename(columns={'date': 'Fecha'}, inplace=True)
                dff_ts = df_acq_ts.set_index(pd.to_datetime(df_acq_ts['Fecha'])).sort_index()['sessions'].asfreq('D').fillna(0)
                if len(dff_ts) >= 14:
                    period_val = min(7, len(dff_ts) // 2 if len(dff_ts) // 2 > 0 else 1)
                    try:
                        decomposition = seasonal_decompose(dff_ts, model='additive', period=period_val)
                        fig_temporal = go.Figure()
                        fig_temporal.add_trace(go.Scatter(x=dff_ts.index, y=dff_ts, mode='lines', name='Original'))
                        fig_temporal.add_trace(go.Scatter(x=dff_ts.index, y=decomposition.trend, mode='lines', name='Tendencia'))
                        fig_temporal.add_trace(go.Scatter(x=dff_ts.index, y=decomposition.seasonal, mode='lines', name='Estacionalidad'))
                        std_dev = decomposition.resid.std()
                        anomalies = pd.DataFrame()
                        if pd.notna(std_dev) and std_dev > 0:
                            anomalies_df = pd.DataFrame({'Fecha': dff_ts.index, 'sessions': dff_ts.values, 'resid': decomposition.resid})
                            anomalies = anomalies_df[(anomalies_df['resid'].notna()) & ((anomalies_df['resid'] < -2 * std_dev) | (anomalies_df['resid'] > 2 * std_dev))]
                            if not anomalies.empty: fig_temporal.add_trace(go.Scatter(x=anomalies['Fecha'], y=anomalies['sessions'], mode='markers', name='Anomalías', marker=dict(color='red', size=10, symbol='x')))
                        fig_temporal.update_layout(title='Descomposición Temporal y Anomalías (Sesiones Diarias)', hovermode='x unified')
                        context_temporal = f"Análisis de descomposición temporal. Tendencia promedio: {decomposition.trend.dropna().mean():.2f}. Estacionalidad: Max {decomposition.seasonal.max():.2f}, Min {decomposition.seasonal.min():.2f}. Anomalías detectadas: {len(anomalies)}."
                        prompt_temporal = "Diagnostica los patrones de tendencia, estacionalidad y anomalías. Sugiere una acción poderosa basada en estos hallazgos."
                        ai_insight_text = get_openai_response(prompt_temporal, context_temporal)
                    except Exception as e:
                        logging.error(f"Error en análisis temporal: {e}")
                        ai_insight_text = f"Error al procesar datos para análisis temporal: {e}"

            return html.Div([
                dcc.Graph(id='temporal-graph', figure=fig_temporal),
                create_ai_insight_card('temporal-ga-ai-insight-visible', title="💡 Diagnóstico y Acción (Temporal)"),
                html.Div(ai_insight_text, id='temporal-ga-ai-insight-data', style={'display': 'none'}),
                create_ai_chat_interface('temporal_ga')
            ])

        elif subtab_ga == 'correlations_ga':
            df_sp = query_ga(metrics=['sessions', 'activeUsers', 'averageSessionDuration', 'bounceRate', 'conversions'], dimensions=['date', 'deviceCategory'], start_date=sd_str, end_date=ed_str)
            df_age_conv = query_ga(metrics=['conversions', 'activeUsers'], dimensions=['userAgeBracket'], start_date=sd_str, end_date=ed_str)

            fig_matrix = go.Figure().update_layout(title="Matriz de Correlación (Datos insuficientes)")
            fig_box_dev_conv = go.Figure().update_layout(title="Conversiones por Dispositivo (Datos insuficientes)")
            fig_box_age_conv = go.Figure().update_layout(title="Conversiones por Edad (Datos insuficientes)")
            corr_matrix_text_for_ai = "No disponible"

            if not df_sp.empty:
                df_sp.rename(columns={'deviceCategory': 'Dispositivo', 'sessions': 'Sesiones', 'activeUsers': 'Usuarios', 'averageSessionDuration': 'Duración Media (s)', 'bounceRate': 'Tasa Rebote (%)'}, inplace=True)
                df_sp['Tasa Rebote (%)'] = df_sp['Tasa Rebote (%)'].fillna(0) * 100
                metrics_for_corr = ['Sesiones', 'Usuarios', 'Duración Media (s)', 'Tasa Rebote (%)', 'conversions']
                metrics_to_plot = [m for m in metrics_for_corr if m in df_sp.columns and df_sp[m].notna().any()]
                if len(metrics_to_plot) >= 2:
                    df_sp_filt_dev = df_sp[df_sp['Dispositivo'] != '(not set)']
                    if not df_sp_filt_dev.empty:
                        try:
                            fig_matrix = px.scatter_matrix(df_sp_filt_dev, dimensions=metrics_to_plot, color="Dispositivo", title="Matriz de Correlación por Dispositivo"); fig_matrix.update_layout(height=800)
                            corr_matrix_text_for_ai = df_sp_filt_dev[metrics_to_plot].corr(numeric_only=True).to_string()
                        except Exception as e:
                            logging.error(f"Error generando scatter matrix o corr: {e}")
                        if 'conversions' in df_sp_filt_dev.columns: fig_box_dev_conv = px.box(df_sp_filt_dev, x="Dispositivo", y="conversions", title="Conversiones por Dispositivo", points="all")

            if not df_age_conv.empty:
                df_age_conv.rename(columns={'userAgeBracket': 'Edad'}, inplace=True)
                df_age_f = df_age_conv[~df_age_conv['Edad'].isin(['unknown', 'Others', None, '', '(not set)'])].copy()
                if not df_age_f.empty and 'conversions' in df_age_f.columns: fig_box_age_conv = px.box(df_age_f, x="Edad", y="conversions", title="Conversiones por Edad", points="all")

            context_corr = f"Matriz de Correlación:\n{corr_matrix_text_for_ai}\nConsidera también boxplots de conversiones por dispositivo y edad."
            prompt_corr = "Identifica correlaciones fuertes o diferencias significativas en conversiones por grupo. Diagnostica y sugiere una acción poderosa."
            ai_insight_text = get_openai_response(prompt_corr, context_corr)

            return html.Div([
                dcc.Graph(id='corr-graph', figure=fig_matrix),
                dbc.Row([dbc.Col(dcc.Graph(figure=fig_box_dev_conv), md=6), dbc.Col(dcc.Graph(figure=fig_box_age_conv), md=6)], className="mt-3"),
                create_ai_insight_card('correlations-ga-ai-insight-visible', title="💡 Diagnóstico y Acción (Correlaciones)"),
                html.Div(ai_insight_text, id='correlations-ga-ai-insight-data', style={'display': 'none'}),
                create_ai_chat_interface('correlations_ga')
            ])

        elif subtab_ga == 'cohort_ga':
            df_ch = query_ga(metrics=['activeUsers'], dimensions=['firstSessionDate', 'nthDay'], start_date=sd_str, end_date=ed_str)
            fig_cohort = go.Figure().update_layout(title="Análisis de Cohortes (Datos insuficientes)")
            cohort_explanation_md = "No hay suficientes datos para el análisis de cohortes."
            ai_insight_text = cohort_explanation_md

            if not df_ch.empty and len(df_ch) >= 2:
                try:
                    df_ch.rename(columns={'firstSessionDate': 'Cohorte', 'nthDay': 'DíaDesdeAdquisición', 'activeUsers': 'UsuariosRetenidos'}, inplace=True)
                    df_ch['Cohorte'] = pd.to_datetime(df_ch['Cohorte'], format='%Y%m%d', errors='coerce').dropna()
                    df_ch['DíaDesdeAdquisición'] = pd.to_numeric(df_ch['DíaDesdeAdquisición'], errors='coerce').fillna(0).astype(int)
                    cohort_pivot = df_ch.pivot_table(index='Cohorte', columns='DíaDesdeAdquisición', values='UsuariosRetenidos')
                    if not cohort_pivot.empty:
                        cohort_pivot = cohort_pivot.sort_index(ascending=False).reindex(sorted(cohort_pivot.columns), axis=1)
                        cohort_sizes = cohort_pivot.iloc[:, 0]
                        retention_matrix = cohort_pivot.apply(lambda row: (row / cohort_sizes.loc[row.name] * 100) if cohort_sizes.loc[row.name] > 0 else 0.0, axis=1).fillna(0.0)
                        retention_matrix_display = retention_matrix.head(15).iloc[:, :15]
                        if not retention_matrix_display.empty:
                            fig_cohort = px.imshow(retention_matrix_display, labels=dict(x="Día desde Adquisición", y="Cohorte", color="Retención (%)"), color_continuous_scale='Blues', aspect='auto', text_auto=".1f")
                            fig_cohort.update_layout(title="Análisis de Cohortes – Retención de Usuarios (%)", xaxis_title="Días Desde la Primera Sesión", yaxis_title="Fecha de Primera Sesión (Cohorte)"); fig_cohort.update_xaxes(type='category'); fig_cohort.update_yaxes(type='category', tickformat='%Y-%m-%d')
                            cohort_explanation_md = "**Interpretación Cohortes:** Agrupa usuarios por fecha de 1ra visita y rastrea su retención. Ayuda a entender cuán bien retienes usuarios y el impacto de cambios. Filas=Cohortes, Columnas=Días desde 1ra visita, Color/Número=% Retención."
                            context_cohort = f"Análisis de Cohortes: Retención promedio Día 1: {retention_matrix_display.iloc[:, 1].mean() if len(retention_matrix_display.columns) > 1 else 'N/A':.1f}%. Retención Día 7: {retention_matrix_display.iloc[:, 7].mean() if len(retention_matrix_display.columns) > 7 else 'N/A':.1f}%."
                            prompt_cohort = "Analiza la tendencia de retención. ¿Alguna cohorte destaca? ¿Patrones generales? Diagnostica y sugiere una acción poderosa."
                            ai_insight_text = get_openai_response(prompt_cohort, context_cohort)
                except Exception as e:
                    logging.error(f"Error en Cohort: {e}", exc_info=True)
                    ai_insight_text = f"Error al procesar datos de cohortes: {e}"

            return html.Div([
                dbc.Card(dbc.CardBody(dcc.Markdown(cohort_explanation_md)), color="info", outline=True, className="mb-3"),
                dcc.Graph(id='cohort-graph', figure=fig_cohort),
                create_ai_insight_card('cohort-ga-ai-insight-visible', title="💡 Diagnóstico y Acción (Cohortes)"),
                html.Div(ai_insight_text, id='cohort-ga-ai-insight-data', style={'display': 'none'}),
                create_ai_chat_interface('cohort_ga')
            ])

        return html.P(f"Pestaña GA '{subtab_ga}' no implementada o datos no disponibles.")


    # Callbacks para actualizar las tarjetas de IA visibles
    ga_ai_insight_visible_ids = [
        'overview-ga-ai-insight-visible', 'demography-ga-ai-insight-visible',
        'funnels-ga-ai-insight-visible', 'what-if-ga-ai-insight-visible',
        'temporal-ga-ai-insight-visible', 'correlations-ga-ai-insight-visible', 'cohort-ga-ai-insight-visible'
    ]
    ga_ai_insight_data_ids = [
        'overview-ga-ai-insight-data', 'demography-ga-ai-insight-data',
        'funnels-ga-ai-insight-data', 'what-if-ga-ai-insight-data',
        'temporal-ga-ai-insight-data', 'correlations-ga-ai-insight-data', 'cohort-ga-ai-insight-data'
    ]

    for visible_id, data_id in zip(ga_ai_insight_visible_ids, ga_ai_insight_data_ids):
        @app.callback(Output(visible_id, 'children'), Input(data_id, 'children'))
        def update_ga_ai_card_generic(ai_text):
            default_no_data_msg = "Análisis IA no disponible o datos insuficientes."
            specific_no_data_msgs = [
                "No hay suficientes datos para un análisis detallado.", "No hay datos de Sankey para analizar.",
                "No hay datos suficientes para analizar los funnels.", "Se necesitan al menos 14 días de datos para el análisis temporal.",
                "Error al procesar datos para análisis temporal", "Matriz de retención vacía después del procesamiento.",
                "No se pudo construir la tabla pivote para cohortes.", "No hay suficientes datos para el análisis de cohortes.",
                "Ajusta los sliders para simular escenarios y ver el análisis."
            ]
            if not ai_text: return html.P(default_no_data_msg)
            ai_text_strip = ai_text.strip()
            if not ai_text_strip or any(msg in ai_text_strip for msg in specific_no_data_msgs):
                return html.P(default_no_data_msg)
            return html.P(ai_text)

    # Callback para el simulador "What If"
    @app.callback(
        [Output('what-if-results-display', 'children'),
         Output('what-if-ga-ai-insight-data', 'children')],
        [Input('what-if-simulate-button', 'n_clicks')],
        [State('date-picker', 'start_date'), State('date-picker', 'end_date'),
         State('what-if-sessions-slider', 'value'), State('what-if-cr-slider', 'value')],
        prevent_initial_call=True
    )
    def simulate_what_if_scenario(n_clicks, start_date, end_date, sessions_increase_pct, cr_change_pct):
        if not n_clicks:
            return html.P("Haz clic en 'Simular Escenario' para ver los resultados."), "Ajusta los sliders y haz clic en simular."

        sd_str, ed_str = pd.to_datetime(start_date).strftime('%Y-%m-%d'), pd.to_datetime(end_date).strftime('%Y-%m-%d')
        df_baseline = query_ga(metrics=['sessions', 'conversions'], dimensions=[], start_date=sd_str, end_date=ed_str)

        if df_baseline.empty or 'sessions' not in df_baseline.columns or 'conversions' not in df_baseline.columns or df_baseline['sessions'].sum() == 0:
            return html.P("No se pudieron obtener datos base para la simulación (se requieren sesiones > 0)."), "Datos base no disponibles o con 0 sesiones."

        baseline_sessions = df_baseline['sessions'].sum()
        baseline_conversions = df_baseline['conversions'].sum()
        baseline_cr = (baseline_conversions / baseline_sessions * 100) if baseline_sessions > 0 else 0
        
        new_sessions = baseline_sessions * (1 + sessions_increase_pct / 100)
        new_cr_abs = max(0, min(baseline_cr * (1 + cr_change_pct / 100), 100))
        predicted_conversions = new_sessions * (new_cr_abs / 100)

        results_display = dbc.Card(dbc.CardBody([
            html.H5("Resultados de la Simulación", className="card-title"),
            dbc.Row([
                dbc.Col([
                    html.H6("Línea Base:"),
                    html.P(f"Sesiones: {baseline_sessions:,.0f}"),
                    html.P(f"Tasa de Conversión: {baseline_cr:.2f}%"),
                    html.P(f"Conversiones: {baseline_conversions:,.0f}"),
                ], md=6),
                dbc.Col([
                    html.H6("Escenario Proyectado:"),
                    html.P(f"Sesiones: {new_sessions:,.0f} ({sessions_increase_pct:+}%)"),
                    html.P(f"Tasa de Conversión: {new_cr_abs:.2f}% ({cr_change_pct:+}% relativo)"),
                    html.P(f"Conversiones: {predicted_conversions:,.0f}"),
                ], md=6),
            ]),
            html.P(f"Cambio en Conversiones: {predicted_conversions - baseline_conversions:,.0f} ({((predicted_conversions / baseline_conversions - 1) * 100) if baseline_conversions > 0 else 'N/A'}%)", className="fw-bold mt-2")
        ]), className="mt-3")

        context_what_if = f"Simulación: Línea Base (Sesiones={baseline_sessions:,.0f}, CR={baseline_cr:.2f}%, Conv={baseline_conversions:,.0f}). Simul_Input (ΔSesiones={sessions_increase_pct}%, ΔCR={cr_change_pct}%). Proyectado (Sesiones={new_sessions:,.0f}, CR={new_cr_abs:.2f}%, Conv={predicted_conversions:,.0f})."
        prompt_what_if = "Interpreta este escenario 'What If'. Diagnostica su realismo, el impacto principal (beneficios/riesgos) y sugiere una acción poderosa para intentar alcanzar el escenario proyectado."
        ai_interpretation = get_openai_response(prompt_what_if, context_what_if)

        return results_display, ai_interpretation

    # Registrar callbacks de chat
    ga_subtabs_with_chat = ['overview_ga', 'demography_ga', 'funnels_ga', 'what_if_ga', 'temporal_ga', 'correlations_ga', 'cohort_ga']
    for tab_id in ga_subtabs_with_chat:
        @app.callback(
            Output(f'{tab_id}-chat-history', 'children'),
            Input(f'{tab_id}-chat-submit', 'n_clicks'),
            State(f'{tab_id}-chat-input', 'value'),
            State(f'{tab_id}-chat-history', 'children'),
            State('google-subtabs', 'value'),
            prevent_initial_call=True,
            # Se usa `memoize` para que el callback se asocie con el `tab_id` correcto en cada iteración
            memoize=True
        )
        def update_chat(n_clicks, user_input, history, current_tab_value, tab_id=tab_id):
            if not n_clicks or not user_input: return history
            if history is None: history = []
            elif not isinstance(history, list): history = [history]

            context = f"Estás en la pestaña '{tab_id}' (sub-pestaña actual de GA: {current_tab_value}). El usuario tiene una pregunta."
            ai_response = get_openai_response(user_input, context)

            new_history_entry_user = html.P([html.B("Tú: ", style={'color': '#007bff'}), user_input], style={'margin': '5px 0'})
            new_history_entry_ai = html.P([html.B("SkyIntel AI: ", style={'color': '#28a745'}), ai_response], style={'background': '#f0f0f0', 'padding': '8px', 'borderRadius': '5px', 'margin': '5px 0'})

            return history + [new_history_entry_user, new_history_entry_ai]