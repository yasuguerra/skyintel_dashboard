import dash
import dash_bootstrap_components as dbc
from dash import html, dcc
import base64
import logging
from datetime import datetime, timedelta

# Dependencias de tu proyecto
from config import LOGO_PATH
from utils import query_ga
# Módulos refactorizados
from layout_components import create_ops_sales_layout, create_web_social_layout
from ops_sales import register_ops_sales_callbacks
from web_social import register_web_social_callbacks

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
app.title = "SkyIntel Dashboard"

# --- Lógica de inicialización (ej. fechas para el DatePicker) ---
START_DATE_GLOBAL = '2023-01-01'
END_DATE_GLOBAL = 'today'
try:
    df_acquisition_init = query_ga(metrics=['sessions'], dimensions=['date'], start_date=START_DATE_GLOBAL, end_date=END_DATE_GLOBAL)
    if not df_acquisition_init.empty:
        df_acquisition_init.rename(columns={'date': 'Fecha'}, inplace=True)
        min_date_allowed = df_acquisition_init['Fecha'].min().date()
        max_date_allowed = df_acquisition_init['Fecha'].max().date()
        start_date_val = (max_date_allowed - timedelta(days=30))
        end_date_val = max_date_allowed
    else:
        raise ValueError("No initial data for DatePicker")
except Exception as e:
    logging.warning(f"Could not load initial dates for DatePicker from GA4: {e}. Using default past year.")
    min_date_allowed = (datetime.now() - timedelta(days=365)).date()
    max_date_allowed = datetime.now().date()
    start_date_val = (max_date_allowed - timedelta(days=30))
    end_date_val = max_date_allowed
logging.info(f"DatePicker initialized: min={min_date_allowed}, max={max_date_allowed}, start={start_date_val}, end={end_date_val}")


# --- Carga del Logo ---
try:
    logo_encoded = base64.b64encode(open(LOGO_PATH, 'rb').read()).decode()
    logo_src = f'data:image/png;base64,{logo_encoded}'
except (FileNotFoundError, TypeError):
    logging.warning(f"Archivo de logo '{LOGO_PATH}' no encontrado o ruta no válida. Se omitirá el logo.")
    logo_src = ""


# --- Layout Principal de la App ---
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.Img(src=logo_src, style={'height': '100px', 'margin': '10px'}), width='auto'),
        dbc.Col(html.H1('SkyIntel Dashboard – AI Insights', style={'textAlign': 'center', 'color': '#002859', 'fontWeight': 'bold', 'paddingTop': '20px'}), width=True),
    ], align="center", className="mb-4"),
    dcc.Tabs(id='main-tabs', value='ops_sales', children=[
        dcc.Tab(label='Operaciones y Ventas', value='ops_sales', children=create_ops_sales_layout()),
        dcc.Tab(label='Análisis Web y Redes Sociales', value='web_social', children=create_web_social_layout(min_date_allowed, max_date_allowed, start_date_val, end_date_val)),
    ]),
], fluid=True, style={'background': '#FFFFFF'})


# --- Registro de Callbacks ---
register_ops_sales_callbacks(app)
register_web_social_callbacks(app)


# --- Ejecución de la App ---
if __name__ == '__main__':
    app.run(debug=True, port=8052)