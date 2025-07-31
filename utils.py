import pandas as pd
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
from google.oauth2 import service_account
import logging
from config import GA_PROPERTY_ID, GA_KEY_PATH

logging.basicConfig(level=logging.INFO)

def query_ga(metrics, dimensions, start_date='30daysAgo', end_date='today', property_id=GA_PROPERTY_ID, key_path=GA_KEY_PATH):
    """Función genérica para consultar datos de GA4."""
    try:
        credentials = service_account.Credentials.from_service_account_file(
            key_path, scopes=['https://www.googleapis.com/auth/analytics.readonly']
        )
        ga_client = BetaAnalyticsDataClient(credentials=credentials)
        request = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name=d) for d in dimensions],
            metrics=[Metric(name=m) for m in metrics],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            keep_empty_rows=True
        )
        response = ga_client.run_report(request)
        rows = []
        dim_headers = [d.name for d in response.dimension_headers]
        metric_headers = [m.name for m in response.metric_headers]

        for row in response.rows:
            d_values = {dim_headers[i]: row.dimension_values[i].value for i in range(len(dim_headers))}
            m_values = {}
            for i in range(len(metric_headers)):
                value_str = row.metric_values[i].value
                try:
                    m_values[metric_headers[i]] = float(value_str)
                except (ValueError, TypeError):
                    m_values[metric_headers[i]] = 0.0
            rows.append({**d_values, **m_values})

        if not rows:
            logging.warning(f"No se devolvieron datos para: {metrics}, {dimensions}")
            return pd.DataFrame(columns=dimensions + metrics)

        df = pd.DataFrame(rows)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d', errors='coerce')
        if 'firstSessionDate' in df.columns:
            df['firstSessionDate'] = pd.to_datetime(df['firstSessionDate'], format='%Y%m%d', errors='coerce')
        if 'nthDay' in df.columns:
            df['nthDay'] = pd.to_numeric(df['nthDay'], errors='coerce').fillna(0).astype(int)

        for m in metrics:
            if m in df.columns:
                df[m] = pd.to_numeric(df[m], errors='coerce').fillna(0)

        return df.dropna(subset=[col for col in ['date', 'firstSessionDate'] if col in df.columns])
    except Exception as e:
        logging.error(f"Error consultando GA4 ({metrics}/{dimensions}): {e}")
        return pd.DataFrame(columns=dimensions + metrics)