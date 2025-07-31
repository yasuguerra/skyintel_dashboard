# data_processing.py
# -------------------------------------------------
import base64
import io
import logging
import re
from datetime import datetime, timedelta

import pandas as pd
import requests

# --- Dependencias de tu proyecto ----------------
from config import FB_ACCESS_TOKEN
from utils import query_ga  # tu wrapper de Google Analytics

# -------------------------------------------------
# 1 · Helpers genéricos
# -------------------------------------------------
def _extract_metric(ins_dict: dict, names: list[str]) -> int:
    """Devuelve el valor del primer insight cuyo name esté en `names`."""
    if not isinstance(ins_dict, dict):
        return 0
    for item in ins_dict.get("data", []):
        if item.get("name") in names:
            return item["values"][0]["value"]
    return 0


def safe_sorted_unique(series: pd.Series) -> list[str]:
    """Lista de valores únicos, limpios y ordenados alfabéticamente."""
    return sorted(
        [str(x) for x in series.dropna().unique() if str(x).strip() and str(x).lower() != "nan"]
    )


# -------------------------------------------------
# 2 · Limpieza y unificación de CSV de operaciones
# -------------------------------------------------
COLUMNAS_ESPERADAS = [
    "Fase actual",
    "Tipo de aeronave",
    "Fecha y hora del vuelo",
    "Número de pasajeros",
    "Monto total a cobrar",
    "Cliente",
    "Aeronave",
    "Operador",
    "Costo del vuelo (acordado con el operador)",
    "Horas de vuelo",
    "Mes",
    "Ganancia",
    "Destino",
    "dia",
    "nombre_dia",
    "hora",
]


