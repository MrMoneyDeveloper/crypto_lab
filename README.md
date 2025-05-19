
# Crypto-Lab

## Project Structure

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
├── .env
├── requirements.txt
├── README.md
│
└── venv/
```

- **`api/`**  
  - `app.py` & `middleware.py`: expose `/api/data/<coin>` endpoints for historical and forecast data.
- **`core/`**  
  - `data_tools.py`: data ingestion and transformation utilities.  
  - `forecast.py`: 24-hour forecasting (AutoARIMA via statsforecast, with Holt–Winters fallback).
- **`data_pipeline/`**  
  - `data_pipeline.py`: fetch BTC/ETH prices, build pandas DataFrames, write Parquet via PyArrow.  
  - `scheduler.py`: schedule regular fetch jobs using APScheduler.
- **Root scripts**  
  - `controller.py`: orchestrates pipeline and launches Flask API.  
  - `dash_app.py`: defines Dash UI (coin selector, charts, CSV/PDF exports).  
  - `report.py`: generates PDF reports with matplotlib & PdfPages.

---

## Setup and Running on Windows

### Prerequisites

1. **Python 3.8+** installed and on your `PATH`.  
2. **Git** (preferred) or ability to download the ZIP from GitHub.

---

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

---

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

---

### 3. Install dependencies

If `requirements.txt` exists:

```powershell
pip install -r requirements.txt
```

Otherwise:

```powershell
pip install dash dash-iconify pandas requests pyarrow statsforecast statsmodels matplotlib flask apscheduler python-dotenv
```

---

### 4. (Optional) Configure environment variables

Create or edit `.env` in the project root:

```dotenv
API_BASE=http://127.0.0.1:5000/api/data
COINS=bitcoin,ethereum
REFRESH_INTERVAL=60
```

---

### 5. Run the controller & API

Ensure you’re in `crypto_lab` or `crypto_lab-main`:

```powershell
python controller.py
```

- Fetches BTC/ETH prices → `data/YYYY-MM-DD/quotes.parquet`  
- Starts Flask API on port 5000:  
  `http://127.0.0.1:5000/api/data/<coin>`

---

### 6. Run the Dash dashboard

In a new terminal (with venv active):

```powershell
python dash_app.py
```

Dash listens on port 8050 by default.

---

### 7. Open the dashboard

Navigate to:

```
http://127.0.0.1:8050/
```

Features:

- Coin selector  
- Price history & 24h forecast  
- 3-point moving average & volatility charts  
- **Download CSV** / **Generate PDF**  

Data auto-refreshes every minute.

