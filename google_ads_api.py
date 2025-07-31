# google_ads_api.py
# -----------------------------------------------------------
# Helper para consultar métricas de Google Ads en SkyIntel
# -----------------------------------------------------------
from __future__ import annotations
import os
from pathlib import Path
from datetime import date, timedelta
from typing import Dict, List
import pandas as pd
from google.ads.googleads.client import GoogleAdsClient
from google.auth.exceptions import RefreshError
from functools import lru_cache

@lru_cache(maxsize=1)
def get_client() -> GoogleAdsClient:
    """Singleton de GoogleAdsClient para toda la sesión."""
    return load_client_safe()

# ────────────────────────────────────────────────────────────
# 1) Localizar YAML de configuración
# ────────────────────────────────────────────────────────────
PROJECT_YAML: Path = Path(__file__).resolve().parent / "google-ads.yaml"

# ────────────────────────────────────────────────────────────
# 2) Cliente Google Ads
# ────────────────────────────────────────────────────────────
def load_client(config_path: str | os.PathLike | None = None) -> GoogleAdsClient:
    if config_path:
        return GoogleAdsClient.load_from_storage(str(config_path))
    env_path = os.getenv("GOOGLE_ADS_CONFIGURATION_FILE_PATH")
    if env_path:
        return GoogleAdsClient.load_from_storage(env_path)
    if PROJECT_YAML.exists():
        return GoogleAdsClient.load_from_storage(str(PROJECT_YAML))
    return GoogleAdsClient.load_from_storage()

def load_client_safe(config_path: str | os.PathLike | None = None) -> GoogleAdsClient:
    try:
        return load_client(config_path)
    except RefreshError as exc:
        raise RuntimeError("⛔ Error al refrescar el token de Google Ads.") from exc

# ────────────────────────────────────────────────────────────
# 3) GAQL queries
# ────────────────────────────────────────────────────────────
GAQL_ADS_METRICS = """
SELECT
  segments.date,
  campaign.name,
  campaign.status,
  metrics.clicks,
  metrics.impressions,
  metrics.conversions,
  metrics.cost_micros,
  metrics.ctr,
  metrics.average_cpc
FROM campaign
WHERE segments.date BETWEEN '{start}' AND '{end}'
  AND campaign.status = 'ENABLED'
"""

GAQL_GEO = """
SELECT
  segments.date,
  segments.geo_target_city,
  metrics.clicks,
  metrics.impressions,
  metrics.conversions,
  metrics.cost_micros
FROM user_location_view
WHERE segments.date BETWEEN '{start}' AND '{end}'
  AND segments.geo_target_city IS NOT NULL
  AND metrics.clicks > 0
"""

# Query para obtener nombres de ciudades directamente
GAQL_GEO_NAMES = """
SELECT
  geo_target_constant.resource_name,
  geo_target_constant.name,
  geo_target_constant.canonical_name,
  geo_target_constant.country_code,
  geo_target_constant.target_type
FROM geo_target_constant
WHERE geo_target_constant.resource_name IN ({resource_names})
"""

GAQL_DEVICE = """
SELECT
  segments.device,
  metrics.clicks,
  metrics.impressions,
  metrics.conversions,
  metrics.cost_micros
FROM campaign
WHERE segments.date BETWEEN '{start}' AND '{end}'
"""

GAQL_AGE = """
SELECT
  ad_group_criterion.age_range.type,
  metrics.clicks,
  metrics.conversions,
  metrics.cost_micros
FROM age_range_view
WHERE segments.date BETWEEN '{start}' AND '{end}'
"""

GAQL_GENDER = """
SELECT
  ad_group_criterion.gender.type,
  metrics.clicks,
  metrics.conversions,
  metrics.cost_micros
FROM gender_view
WHERE segments.date BETWEEN '{start}' AND '{end}'
"""

