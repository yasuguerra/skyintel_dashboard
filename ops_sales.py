from dash import dcc, html, Input, Output, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# ----- Dependencias internas -----
from ai import get_openai_response
from data_processing import unify_data, clean_df, safe_sorted_unique

# ===============================================================
def register_ops_sales_callbacks(app):
    @app.callback(
        # ---------------------- 33 Outputs ----------------------
        [
            Output('output-kpis', 'children'),
            Output('destino-filter', 'options'),
            Output('operador-filter', 'options'),
            Output('mes-filter', 'options'),
            Output('vuelos-mes', 'figure'),
            Output('ingresos-mes', 'figure'),
            Output('ganancia-mes', 'figure'),
            Output('ganancia-total-mes', 'figure'),
            Output('ops-total-mes', 'figure'),
            Output('vuelos-tiempo', 'figure'),
            Output('ingresos-tiempo', 'figure'),
            Output('ganancia-tiempo', 'figure'),
            Output('top-destinos-vuelos', 'figure'),
            Output('top-destinos-ganancia', 'figure'),
            Output('pasajeros-destino', 'figure'),
            Output('vuelos-operador', 'figure'),
            Output('ganancia-aeronave', 'figure'),
            Output('top-ganancia-operador', 'figure'),
            Output('top-ganancia-aeronave', 'figure'),
            Output('ganancia-tipo-nave', 'figure'),
            Output('operaciones-tipo-nave', 'figure'),
            Output('destino-heatmap', 'options'),
            Output('heatmap-gain-destino-dia', 'figure'),
            Output('heatmap-count-destino-dia', 'figure'),
            Output('heatmap-dia-hora', 'figure'),
            Output('ticket-promedio', 'figure'),
            Output('tabla-detallada', 'data'),
            Output('tabla-detallada', 'columns'),
            Output('error-message', 'children'),
            Output('ai-insight-comparativo-general', 'children'),
            Output('ai-insight-vuelos-destinos', 'children'),
            Output('ai-insight-operadores-aeronaves', 'children'),
            Output('ai-insight-analisis-avanzado', 'children')
        ],
        # ----------------------- Inputs -------------------------
        [
            Input('upload-data', 'contents'),
            Input('upload-data', 'filename'),
            Input('destino-filter', 'value'),
            Input('operador-filter', 'value'),
            Input('mes-filter', 'value'),
            Input('destino-heatmap', 'value')
        ]
    )
    def update_dashboard(contents, filenames,
                         destino_filter_val, operador_filter_val,
                         mes_filter_val, destino_heatmap_val): 
        # ---------- Estado inicial (33 elementos, uno por Output) ----------
        empty_fig = go.Figure()
        no_ai_insight = "No hay suficientes datos para generar un análisis IA."
        initial_return_state = [
            [], [], [], [],                                # 0-3
            empty_fig, empty_fig, empty_fig, empty_fig, empty_fig,        # 4-8
            empty_fig, empty_fig, empty_fig, empty_fig, empty_fig,        # 9-13
            empty_fig, empty_fig, empty_fig, empty_fig,                   # 14-17
            empty_fig,         # 18 -> top_ganancia_aeronave
            empty_fig,         # 19 -> ganancia_tipo_nave
            empty_fig,         # 20 -> operaciones_tipo_nave
            [],                # 21 -> destino_heatmap_options
            empty_fig, empty_fig, empty_fig, empty_fig,   # 22-25
            [], [], '',                                   # 26-28
            no_ai_insight, no_ai_insight,
            no_ai_insight, no_ai_insight                  # 29-32
        ]

        # ---------- Validaciones de carga ----------
        if contents is None or filenames is None:
            return initial_return_state

        df, err = unify_data(contents, filenames)
        if err:
            initial_return_state[28] = err         # error-message
            return initial_return_state
        if df.empty:
            initial_return_state[28] = ("No data to display "
                                        "after processing files.")
            return initial_return_state

        # ---------- Limpieza y filtros ----------
        df = clean_df(df)
        df_plot_original = df.copy()

        filtered_df = df.copy()
        if destino_filter_val:
            filtered_df = filtered_df[
                filtered_df['Destino'].astype(str).isin(destino_filter_val)]
        if operador_filter_val:
            filtered_df = filtered_df[
                filtered_df['Operador'].astype(str).isin(operador_filter_val)]
        if mes_filter_val:
            filtered_df = filtered_df[
                filtered_df['Mes'].astype(str)
                .isin([str(m) for m in mes_filter_val])]

        if filtered_df.empty:
            initial_return_state[28] = ("No data matches the "
                                        "selected filters.")
            # Actualiza opciones de filtros
            initial_return_state[1] = [{'label': d, 'value': d}
                                       for d in safe_sorted_unique(
                                           df_plot_original['Destino'])]
            initial_return_state[2] = [{'label': o, 'value': o}
                                       for o in safe_sorted_unique(
                                           df_plot_original['Operador'])]
            initial_return_state[3] = [{'label': m, 'value': m}
                                       for m in safe_sorted_unique(
                                           df_plot_original['Mes'])]
            initial_return_state[21] = [{'label': d, 'value': d}
                                        for d in safe_sorted_unique(
                                            df_plot_original['Destino'])]
            return initial_return_state
        
                # ---------- KPI CARDS (vuelve a incluir esta sección) ----------
        kpi_cards_list = []
        for year_val in sorted(filtered_df['Año'].unique()):
            df_year = filtered_df[filtered_df['Año'] == year_val]
            if df_year.empty:
                continue
            kpi_cards_list.append(
                dbc.Col(
                    dbc.Card([
                        dbc.CardHeader(f"Resumen Año {year_val}",
                                    className="text-white bg-primary"),
                        dbc.CardBody([
                            html.H5("Vuelos Totales", className="card-title"),
                            html.P(f"{df_year.shape[0]}",
                                className="card-text fs-4 fw-bold"),
                            html.H5("Pasajeros Totales", className="card-title mt-2"),
                            html.P(f"{int(df_year['Número de pasajeros'].sum())}",
                                className="card-text fs-4 fw-bold"),
                            html.H5("Ingresos Totales", className="card-title mt-2"),
                            html.P(f"${df_year['Monto total a cobrar'].sum():,.2f}",
                                className="card-text fs-4 fw-bold"),
                            html.H5("Ganancia Total", className="card-title mt-2"),
                            html.P(f"${df_year['Ganancia'].sum():,.2f}",
                                className="card-text fs-4 fw-bold"),
                            html.H5("Ticket Promedio", className="card-title mt-2"),
                            html.P(f"${df_year['Monto total a cobrar'].mean():,.2f}",
                                className="card-text fs-4 fw-bold"),
                        ])
                    ], className="shadow-sm mb-4 h-100"),
                    xs=12, sm=6, md=4, lg=3
                )
            )

        # Row que contendrá todas las tarjetas
        output_kpis_children = dbc.Row(kpi_cards_list, className="mb-4")

        # ============= Construcción de figuras =================
        df_plot = filtered_df.copy()
        meses_order = ["January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November",
                       "December"]
        df_plot['MonthName'] = pd.Categorical(
            df_plot['Fecha y hora del vuelo'].dt.strftime('%B'),
            categories=meses_order, ordered=True)

        # --- Gráficos mensuales básicos ---
        vuelos_mes_data = df_plot.groupby(['Año', 'MonthName'],
                                          observed=False).size()\
                                          .reset_index(name='Vuelos')
        fig_vuelos_mes = px.line(vuelos_mes_data, x='MonthName', y='Vuelos',
                                 color='Año', markers=True,
                                 title='Vuelos por Mes')

        ingresos_mes_data = df_plot.groupby(['Año', 'MonthName'],
                                            observed=False)[
                                                'Monto total a cobrar'].sum()\
                                            .reset_index()
        fig_ingresos_mes = px.line(ingresos_mes_data, x='MonthName',
                                   y='Monto total a cobrar', color='Año',
                                   markers=True, title='Ingresos por Mes')

        ganancia_mes_data = df_plot.groupby(['Año', 'MonthName'],
                                            observed=False)['Ganancia'].sum()\
                                            .reset_index()
        fig_ganancia_mes = px.line(ganancia_mes_data, x='MonthName',
                                   y='Ganancia', color='Año', markers=True,
                                   title='Ganancia por Mes')

        # --- Ganancia / Operaciones totales con tendencia ---
        df_plot['year_month'] = df_plot['Fecha y hora del vuelo']\
                                    .dt.to_period('M').astype(str)

        ganancia_timeline = df_plot.groupby('year_month')['Ganancia']\
                                   .sum().reset_index()\
                                   .sort_values('year_month')
        fig_ganancia_total_mes = go.Figure(go.Scatter(
            x=ganancia_timeline['year_month'],
            y=ganancia_timeline['Ganancia'],
            mode='lines+markers', name='Ganancia Mensual'))
        if ganancia_timeline.shape[0] > 1:
            x = np.arange(len(ganancia_timeline))
            z = np.polyfit(x, ganancia_timeline['Ganancia'], 1)
            fig_ganancia_total_mes.add_trace(go.Scatter(
                x=ganancia_timeline['year_month'],
                y=np.poly1d(z)(x), mode='lines', name='Tendencia',
                line=dict(dash='dash')))

        ops_total_mes_data = df_plot.groupby('MonthName', observed=False)\
                                    .size().reset_index(name='Vuelos')
        ops_total_mes_data['MonthName_cat'] = pd.Categorical(
            ops_total_mes_data['MonthName'],
            categories=meses_order, ordered=True)
        ops_total_mes_data = ops_total_mes_data.sort_values('MonthName_cat')
        fig_ops_total_mes = go.Figure(go.Scatter(
            x=ops_total_mes_data['MonthName'],
            y=ops_total_mes_data['Vuelos'],
            mode='lines+markers', name='Operaciones Mensuales'))
        if ops_total_mes_data.shape[0] > 1:
            x = np.arange(len(ops_total_mes_data))
            z = np.polyfit(x, ops_total_mes_data['Vuelos'], 1)
            fig_ops_total_mes.add_trace(go.Scatter(
                x=ops_total_mes_data['MonthName'],
                y=np.poly1d(z)(x), mode='lines', name='Tendencia',
                line=dict(dash='dash')))

        # --- Series de tiempo semanales ---
        fig_vuelos_tiempo, fig_ingresos_tiempo, fig_ganancia_tiempo = \
            go.Figure(), go.Figure(), go.Figure()
        for yr in df_plot['Año'].unique():
            dfyr = df_plot[df_plot['Año'] == yr]\
                   .set_index('Fecha y hora del vuelo').sort_index()
            if dfyr.empty:
                continue
            vuelos_sem = dfyr.resample('W').size().reset_index(name='Vuelos')
            fig_vuelos_tiempo.add_scatter(x=vuelos_sem['Fecha y hora del vuelo'],
                                          y=vuelos_sem['Vuelos'],
                                          mode='lines', name=f'Año {yr}')

            ingresos_sem = dfyr['Monto total a cobrar']\
                            .resample('W').sum().reset_index()
            fig_ingresos_tiempo.add_scatter(
                x=ingresos_sem['Fecha y hora del vuelo'],
                y=ingresos_sem['Monto total a cobrar'],
                mode='lines', name=f'Año {yr}')

            ganancia_sem = dfyr['Ganancia'].resample('W').sum().reset_index()
            fig_ganancia_tiempo.add_scatter(
                x=ganancia_sem['Fecha y hora del vuelo'],
                y=ganancia_sem['Ganancia'],
                mode='lines', name=f'Año {yr}')

        # --- Top rankings por destino / operador / aeronave ---
        top_destinos_vuelos_data = df_plot.groupby(['Año', 'Destino'],
                                                   observed=False).size()\
                                          .reset_index(name='Cantidad')\
                                          .sort_values('Cantidad',
                                                       ascending=False)
        fig_top_destinos_vuelos = px.bar(top_destinos_vuelos_data,
                                         x='Destino', y='Cantidad',
                                         color='Año', barmode='group',
                                         title='Top Destinos por Vuelos')

        top_destinos_ganancia_data = df_plot.groupby(['Año', 'Destino'],
                                                     observed=False)['Ganancia']\
                                            .sum().reset_index().sort_values(
                                                'Ganancia', ascending=False)
        fig_top_destinos_ganancia = px.bar(top_destinos_ganancia_data,
                                           x='Destino', y='Ganancia',
                                           color='Año', barmode='group',
                                           title='Top Destinos por Ganancia')

        pasajeros_destino_data = df_plot.groupby(['Año', 'Destino'],
                                                 observed=False)[
                                                     'Número de pasajeros']\
                                        .sum().reset_index().sort_values(
                                            'Número de pasajeros',
                                            ascending=False)
        fig_pasajeros_destino = px.bar(pasajeros_destino_data, x='Destino',
                                       y='Número de pasajeros', color='Año',
                                       barmode='group',
                                       title='Top Destinos por Pasajeros')

        vuelos_operador_data = df_plot.groupby(['Año', 'Operador'],
                                               observed=False).size()\
                                      .reset_index(name='Vuelos')\
                                      .sort_values(['Año', 'Vuelos'],
                                                   ascending=[True, False])
        fig_vuelos_operador = px.bar(vuelos_operador_data, x='Operador',
                                     y='Vuelos', color='Año',
                                     barmode='group',
                                     title='Vuelos por Operador')

        ganancia_aeronave_data = df_plot.groupby(['Año', 'Aeronave'],
                                                 observed=False)['Ganancia']\
                                        .sum().reset_index()\
                                        .sort_values(['Año', 'Ganancia'],
                                                     ascending=[True, False])
        fig_ganancia_aeronave = px.bar(ganancia_aeronave_data, x='Aeronave',
                                       y='Ganancia', color='Año',
                                       barmode='group',
                                       title='Ganancia por Aeronave')

        top_ganancia_operador_data = df_plot.groupby('Operador',
                                                     observed=False)['Ganancia']\
                                            .sum().reset_index().sort_values(
                                                'Ganancia', ascending=False)
        fig_top_ganancia_operador = px.bar(top_ganancia_operador_data,
                                           x='Operador', y='Ganancia',
                                           title='Operadores con más Ganancia')

        top_ganancia_aeronave_data = df_plot.groupby('Aeronave',
                                                     observed=False)['Ganancia']\
                                            .sum().reset_index().sort_values(
                                                'Ganancia', ascending=False)
        fig_top_ganancia_aeronave = px.bar(top_ganancia_aeronave_data,
                                           x='Aeronave', y='Ganancia',
                                           title='Aeronaves con más Ganancia')

        # --------- NUEVOS GRÁFICOS: Tipo de nave ---------
        ganancia_tipo_data = df_plot.groupby('Tipo de aeronave',
                                             observed=False)['Ganancia']\
                                    .sum().reset_index()
        fig_ganancia_tipo_nave = px.bar(
            ganancia_tipo_data, x='Tipo de aeronave', y='Ganancia',
            text_auto='.2s', title='Ganancia Total por Tipo de Nave')
        fig_ganancia_tipo_nave.update_layout(yaxis_title='USD')

        ops_tipo_data = df_plot.groupby('Tipo de aeronave',
                                        observed=False).size()\
                               .reset_index(name='Operaciones')
        fig_ops_tipo_nave = px.bar(
            ops_tipo_data, x='Tipo de aeronave', y='Operaciones',
            text_auto=True, title='Operaciones Totales por Tipo de Nave')

        # --------- Placeholders para heatmaps ------------
        fig_heatmap_gain_destino = empty_fig
        fig_heatmap_count_destino = empty_fig
        fig_heatmap = empty_fig

        # … (lógica de heatmaps y ticket_promedio sin cambios) …
        # ---- Ticket promedio ----
        fig_ticket_promedio = px.bar(
            df_plot.groupby(['Año', 'Destino'], observed=False)[
                'Monto total a cobrar'].mean().reset_index(),
            x='Destino', y='Monto total a cobrar', color='Año',
            barmode='group', title='Ticket Promedio por Destino y Año')

        # ============ Insights IA ============
        ai_insight_comparativo = get_openai_response(
            "Analiza tendencias comparativas de vuelos, ingresos y ganancias. "
            "Da un diagnóstico y una acción poderosa.",
            f"Vuelos/mes:\n{vuelos_mes_data.head().to_string()}\n"
            f"Ingresos/mes:\n{ingresos_mes_data.head().to_string()}\n"
            f"Ganancia/mes:\n{ganancia_mes_data.head().to_string()}")

        ai_insight_vuelos = get_openai_response(
            "Analiza los top destinos por vuelos y ganancia. Sugiere acción.",
            f"{top_destinos_vuelos_data.head().to_string()}\n"
            f"{top_destinos_ganancia_data.head().to_string()}")

        ai_insight_operadores = get_openai_response(
            "Analiza rendimiento por operador y aeronave. Sugiere acción.",
            f"{vuelos_operador_data.head().to_string()}\n"
            f"{ganancia_aeronave_data.head().to_string()}")

        ai_insight_avanzado = no_ai_insight  # (déjalo así si omites heatmaps)

        # ---------- Tabla detallada ----------
        display_columns = ['Año', 'Mes', 'Fecha y hora del vuelo', 'Destino',
                           'Operador', 'Aeronave', 'Número de pasajeros',
                           'Monto total a cobrar', 'Ganancia',
                           'Cliente', 'Fase actual']
        df_table_display = df_plot[[c for c in display_columns
                                    if c in df_plot.columns]].copy()
        df_table_display['Fecha y hora del vuelo'] = \
            df_table_display['Fecha y hora del vuelo']\
            .dt.strftime('%Y-%m-%d %H:%M')
        tabla_data = df_table_display.to_dict('records')
        tabla_columns = [{'name': c, 'id': c} for c in df_table_display.columns]

        # ---------- Opciones de filtros (después de procesar) ----------
        destino_options = [{'label': d, 'value': d}
                           for d in safe_sorted_unique(
                               df_plot_original['Destino'])]
        operador_options = [{'label': o, 'value': o}
                            for o in safe_sorted_unique(
                                df_plot_original['Operador'])]
        mes_options = [{'label': m, 'value': m}
                       for m in safe_sorted_unique(
                           df_plot_original['Mes'])]
        destino_heatmap_options = [{'label': d, 'value': d}
                                   for d in safe_sorted_unique(
                                       df_plot_original['Destino'])]

        # =================== RETURN (33 ítems) ===================
        return (
            # 0-3  KPIs + opciones filtros básicos
            output_kpis_children, destino_options, operador_options, mes_options,
            # 4-8  Series mensuales
            fig_vuelos_mes, fig_ingresos_mes, fig_ganancia_mes,
            fig_ganancia_total_mes, fig_ops_total_mes,
            # 9-11 Series semanales
            fig_vuelos_tiempo, fig_ingresos_tiempo, fig_ganancia_tiempo,
            # 12-14 Destinos
            fig_top_destinos_vuelos, fig_top_destinos_ganancia,
            fig_pasajeros_destino,
            # 15-18 Operadores/Aeronaves
            fig_vuelos_operador, fig_ganancia_aeronave,
            fig_top_ganancia_operador, fig_top_ganancia_aeronave,
            # 19-20  NUEVOS charts Tipo de Nave
            fig_ganancia_tipo_nave, fig_ops_tipo_nave,
            # 21-25  Heatmaps + ticket
            destino_heatmap_options, fig_heatmap_gain_destino,
            fig_heatmap_count_destino, fig_heatmap, fig_ticket_promedio,
            # 26-28  Tabla + error
            tabla_data, tabla_columns, '',
            # 29-32  Insights IA
            ai_insight_comparativo, ai_insight_vuelos,
            ai_insight_operadores, ai_insight_avanzado
        )
