Thought for a second

```markdown
## Crypto-Lab

### Setup and Running on Windows

Follow these steps to get Crypto-Lab running locally on a Windows machine.

1. **Clone the repository**  
   ```bash
   git clone https://github.com/MrMoneyDeveloper/crypto_lab.git
   cd crypto_lab
   ```

2. **Create and activate a Python virtual environment**  
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. **Install dependencies**  
   ```bash
   pip install -r requirements.txt
   ```  
   _Or, if there’s no `requirements.txt`:_  
   ```bash
   pip install dash dash-iconify pandas requests pyarrow statsforecast statsmodels matplotlib flask apscheduler python-dotenv
   ```

4. **(Optional) Configure environment variables**  
   Create or edit a `.env` file in the project root to override defaults:
   ```dotenv
   API_BASE=http://127.0.0.1:5000/api/data
   COINS=bitcoin,ethereum
   REFRESH_INTERVAL=60
   ```

5. **Run the data controller and API**  
   ```bash
   python controller.py
   ```
   - Fetches BTC/ETH prices → `data/YYYY-MM-DD/quotes.parquet`  
   - Starts Flask API on port 5000 (`/api/data/<coin>`)

6. **Run the Dash dashboard**  
   ```bash
   python dash_app.py
   ```
   - Dash server listens on port 8050

7. **Open the web dashboard**  
   Navigate your browser to `http://127.0.0.1:8050/` to view:
   - Coin selector  
   - Price History  
   - 24h Forecast  
   - 3-Point Moving Average  
   - Volatility  
   - “Download CSV” & “Generate PDF” buttons

8. **Verify the API**  
   ```bash
   curl http://127.0.0.1:5000/api/data/bitcoin
   ```

---

**Expected outputs:**  
- **Controller terminal:** logs showing price fetches and scheduling actions  
- **Dash terminal:** server start message; no critical errors if API is reachable  
- **Browser:** dark-themed dashboard with all charts rendered  
- **Generated files:**  
  - Timestamped PDF reports in output directory  
  - CSV exports when clicking “Download CSV”

You now have Crypto-Lab running locally on Windows:  
- Dashboard → `http://localhost:8050/`  
- API → `http://localhost:5000/api/data/<coin>`
```