GAQL_KEYWORD = """
SELECT
  segments.date,
  ad_group_criterion.keyword.text,
  metrics.clicks,
  metrics.impressions,
  metrics.conversions,
  metrics.cost_micros
FROM keyword_view
WHERE segments.date BETWEEN '{start}' AND '{end}'
  AND ad_group_criterion.status IN ('ENABLED','PAUSED')
"""

GAQL_ADGROUP = """
SELECT
  ad_group.name,
  metrics.clicks,
  metrics.impressions,
  metrics.ctr,
  metrics.average_cpc,
  metrics.conversions
FROM ad_group
WHERE segments.date BETWEEN '{start}' AND '{end}'
  AND ad_group.status IN ('ENABLED','PAUSED')
"""

# ────────────────────────────────────────────────────────────
# 4) Helper genérico
# ────────────────────────────────────────────────────────────
def _run_gaql(client: GoogleAdsClient, customer_id: str, query: str) -> List:
    service = client.get_service("GoogleAdsService")
    stream = service.search_stream(customer_id=customer_id, query=query)
    rows = []
    for batch in stream:
        for r in batch.results:
            rows.append(r)
    return rows

# ────────────────────────────────────────────────────────────
# 5) Funciones de alto nivel
# ────────────────────────────────────────────────────────────
def _get_customer_id(config_path: str | os.PathLike | None = None) -> str:
    cid = os.getenv("GOOGLE_ADS_CUSTOMER_ID")
    if cid:
        return str(cid)
    path = Path(config_path or PROJECT_YAML)
    if path.exists():
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        cid_yaml = data.get("customer_id")
        if cid_yaml:
            return str(cid_yaml)
    return ""

# ---------- Rendimiento básico ----------
def fetch_ads_metrics(client, customer_id, start, end) -> pd.DataFrame:
    raw = _run_gaql(client, customer_id, GAQL_ADS_METRICS.format(start=start, end=end))
    rows = [{
        "date": r.segments.date,
        "campaign": r.campaign.name,
        "clicks": r.metrics.clicks,
        "impressions": r.metrics.impressions,
        "conversions": r.metrics.conversions,
        "ctr": float(r.metrics.ctr) * 100,
        "cpc":  r.metrics.average_cpc / 1_000_000,
        "cost": r.metrics.cost_micros / 1_000_000,
    } for r in raw]
    return pd.DataFrame(rows)

# ---------- GEO ----------
# Cache global para nombres de ciudades
_city_name_cache = {}

def _extract_geo_id(resource_name: str) -> str:
    """Extrae el ID numérico del resource name de geo targeting"""
    try:
        parts = str(resource_name).split("/")
        if "geoTargetConstants" in parts:
            idx = parts.index("geoTargetConstants")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        return parts[-1]
    except:
        return str(resource_name).split("/")[-1]

def _get_geo_names_via_query(resource_names: List[str]) -> Dict[str, str]:
    """
    Obtiene nombres de ciudades usando GAQL en lugar del servicio directo.
    """
    if not resource_names:
        return {}
    
    try:
        client = get_client()
        cid = _get_customer_id()
        
        # Formatear resource names para la query
        formatted_names = "','".join(resource_names)
        query = GAQL_GEO_NAMES.format(resource_names=f"'{formatted_names}'")
        
        raw = _run_gaql(client, cid, query)
        
        name_map = {}
        for r in raw:
            resource_name = r.geo_target_constant.resource_name
            
            # Obtener el mejor nombre disponible
            name = "N/A"
            if hasattr(r.geo_target_constant, 'canonical_name') and r.geo_target_constant.canonical_name:
                name = r.geo_target_constant.canonical_name
            elif hasattr(r.geo_target_constant, 'name') and r.geo_target_constant.name:
                name = r.geo_target_constant.name
            
            name_map[resource_name] = name
            
            # También mapear por ID
            geo_id = _extract_geo_id(resource_name)
            _city_name_cache[geo_id] = name
        
        return name_map
        
    except Exception as e:
        print(f"⚠️ Error obteniendo nombres via query: {e}")
        return {}

