## Crypto-Lab

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

* **`api/`**
  * `app.py` & `middleware.py`: expose `/api/data/<coin>` endpoints for historical and forecast data.
* **`core/`**
  * `data_tools.py`: data ingestion and transformation utilities.
  * `forecast.py`: 24-hour forecasting (AutoARIMA via statsforecast, with Holt–Winters fallback).
* **`data_pipeline/`**
  * `data_pipeline.py`: fetch BTC/ETH prices, build pandas DataFrames, write Parquet via PyArrow.
  * `scheduler.py`: schedule regular fetch jobs using APScheduler.
* **Root scripts**
  * `controller.py`: orchestrates the pipeline and starts the Flask API.
  * `dash_app.py`: defines the Dash UI (coin selector, charts, CSV/PDF exports).
  * `report.py`: generates PDF reports with matplotlib & PdfPages.

---

## Setup and Running on Windows

Follow these steps to get Crypto-Lab working locally on a Windows machine.

---

### 1. Clone the repository

Open PowerShell and run:

```bash
git clone https://github.com/MrMoneyDeveloper/crypto_lab.git
cd crypto_lab
```

This will download the Crypto-Lab project into a local folder.

---

### 2. Create and activate a Python virtual environment

Still in the project folder, create a venv and activate it:

```bash
python -m venv venv
.\venv\Scripts\activate
```

> After activation, your prompt should show `(venv)`. This isolates the project’s Python packages.

---

### 3. Install dependencies

If a `requirements.txt` is included:

```bash
pip install -r requirements.txt
```

Otherwise, install the main libraries manually:

```bash
pip install dash dash-iconify pandas requests pyarrow statsforecast statsmodels matplotlib flask apscheduler python-dotenv
```

* **Dash & Dash-Iconify**: web dashboard (Python Dash framework)  
* **pandas & pyarrow**: data handling (reading/writing price series)  
* **statsforecast / statsmodels**: forecasting (AutoARIMA, Holt–Winters)  
* **matplotlib**: generating PDF reports with charts  
* **Flask & APScheduler**: background API and scheduling pipeline  
* **python-dotenv**: manage environment variables via a `.env` file  

---

### 4. (Optional) Configure environment variables

By default, the app uses:

```dotenv
API_BASE=http://127.0.0.1:5000/api/data
```

To override defaults, create or edit a `.env` file in the project root and set:

```dotenv
API_BASE=<your_api_url>
COINS=<comma_separated_coin_list>
REFRESH_INTERVAL=<seconds>
```

No changes are required for basic use.

---

### 5. Run the data controller and API

In one terminal (with the venv activated), start the data service:

```bash
python controller.py
```

This will:

* Fetch the latest Bitcoin and Ethereum prices and append them to `data/YYYY-MM-DD/quotes.parquet`.  
* Start a Flask API server on port 5000, serving endpoints like `http://127.0.0.1:5000/api/data/bitcoin`.  

You should see log messages such as:

```
Fetched X prices → data/2025-05-19/quotes.parquet
```

Keep this process running in the background.

---

### 6. Run the Dash dashboard

Open another terminal (activate the same venv) and run:

```bash
python dash_app.py
```

By default, the Dash server listens on port 8050.

---

### 7. Open the web dashboard

In your browser, navigate to:

```
http://127.0.0.1:8050/
```

You should see the Crypto-Lab dashboard UI with:

* **Coin selector**  
* **Price History**  
* **24h Forecast**  
* **3-Point Moving Average**  
* **Volatility**  

The data refreshes every minute automatically. Use **Download CSV** to save the latest historical data, or **Generate PDF** to create a timestamped report.