def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia y formatea columnas clave de operaciones."""
    df["Fecha y hora del vuelo"] = pd.to_datetime(df["Fecha y hora del vuelo"], errors="coerce")
    df["Mes"] = df["Mes"].astype(str)
    df["hora"] = pd.to_numeric(df["hora"], errors="coerce")
    df["Ganancia"] = pd.to_numeric(df["Ganancia"], errors="coerce").fillna(0)
    df["Monto total a cobrar"] = pd.to_numeric(df["Monto total a cobrar"], errors="coerce").fillna(0)
    df["Número de pasajeros"] = pd.to_numeric(df["Número de pasajeros"], errors="coerce").fillna(0)
    return df


def _try_read_csv(decoded: bytes):
    """Intenta leer CSV en varias codificaciones comunes."""
    for enc in ("utf-8", "latin1", "cp1252"):
        try:
            return pd.read_csv(io.StringIO(decoded.decode(enc))), None
        except Exception as e:
            last_error = str(e)
    return None, (
        "No se pudo leer el archivo CSV. Intenta guardarlo como UTF-8 o Latin1. "
        f"Error original: {last_error}"
    )


def unify_data(contents: list[str], filenames: list[str]):
    """Unifica múltiples CSV subidos por el usuario en un único DataFrame."""
    if not contents or not filenames:
        empty = pd.DataFrame(columns=COLUMNAS_ESPERADAS + ["Archivo", "Año"])
        return empty, "No files uploaded or empty content."

    all_dfs = []
    for content, fname in zip(contents, filenames):
        _, content_string = content.split(",")
        decoded = base64.b64decode(content_string)
        df, err = _try_read_csv(decoded)
        if err:
            return None, err

        missing = [c for c in COLUMNAS_ESPERADAS if c not in df.columns]
        if missing:
            return None, f"El archivo '{fname}' carece de columnas requeridas: {', '.join(missing)}"

        df["Archivo"] = fname
        match = re.search(r"(\d{4})", fname)
        df["Año"] = match.group(0) if match else fname.split(".")[0]
        all_dfs.append(df)

    if not all_dfs:
        empty = pd.DataFrame(columns=COLUMNAS_ESPERADAS + ["Archivo", "Año"])
        return empty, "No valid data processed from files."

    return pd.concat(all_dfs, ignore_index=True), None


# -------------------------------------------------
# 3 · Conexión a Facebook / Instagram Graph API
# -------------------------------------------------
def _fb_request(endpoint: str, params: dict | None = None) -> dict:
    """Realiza GET a Graph API con manejo de errores."""
    base_url = "https://graph.facebook.com/v22.0/"
    params = params or {}
    params["access_token"] = FB_ACCESS_TOKEN
    try:
        resp = requests.get(f"{base_url}{endpoint}", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Graph API error en '{endpoint}': {e}")
        return {}


# ---------- Facebook ----------
def get_facebook_posts(page_id: str) -> list[dict]:
    endpoint = f"{page_id}/posts"
    params = {
        "fields": (
            "id,message,created_time,"
            "likes.summary(true),comments.summary(true),shares,"
            "insights.metric(post_impressions).period(lifetime)"
        )
    }
    return _fb_request(endpoint, params).get("data", [])


def process_facebook_posts(posts: list[dict]) -> pd.DataFrame:
    if not posts:
        cols = ["id", "message", "created_time", "likes", "comments", "shares", "impressions"]
        return pd.DataFrame(columns=cols)

    df = pd.DataFrame(posts)

    df["likes"] = (
        df["likes"].apply(lambda x: x["summary"]["total_count"]) if "likes" in df else 0
    )
    df["comments"] = (
        df["comments"].apply(lambda x: x["summary"]["total_count"]) if "comments" in df else 0
    )
    df["shares"] = (
        df["shares"].apply(lambda x: x.get("count", 0) if isinstance(x, dict) else 0)
        if "shares" in df
        else 0
    )
    df["impressions"] = df["insights"].apply(
        lambda x: _extract_metric(x, ["post_impressions"])
    )

    df["created_time"] = pd.to_datetime(df["created_time"]).dt.tz_localize(None)
    return df[["id", "message", "created_time", "likes", "comments", "shares", "impressions"]]


# ---------- Instagram ----------
def get_instagram_posts(ig_user_id: str) -> list[dict]:
    endpoint = f"{ig_user_id}/media"
    params = {
        "fields": (
            "id,caption,media_type,media_url,permalink,thumbnail_url,timestamp,"
            "username,like_count,comments_count,"
            "insights.metric(impressions,reach,total_interactions,video_views,plays)"
        )
    }
    return _fb_request(endpoint, params).get("data", [])


def process_instagram_posts(posts: list[dict]) -> pd.DataFrame:
    if not posts:
        cols = [
            "id",
            "caption",
            "media_type",
            "media_url",
            "permalink",
            "thumbnail_url",
            "timestamp",
            "username",
            "like_count",
            "comments_count",
            "impressions",
            "reach",
            "engagement",
            "video_views",
        ]
        return pd.DataFrame(columns=cols)

    df = pd.DataFrame(posts)

    df["impressions"] = df["insights"].apply(
        lambda x: _extract_metric(x, ["impressions", "plays", "reach"])
    )
    df["reach"] = df["insights"].apply(lambda x: _extract_metric(x, ["reach"]))
    df["engagement"] = df["insights"].apply(
        lambda x: _extract_metric(x, ["total_interactions", "engagement"])
    )
    df["video_views"] = df["insights"].apply(
        lambda x: _extract_metric(x, ["video_views", "plays"])
    )

    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)
    for col in ("like_count", "comments_count"):
        if col not in df.columns:
            df[col] = 0

    return df[
        [
            "id",
            "caption",
            "media_type",
            "media_url",
            "permalink",
            "thumbnail_url",
            "timestamp",
            "username",
            "like_count",
            "comments_count",
            "impressions",
            "reach",
            "engagement",
            "video_views",
        ]
    ]

# ---------- Instagram DAILY followers / content ----------
def get_instagram_daily_followers(ig_user_id: str, since: str, until: str):
    """
    Devuelve DataFrame con columnas:
    date, followers, posts, reels, stories, videos, photos
    """
    # 1) followers diarios
    metric = "follower_count"
    params = {
        "metric": metric,
        "period": "day",
        "since": since,
        "until": until,
    }
    followers = _fb_request(f"{ig_user_id}/insights", params).get("data", [])
    records = []
    for item in followers:
        for v in item.get("values", []):
            records.append({"date": v["end_time"][:10], "followers": v["value"]})

    df = pd.DataFrame(records)

    # 2) publicaciones diarias por tipo
    posts = get_instagram_posts(ig_user_id)
    df_posts = pd.DataFrame(posts)
    if not df_posts.empty and "timestamp" in df_posts.columns:
        df_posts["date"] = df_posts["timestamp"].str[:10]
        df_posts["cnt"] = 1
        pivot = (
            df_posts.pivot_table(
                index="date", columns="media_type", values="cnt", aggfunc="sum"
            )
            .fillna(0)
            .rename(
                columns={
                    "REEL": "reels",
                    "VIDEO": "videos",
                    "CAROUSEL_ALBUM": "photos",
                    "IMAGE": "photos",
                }
            )
        )
        pivot["posts"] = pivot.sum(axis=1)
        df = df.merge(pivot, on="date", how="left")

    return df.sort_values("date")


def get_instagram_demography(ig_user_id: str):
    """
    Devuelve dict con:
    - gender_pct {'M': 0.55, 'F': 0.40, 'U': 0.05}
    - age_buckets {'13-17':1, '18-24':5, ...}
    """
    params = {
        "metric": "audience_gender_age",
        "period": "lifetime",
    }
    data = _fb_request(f"{ig_user_id}/insights", params).get("data", [])
    if not data:
        return None

    raw = data[0]["values"][0]["value"]  # dict como 'F.25-34': 45
    gender_pct = {"M": 0, "F": 0, "U": 0}
    age_buckets = {}
    for k, v in raw.items():
        g, age = k.split(".")
        gender_pct[g] += v
        age_buckets[age] = age_buckets.get(age, 0) + v

    # normaliza %
    total = sum(gender_pct.values()) or 1
    gender_pct = {g: v / total for g, v in gender_pct.items()}
    return {"gender_pct": gender_pct, "age_buckets": age_buckets}


# -------------------------------------------------
# 4 · Funnel GA
# -------------------------------------------------
def get_funnel_data(steps_config: list[dict], start_date: str, end_date: str):
    """Devuelve labels y counts para un funnel basado en Google Analytics."""
    counts, labels = [], []
    for step in steps_config:
        labels.append(step["label"])
        if step["value"] == "page_view":
            df = query_ga(
                metrics=["sessions"], dimensions=["eventName"], start_date=start_date, end_date=end_date
            )
            count = int(df["sessions"].sum()) if not df.empty else 0
        else:
            df = query_ga(
                metrics=["eventCount"],
                dimensions=["eventName"],
                start_date=start_date,
                end_date=end_date,
            )
            if not df.empty:
                filtered = df[df["eventName"] == step["value"]]
                count = int(filtered["eventCount"].sum()) if not filtered.empty else 0
            else:
                count = 0
        counts.append(count)
    return labels, counts