def fetch_geo_performance(start_date: date, end_date: date) -> pd.DataFrame:
    """
    Obtiene rendimiento por ubicación geográfica con nombres de ciudades reales.
    Usa GAQL para obtener los nombres en lugar del servicio directo.
    """
    client = get_client()
    cid = _get_customer_id()
    
    try:
        raw = _run_gaql(client, cid, GAQL_GEO.format(
            start=start_date.isoformat(), 
            end=end_date.isoformat()
        ))
    except Exception as e:
        print(f"⚠️ Error ejecutando query GEO: {e}")
        return pd.DataFrame(columns=["city", "clicks", "conv", "cost"])

    if not raw:
        return pd.DataFrame(columns=["city", "clicks", "conv", "cost"])

    print(f"📊 Procesando {len(raw)} registros de ubicaciones...")

    # Extraer resource names únicos y datos
    resource_names = set()
    raw_data = []
    
    for r in raw:
        resource_name = str(r.segments.geo_target_city)
        resource_names.add(resource_name)
        
        raw_data.append({
            "resource_name": resource_name,
            "clicks": r.metrics.clicks,
            "conv": r.metrics.conversions,
            "cost": r.metrics.cost_micros / 1_000_000,
        })

    print(f"🔍 Obteniendo nombres para {len(resource_names)} ubicaciones únicas...")
    
    # Obtener nombres usando GAQL
    if len(resource_names) <= 100:  # Límite razonable para la query
        geo_names = _get_geo_names_via_query(list(resource_names))
    else:
        # Procesar en lotes si hay demasiados
        geo_names = {}
        resource_list = list(resource_names)
        batch_size = 100
        
        for i in range(0, len(resource_list), batch_size):
            batch = resource_list[i:i + batch_size]
            batch_names = _get_geo_names_via_query(batch)
            geo_names.update(batch_names)

    # Construir DataFrame final
    rows = []
    for data in raw_data:
        resource_name = data["resource_name"]
        geo_id = _extract_geo_id(resource_name)
        
        # Intentar obtener nombre del mapeo, luego del cache, luego usar ID
        city_name = (geo_names.get(resource_name) or 
                    _city_name_cache.get(geo_id) or 
                    f"Ciudad {geo_id}")
        
        rows.append({
            "city": city_name,
            "clicks": data["clicks"],
            "conv": data["conv"],
            "cost": data["cost"],
        })

    df = pd.DataFrame(rows)
    
    # Agrupar por ciudad en caso de duplicados
    if not df.empty:
        df = df.groupby("city", as_index=False).sum().sort_values("clicks", ascending=False)
    
    print(f"✅ Procesamiento GEO completado. {len(df)} ubicaciones finales.")
    return df

def debug_geo_data(start_date: date, end_date: date, limit: int = 10) -> None:
    """Función para debugging de datos geo con límite configurable"""
    client = get_client()
    cid = _get_customer_id()
    raw = _run_gaql(client, cid, GAQL_GEO.format(start=start_date.isoformat(), end=end_date.isoformat()))
    
    print(f"📊 Encontrados {len(raw)} registros geo")
    print(f"🔍 Mostrando primeros {min(limit, len(raw))} registros:")
    
    # Recopilar resource names únicos para obtener nombres
    resource_names = []
    for i, r in enumerate(raw[:limit]):
        resource_name = str(r.segments.geo_target_city)
        resource_names.append(resource_name)
    
    # Obtener nombres
    geo_names = _get_geo_names_via_query(resource_names)
    
    for i, r in enumerate(raw[:limit]):
        resource_name = str(r.segments.geo_target_city)
        geo_id = _extract_geo_id(resource_name)
        city_name = geo_names.get(resource_name, f"Ciudad {geo_id}")
        
        print(f"{i+1:2d}. Resource: {resource_name}")
        print(f"    → ID: {geo_id}")
        print(f"    → Nombre: {city_name}")
        print(f"    → Clicks: {r.metrics.clicks}")
        print("    " + "-"*50)

