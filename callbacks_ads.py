# callbacks_ads.py (CÓDIGO CORREGIDO Y ROBUSTO)

import os
from pathlib import Path
from datetime import datetime, timedelta
import yaml  # Se añade la importación de yaml

import plotly.express as px
from dash import Output, Input, html, dcc, ctx

from google_ads_api import (
    load_client_safe,
    fetch_ads_metrics,
    fetch_keyword_metrics,
    fetch_geo_metrics,
)
from ai import get_openai_response

# ---------- Ruta YAML (mismo directorio del proyecto) ----------
BASE_DIR  = Path(__file__).resolve().parent
YAML_PATH = BASE_DIR / "google-ads.yaml"            # credenciales

# ---------- Helper ----------
def _safe_dates(start, end):
    """Si el DatePicker todavía no ha emitido fechas, usa último 30 días."""
    if not start or not end:
        today = datetime.utcnow().date()
        start = (today - timedelta(days=30)).isoformat()
        end   = today.isoformat()
    return start, end

# ---------- Registro ----------
def register_ads_callbacks(app):
    @app.callback(
        Output("fig-ads-overview", "figure"),
        Output("fig-ads-cost",     "figure"),
        Output("fig-ads-keywords", "figure"),
        Output("fig-ads-cities",   "figure"),
        Output("ads-ai-insight-visible", "children"),
        Input("date-picker", "start_date"),
        Input("date-picker", "end_date"),
    )
    def update_ads_figures(start_date, end_date):
    # 0️⃣ Imprimir información de inicio para depuración
        print("\n" + "="*50)
        print("INICIANDO ACTUALIZACIÓN DE GRÁFICOS DE GOOGLE ADS")

        start_date, end_date = _safe_dates(start_date, end_date)
        print(f"Rango de fechas seleccionado: {start_date} a {end_date}")

        # 1️⃣ Conectar Google Ads y obtener el ID de cliente correcto
        try:
            client = load_client_safe(YAML_PATH)
            print("Cliente de Google Ads cargado exitosamente.")

            with open(YAML_PATH, 'r') as f:
                ads_config = yaml.safe_load(f)

            customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID") or ads_config.get("customer_id")
            customer_id = str(customer_id) if customer_id else None # Aseguramos que sea string
            print(f"ID de cliente para la consulta: {customer_id}")

        except Exception as err:
            print(f"!!! ERROR al cargar cliente o configuración: {err}")
            msg = html.P(f"❌ Error al cargar cliente o configuración: {str(err)}", style={"color": "red"})
            empty = {}
            print("="*50 + "\n")
            return empty, empty, empty, empty, msg

        if not customer_id:
            print("!!! ERROR: No se encontró un ID de cliente.")
            msg = html.P("⚠️ Error de configuración: Debes especificar el 'customer_id' en tu archivo google-ads.yaml.", style={"color": "red"})
            empty = {}
            print("="*50 + "\n")
            return empty, empty, empty, empty, msg

        try:
            # 2️⃣ Descarga datos
            print("\n-> Intentando descargar métricas de campañas (fetch_ads_metrics)...")
            df = fetch_ads_metrics(client, customer_id, start_date, end_date)
            print(f"Llamada a fetch_ads_metrics completada. ¿DataFrame vacío?: {df.empty}. Número de filas: {len(df)}")
            if not df.empty:
                print("Primeras filas de df:")
                print(df.head())

            print("\n-> Intentando descargar métricas de keywords (fetch_keyword_metrics)...")
            df_kw = fetch_keyword_metrics(client, customer_id, start_date, end_date)
            print(f"Llamada a fetch_keyword_metrics completada. ¿DataFrame vacío?: {df_kw.empty}. Número de filas: {len(df_kw)}")

            print("\n-> Intentando descargar métricas geográficas (fetch_geo_metrics)...")
            df_geo = fetch_geo_metrics(client, customer_id, start_date, end_date)
            print(f"Llamada a fetch_geo_metrics completada. ¿DataFrame vacío?: {df_geo.empty}. Número de filas: {len(df_geo)}")

            print("\nProcesamiento de datos completado.")
            
            if df.empty:
                print("!!! DataFrame principal (df) está vacío. No se generarán gráficos.")
                msg = html.P("No se encontraron datos de rendimiento de Google Ads en el rango de fechas seleccionado.")
                empty = {}
                print("="*50 + "\n")
                return empty, empty, empty, empty, msg

            # --- El resto del código para generar figuras es el mismo ---
            # ... (código para fig_overview, fig_cost, fig_kw, etc.)
            daily = (
                df.groupby("date")
                .agg(clicks=("clicks", "sum"),
                    impressions=("impressions", "sum"),
                    conversions=("conversions", "sum"))
                .reset_index()
            )
            fig_overview = px.bar(
                daily, x="date",
                y=["clicks", "impressions", "conversions"],
                barmode="group",
                title="Google Ads · Clics, Impresiones, Conversiones",
            )

            fig_cost = px.line(
                df.groupby("date")["cost"].sum().reset_index(),
                x="date", y="cost", title="Inversión diaria ($)",
            )
            fig_cost.update_yaxes(tickprefix="$")

            fig_kw, top_kw_name = {}, "N/A"
            if not df_kw.empty:
                top_kw_df = (
                    df_kw.groupby("keyword", as_index=False)
                        .agg(clicks=("clicks","sum"), cost=("cost","sum"))
                        .sort_values("clicks", ascending=False)
                        .head(10)
                )
                fig_kw = px.bar(top_kw_df, x="keyword", y="clicks",
                                hover_data=["cost"],
                                title="Top 10 Keywords por Clics")
                top_kw_name = top_kw_df.iloc[0]["keyword"]

            fig_city, top_city = {}, "N/A"
            if not df_geo.empty:
                top_city_df = (
                    df_geo.groupby("city", as_index=False)["clicks"]
                        .sum()
                        .sort_values("clicks", ascending=False)
                        .head(10)
                )
                fig_city = px.bar(top_city_df, x="city", y="clicks",
                                title="Top 10 Ciudades por Clics")
                top_city = top_city_df.iloc[0]["city"]

            total_spend = df["cost"].sum()
            contexto = (f"Gasto total: ${total_spend:,.2f}. "
                        f"Keyword top: {top_kw_name}. "
                        f"Ciudad top: {top_city}.")
            insight = get_openai_response(
                "Diagnostica el rendimiento de Google Ads y sugiere una acción valiente.",
                contexto
            ) if total_spend > 0 else "No hay datos suficientes para el análisis de IA."

            print("Generación de gráficos e insight completada exitosamente.")
            print("="*50 + "\n")
            return (fig_overview, fig_cost, fig_kw, fig_city, html.P(insight))

        except Exception as e:
            print(f"!!! ERROR INESPERADO durante la obtención de datos o creación de figuras: {e}")
            import traceback
            traceback.print_exc() # Imprime el rastreo completo del error
            msg = html.P(f"❌ Error durante la obtención de datos de Google Ads: {str(e)}", style={"color": "red"})
            empty = {}
            print("="*50 + "\n")
            return empty, empty, empty, empty, msg