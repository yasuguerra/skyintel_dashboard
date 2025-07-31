
# SkyIntel Dashboard

SkyIntel Dashboard is an internal analytics tool built with [Dash](https://dash.plotly.com/) that pulls together
marketing & sales data from several sources into a single, interactive web interface.

**Main tabs**

| Tab | Source | What you get |
|-----|--------|--------------|
| Web Analytics | Google Analytics 4 | Traffic, engagement & goal conversions |
| Google Ads | Google Ads API | Spend, clicks, conversion performance with device / geo / audience breakdowns |
| Social Media | Facebook / Instagram Graph API | Post‑level impressions, engagement & follower growth |
| Sales Ops | CSV/Google Sheets | Pipeline & revenue KPI |
| AI Insights | OpenAI GPT‑4o | One‑click narrative reports summarising the numbers |

## Quick start

```bash
# 1.  Clone
git clone https://github.com/your-org/skyintel-dashboard.git
cd skyintel-dashboard

# 2.  Create a virtual‑env
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# 3.  Install deps
pip install -r requirements.txt

# 4.  Add your secrets (see **Configuration** below)

# 5.  Run it
python app.py
# open http://127.0.0.1:8052 in your browser
```

## Configuration

All secrets are injected via environment variables (preferred) **or**
a `google-ads.yaml` file for the Google Ads client.

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | API key for GPT reports |
| `GOOGLE_ADS_CONFIGURATION_FILE_PATH` | Path to your *google‑ads.yaml* creds (optional) |
| `GOOGLE_ADS_CUSTOMER_ID` | Customer account ID (e.g. `1234567890`) |
| `FACEBOOK_PAGE_TOKEN` | Long‑lived page token with `ads_read, pages_read_engagement` scopes |
| `INSTAGRAM_PAGE_ID` | Business IG page id (prefetch in *web_social.py*) |
| `GA4_PROPERTY_ID` | Numeric GA4 property id |
| `SALES_CSV` | Path or URL of your sales pipeline CSV |

Create a _.env_ file to make local development easier:

```env
OPENAI_API_KEY=sk-...
GOOGLE_ADS_CUSTOMER_ID=1234567890
FACEBOOK_PAGE_TOKEN=EAAB...
INSTAGRAM_PAGE_ID=1784...
GA4_PROPERTY_ID=34567890
SALES_CSV=data/pipeline.csv
```

## Folder structure

```
├── app.py                    # Dash bootstrapper
├── google_ads_api.py         # Thin wrapper around Google Ads GAQL queries
├── google_ads_tab.py         # Layout & callbacks for the Ads tab
├── callbacks_*               # Per‑tab callback modules
├── layout_components.py      # Re‑usable Dash/dbc helpers
├── data_processing.py        # Social & GA4 ETL helpers
└── ai.py                     # OpenAI helper utilities
```

## Development tips

* Use **debug mode** (`export FLASK_ENV=development`) for hot‑reloading.
* Each external API call is memoised with `functools.lru_cache` (see *google_ads_api.py*) – tune the `maxsize` or expire logic if you need fresher data.
* Heavy computations (e.g. NLP sentiment) should go to background jobs / Celery workers to keep the UI snappy.

## License

Private / internal – not for public redistribution.