# ---------- DEVICE ----------
def fetch_device_performance(start_date: date, end_date: date) -> pd.DataFrame:
    client = get_client()
    cid = _get_customer_id()
    raw = _run_gaql(client, cid, GAQL_DEVICE.format(start=start_date.isoformat(), end=end_date.isoformat()))
    rows = [{
        "device":        r.segments.device.name,
        "clicks":        r.metrics.clicks,
        "conversions":   r.metrics.conversions,
        "cost":          r.metrics.cost_micros / 1_000_000,
    } for r in raw]
    df = pd.DataFrame(rows)
    return df.groupby("device", as_index=False).sum()

# ---------- AGE ----------
_age_map = {
    "AGE_RANGE_18_24": "18-24", "AGE_RANGE_25_34": "25-34", "AGE_RANGE_35_44": "35-44",
    "AGE_RANGE_45_54": "45-54", "AGE_RANGE_55_64": "55-64", "AGE_RANGE_65_UP": "65+",
    "AGE_RANGE_UNDETERMINED": "N/D",
}

def fetch_age_performance(start_date: date, end_date: date) -> pd.DataFrame:
    client = get_client()
    cid = _get_customer_id()
    raw = _run_gaql(client, cid, GAQL_AGE.format(start=start_date.isoformat(), end=end_date.isoformat()))
    rows = [{
        "age_range": _age_map.get(r.ad_group_criterion.age_range.type.name, "N/D"),
        "clicks":    r.metrics.clicks,
        "conv":      r.metrics.conversions,
        "cost":      r.metrics.cost_micros / 1_000_000,
    } for r in raw]
    return pd.DataFrame(rows).groupby("age_range", as_index=False).sum()

# ---------- GENDER ----------
_gender_map = {"MALE": "Hombre", "FEMALE": "Mujer", "UNDETERMINED": "N/D", "UNKNOWN": "Desconocido"}

def fetch_gender_performance(start_date: date, end_date: date) -> pd.DataFrame:
    client = get_client()
    cid = _get_customer_id()
    raw = _run_gaql(client, cid, GAQL_GENDER.format(start=start_date.isoformat(), end=end_date.isoformat()))
    rows = [{
        "gender": _gender_map.get(r.ad_group_criterion.gender.type.name, "Otro"),
        "clicks": r.metrics.clicks,
        "conv":   r.metrics.conversions,
        "cost":   r.metrics.cost_micros / 1_000_000,
    } for r in raw]
    return pd.DataFrame(rows).groupby("gender", as_index=False).sum()

# ---------- Daily ----------
def fetch_daily_performance(start_date: date, end_date: date) -> pd.DataFrame:
    client = get_client()
    cid = _get_customer_id()
    df = fetch_ads_metrics(client, cid, start_date.isoformat(), end_date.isoformat())
    if df.empty:
        return pd.DataFrame(columns=["date", "spend", "clicks", "conversions"])
    return (
        df.groupby("date", as_index=False)
          .agg(spend=("cost","sum"), clicks=("clicks","sum"), conversions=("conversions","sum"))
          .sort_values("date")
    )

# ---------- Campaign ----------
def fetch_campaign_performance(start_date: date, end_date: date) -> pd.DataFrame:
    client = get_client()
    cid = _get_customer_id()
    df = fetch_ads_metrics(client, cid, start_date.isoformat(), end_date.isoformat())
    if df.empty:
        return pd.DataFrame(columns=["campaign","spend","clicks","conversions","cpc","cpa","roas"])
    agg = (df.groupby("campaign", as_index=False)
             .agg(spend=("cost","sum"), clicks=("clicks","sum"), conversions=("conversions","sum"))
             .sort_values("spend", ascending=False))
    agg["cpc"] = agg.spend / agg.clicks.replace({0: None})
    agg["cpa"] = agg.spend / agg.conversions.replace({0: None})
    agg["roas"]= agg.conversions / agg.spend.replace({0: None})
    return agg

