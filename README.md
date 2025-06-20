# Crypto‑Lab

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![CI](https://img.shields.io/badge/build-passing-brightgreen)

> **End‑to‑end crypto data lab** – ingest live BTC / ETH prices, store them as partitioned Parquet, serve them via a Flask micro‑service, forecast the next 24 hours, and visualise everything in a Dash dashboard *or* export a single‑page PDF report.

---

## ✨ Key Features

| Area              | Highlights                                                                                                         |
| ----------------- | ------------------------------------------------------------------------------------------------------------------ |
| **Data pipeline** | Hourly REST fetch → pandas DataFrame → Parquet (Hive partitions) with **schema evolution safety** & UTC timestamps |
| **Forecasting**   | AutoARIMA (statsforecast) with Holt‑Winters fallback; configurable horizon & confidence intervals                  |
| **API**           | Flask + Blueprints · JSON & CSV responses · CORS · SimpleCache layer · Prometheus metrics `/metrics`               |
| **Dashboard**     | Dash 4, Bootstrap styling, live WebSocket updates, CSV download & "Generate PDF" button                            |
| **Reporting**     | `report.py` builds a single‑page PDF (history, MA, volatility, forecast) via matplotlib/Agg                        |
| **Ops**           | APScheduler job‑store, structured NDJSON logs, `.env` for secrets, Dockerfile & docker‑compose                     |
| **Quality**       | Type hints, pre‑commit (`ruff`, `black`), smoke tests with pytest + CI badge                                       |
| **Data pipeline** | Hourly REST fetch → pandas DataFrame → Parquet partitions |
| **Forecasting**   | AutoARIMA (statsforecast) with Holt‑Winters fallback |
| **API**           | Flask JSON endpoints with simple caching and Prometheus metrics `/metrics` |
| **Dashboard**     | Dash 4, Bootstrap styling, polling updates, CSV download & "Generate PDF" button |
| **Reporting**     | `report.py` builds a single‑page PDF summary |
| **Ops**           | APScheduler background jobs and NDJSON logs configured via `.env` |

---

## 🗂 Project Structure

```text
Crypto-Lab/
├── api/
│   ├── app.py
│   └── middleware.py
│
├── core/
│   ├── data_tools.py
│   └── forecast.py
│
├── data_pipeline/
│   ├── __init__.py
│   ├── data_pipeline.py
│   └── scheduler.py
│
├── data/
│   ├── logs/
│   │   └── quotes.ndjson
│   │
│   └── parquet/
│       ├── 2025-05-18/
│       │   └── quotes.parquet
│       └── 2025-05-19/
│           └── quotes.parquet
│
├── controller.py
├── controller.log
├── dash_app.py
├── report.py
│
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── README.md
│
└── venv/
├── .env
└── README.md
```

### Directory notes (unchanged)

* **`api/`**

  * `app.py` & `middleware.py`: expose `/api/data/<coin>` endpoints for historical and forecast data.
* **`core/`**

  * `data_tools.py`: data ingestion and transformation utilities.
  * `forecast.py`: 24‑hour forecasting (AutoARIMA via *statsforecast*, with Holt–Winters fallback).
* **`data_pipeline/`**

  * `data_pipeline.py`: fetch BTC/ETH prices, build pandas DataFrames, write Parquet via PyArrow.
  * `scheduler.py`: schedule regular fetch jobs using APScheduler.
* **Root scripts**

  * `controller.py`: orchestrates pipeline and launches Flask API (includes Prometheus metrics).
  * `dash_app.py`: defines Dash UI (coin selector, charts, CSV/PDF exports).
  * `report.py`: generates PDF reports with matplotlib & PdfPages.

---

## ⚡️ Quick Start (Docker, cross‑platform)
## ⚡️ Quick Start

```bash
git clone https://github.com/MrMoneyDeveloper/crypto_lab.git
cd crypto_lab
cp .env.example .env               # edit API_BASE etc. if desired
docker compose up --build          # API → :5000, Dash → :8050
python -m venv venv && source venv/bin/activate
pip install dash dash-iconify pandas requests pyarrow statsforecast statsmodels matplotlib flask apscheduler python-dotenv prometheus-client flask-caching flask-cors Flask-Limiter
python controller.py
```

> **Tip:** `docker compose up -d` to run detached; logs in `docker compose logs -f`.

---

## 🪟 Setup and Running on **Windows** (manual)

*(Existing instructions preserved – scroll if you prefer Linux/macOS)*

### Prerequisites

1. **Python 3.8+** installed and on your `PATH`.
2. **Git** (preferred) or ability to download the ZIP from GitHub.

### 1. Obtain the source

**Via Git**

```powershell
git clone https://github.com/MrMoneyDeveloper/crypto_lab.git
cd crypto_lab
```

**Via ZIP**

1. Download `crypto_lab-main.zip` from GitHub.
2. Extract, then:

   ```powershell
   cd crypto_lab-main
   ```

### 2. Create and activate a virtual environment

```powershell
python -m venv venv
```

If activation is blocked, bypass execution policy:

```powershell
Set-ExecutionPolicy Bypass -Scope Process
.\venv\Scripts\activate
```

> After activation, your prompt shows `(venv)`, isolating project packages.

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

*(If `requirements.txt` missing)*

```powershell
pip install dash dash-iconify pandas requests pyarrow statsforecast statsmodels matplotlib flask apscheduler python-dotenv prometheus-client ruff black pytest
pip install dash dash-iconify pandas requests pyarrow statsforecast statsmodels matplotlib flask apscheduler python-dotenv prometheus-client flask-caching flask-cors Flask-Limiter
```

### 4. Configure environment variables

Create or edit `.env` in the project root; see **Environment variables** table below.

### 5. Run the controller & API

```powershell
python controller.py  # fetch prices, start API on :5000
```

### 6. Run the Dash dashboard

In a **new** terminal (still in venv):

```powershell
python dash_app.py    # dashboard on :8050
```

---

## 🐧 Setup on **Linux / macOS**

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install dash dash-iconify pandas requests pyarrow statsforecast statsmodels matplotlib flask apscheduler python-dotenv prometheus-client flask-caching flask-cors Flask-Limiter
python controller.py
```

*(the remaining steps mirror Windows)*

---

## 🔧 Environment Variables (.env)

| Key                | Default                            | Description                                        |
| ------------------ | ---------------------------------- | -------------------------------------------------- |
| `API_BASE`         | `https://api.coingecko.com/api/v3` | Upstream price source                              |
| `COINS`            | `bitcoin,ethereum`                 | Comma‑separated list of slugs to track             |
| `REFRESH_INTERVAL` | `60`                               | Scheduler run frequency in seconds                 |
| `CACHE_TTL`        | `30`                               | In‑memory cache expiry (seconds) for API responses |
| `LOG_LEVEL`        | `INFO`                             | `DEBUG` / `INFO` / `WARNING` etc.                  |
| `PORT`             | `5000`                             | Flask API port                                     |
| `COINS`            | `bitcoin,ethereum` | CoinGecko IDs to track |
| `CURRENCY`         | `usd`             | Quote currency |
| `DATA_DIR`         | `./data`          | Storage folder for Parquet and logs |
| `FETCH_INTERVAL`   | `60`              | Seconds between automatic fetches |
| `TIMEOUT`          | `10`              | HTTP timeout (seconds) |
| `MAX_RETRIES`      | `3`               | Retry attempts on API failure |
| `BACKOFF_S`        | `2`               | Back-off multiplier between retries |
| `FLASK_DEBUG`      | `1`               | Enable Flask debug mode |
| `PORT`             | `5000`            | Flask API port |
| `API_BASE`         | `http://127.0.0.1:5000/api/data` | Base URL for API used by other modules |
| `FMD_USERNAME`     | `admin`           | Flask-Monitoring-Dashboard user |
| `FMD_PASSWORD`     | `supersecret123`  | Password for FMD |
| `FMD_SECURITY_TOKEN` | *(none)*        | Security token for FMD |

---

## 📟 API Reference

> Base URL is `http://<host>:5000`

| Verb | Route                  | Purpose                                        |
| ---- | ---------------------- | ---------------------------------------------- |
| GET  | `/api/data/<coin>`     | Historical & forecast JSON (hourly)            |
| GET  | `/api/data/<coin>.csv` | Same payload as CSV download                   |
| GET  | `/api/refresh`         | Force immediate data pull & forecast recompute |
| GET  | `/api/health`          | Liveness probe (returns `{"status":"ok"}`)     |
| GET  | `/metrics`             | Prometheus metrics scrape                      |

---

## 🖥️ Dashboard

Navigate to `http://<host>:8050` and enjoy:

* Interactive selector (BTC / ETH / any tracked coin)
* Price history vs. 24 h forecast overlay
* Moving average & volatility plots
* Toast notifications for job status
* **Download CSV** and **Generate PDF report** buttons

---

## 🧪 Running Tests

```bash
pytest -q   # unit + smoke tests in tests/
```

Pre‑commit hooks auto‑run `ruff`, `black` and `pytest --quick`.

---

## 🐳 Container Images

```bash
docker build -t crypto-lab:latest .   # API + scheduler
```

*Multi‑service orchestration* (`docker-compose.yml`) includes:

```yaml
services:
  api:
    build: .
    image: crypto-lab
    ports: ["5000:5000"]
  dash:
    build: .
    command: python dash_app.py
    depends_on: [api]
    ports: ["8050:8050"]
```

---

## 🛣 Roadmap

* [ ] WebSocket push to dashboard (no polling)
* [ ] Automatic schema evolution via PyArrow 17
* [ ] GitHub Actions matrix build (Windows/macOS/Linux)
* [ ] Alpine‑based slim image (<120 MB)

---

## 🤝 Contributing

1. Fork > feature branch > PR (conventional commits).
2. Ensure `pre‑commit run --all-files` passes.
3. Update docs / tests for any new feature.
1. Fork and create a feature branch using conventional commits.
2. Format code with `ruff` and `black` before opening a PR.
3. Update documentation for any new feature.

---

## 📝 License

MIT © Mohammed Farhaan Buckas – see `LICENSE` file.