# ---------- Keywords ----------
def fetch_keyword_performance(start_date: date, end_date: date) -> pd.DataFrame:
    client = get_client()
    cid = _get_customer_id()
    raw = _run_gaql(client, cid, GAQL_KEYWORD.format(start=start_date.isoformat(), end=end_date.isoformat()))
    if not raw:
        return pd.DataFrame(columns=["date", "keyword", "clicks", "impressions", "conversions", "cost"])
    rows = [{
        "date": r.segments.date,
        "keyword": r.ad_group_criterion.keyword.text,
        "clicks": r.metrics.clicks,
        "impressions": r.metrics.impressions,
        "conversions": r.metrics.conversions,
        "cost": r.metrics.cost_micros / 1_000_000,
    } for r in raw]
    return pd.DataFrame(rows)

# ---------- Overview ----------
def fetch_overview(start_date: date, end_date: date) -> Dict[str, float]:
    client = get_client()
    cid = _get_customer_id()

    df_now  = fetch_ads_metrics(client, cid, start_date.isoformat(), end_date.isoformat())
    period_days = (end_date - start_date).days + 1
    prev_start, prev_end = start_date - timedelta(days=period_days), start_date - timedelta(days=1)
    df_prev = fetch_ads_metrics(client, cid, prev_start.isoformat(), prev_end.isoformat())

    def tot(df, col): return df[col].sum() if not df.empty else 0.0
    curr = {k: tot(df_now,k)  for k in ["clicks","impressions","conversions","cost"]}
    prev = {k: tot(df_prev,k) for k in ["clicks","impressions","conversions","cost"]}

    pct = lambda c,o: 0.0 if o==0 else (c-o)/o*100
    avg_cpc  = curr["cost"]/curr["clicks"]          if curr["clicks"] else 0.0
    prev_cpc = prev["cost"]/prev["clicks"]          if prev["clicks"] else 0.0
    ctr      = curr["clicks"]/curr["impressions"]   if curr["impressions"] else 0.0
    prev_ctr = prev["clicks"]/prev["impressions"]   if prev["impressions"] else 0.0
    roas     = curr["conversions"]/curr["cost"]     if curr["cost"] else 0.0
    prev_roas= prev["conversions"]/prev["cost"]     if prev["cost"] else 0.0

    return {
        "spend": round(curr["cost"],2),          "delta_spend":  pct(curr["cost"], prev["cost"]),
        "clicks": int(curr["clicks"]),           "delta_clicks": pct(curr["clicks"], prev["clicks"]),
        "impr": int(curr["impressions"]),        "delta_impr":   pct(curr["impressions"], prev["impressions"]),
        "ctr": round(ctr*100,2),                 "delta_ctr":    pct(ctr, prev_ctr),
        "conv": round(curr["conversions"],2),    "delta_conv":   pct(curr["conversions"], prev["conversions"]),
        "cpc": round(avg_cpc,2),                 "delta_cpc":    pct(avg_cpc, prev_cpc),
        "roas": round(roas,2),                   "delta_roas":   pct(roas, prev_roas),
    }

# ---------- AdGroup ----------
def fetch_adgroup_performance(start_date: date, end_date: date) -> pd.DataFrame:
    client = get_client()
    cid = _get_customer_id()
    raw = _run_gaql(client, cid, GAQL_ADGROUP.format(start=start_date.isoformat(), end=end_date.isoformat()))
    rows = [{
        "ad_group":     r.ad_group.name,
        "clicks":       r.metrics.clicks,
        "impr":         r.metrics.impressions,
        "ctr":          r.metrics.ctr,
        "avg_cpc":      r.metrics.average_cpc,
        "conv":         r.metrics.conversions,
    } for r in raw]
    return pd.DataFrame(rows).sort_values("clicks", ascending=False)

# -----------------------------------------------------------
# END OF MODULE
# -----------------------------------------------------------