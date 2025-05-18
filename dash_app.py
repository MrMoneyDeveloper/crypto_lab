from __future__ import annotations

"""
Dash dashboard for Crypto-Lab
─────────────────────────────
Launch →  python dash_app.py
Visit  →  http://127.0.0.1:8050/
"""

import os
from typing import Any, Tuple

import dash
import pandas as pd
import requests
from dash import Dash, dcc, html, Input, Output, State, no_update

# optional icon helper
try:
    from dash_iconify import DashIconify  # pip install dash-iconify
except ImportError:
    def DashIconify(**kwargs):
        return html.Span("", **kwargs)

# ───────────────────────── configuration ─────────────────────────────────
API_BASE   = os.getenv("API_BASE",  "http://127.0.0.1:5000/api/data")
COINS      = os.getenv("COINS",     "bitcoin,ethereum").split(",")
REFRESH_MS = int(os.getenv("REFRESH_MS", "60000"))

# ───────────────────────── app setup ──────────────────────────────────────
app: Dash = Dash(__name__, title="Crypto-Lab", suppress_callback_exceptions=True)
server      = app.server
STYLE_GRAPH = {"flex": "1 1 45%", "minWidth": "300px", "height": "350px"}

# ───────────────────────── layout ─────────────────────────────────────────
app.layout = html.Div(
    [
        # Header
        html.Div(
            html.H2(
                "Crypto-Lab Dashboard",
                style={"margin": "0", "fontSize": "2rem", "fontWeight": "bold"}
            ),
            style={"textAlign": "center", "paddingBottom": "1rem", "borderBottom": "2px solid #eee"}
        ),

        # Controls row
        html.Div(
            [
                html.Label("Select Coin:", style={"marginRight": "0.5rem", "fontWeight": "600"}),
                dcc.Dropdown(
                    id="coin-dropdown",
                    options=[{"label": c.capitalize(), "value": c} for c in COINS],
                    value=COINS[0],
                    clearable=False,
                    style={"width": "200px"}
                ),
            ],
            style={"display": "flex", "alignItems": "center", "justifyContent": "flex-end", "padding": "1rem 0"}
        ),

        # Charts grid (2x2)
        html.Div(
            [
                html.Div(
                    [ html.Div("Price History", className="card-title"),
                      dcc.Graph(id="history-graph", config={"displayModeBar": False}, style={"height": "100%"}) ],
                    className="card", style={"gridArea": "history"}
                ),
                html.Div(
                    [ html.Div("24h Forecast", className="card-title"),
                      dcc.Graph(id="forecast-graph", config={"displayModeBar": False}, style={"height": "100%"}) ],
                    className="card", style={"gridArea": "forecast"}
                ),
                html.Div(
                    [ html.Div("3-Point Moving Average", className="card-title"),
                      dcc.Graph(id="ma-graph", config={"displayModeBar": False}, style={"height": "100%"}) ],
                    className="card", style={"gridArea": "ma"}
                ),
                html.Div(
                    [ html.Div("Annualized Volatility", className="card-title"),
                      dcc.Graph(id="vol-graph", config={"displayModeBar": False}, style={"height": "100%"}) ],
                    className="card", style={"gridArea": "vol"}
                ),
            ],
            style={
                "display": "grid",
                "gridTemplateAreas": """
                    "history forecast"
                    "ma      vol"
                """,
                "gridGap": "1rem",
                "gridTemplateRows": "300px 300px",
                "marginBottom": "1rem"
            }
        ),

        # CSV export + toast
        html.Div(
            [
                html.Button(
                    "📥 Download CSV",
                    id="btn-download", n_clicks=0,
                    style={
                        "backgroundColor": "#0d6efd", "color": "white", "border": "none",
                        "padding": "0.5rem 1rem", "borderRadius": "0.25rem", "cursor": "pointer"
                    }
                ),
                dcc.Download(id="download-data"),
                html.Div(id="toast", style={"marginLeft": "1rem", "color": "crimson", "fontWeight": "600"})
            ],
            style={"display": "flex", "alignItems": "center", "paddingBottom": "1rem"}
        ),

        # Auto-refresh interval (must be present for the callback)
        dcc.Interval(id="refresh-int", interval=REFRESH_MS, n_intervals=0),

        # Footer
        html.Div(
            f"Auto-updates every {REFRESH_MS//1000}s • data from CoinGecko",
            style={"textAlign": "center", "fontSize": "0.8rem", "color": "#666",
                   "borderTop": "1px solid #eee", "paddingTop": "1rem"}
        ),
    ],
    style={"maxWidth": "980px", "margin": "auto", "padding": "20px", "fontFamily": "Arial, sans-serif"}
)



# ───────────────────────── data fetcher ───────────────────────────────────
def fetch_data(coin: str) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    resp = requests.get(f"{API_BASE}/{coin}", timeout=6)
    resp.raise_for_status()
    j = resp.json()

    df_hist = pd.DataFrame(j["history"])
    df_hist["ts"] = pd.to_datetime(df_hist["ts"])

    df_fc = pd.DataFrame(j["forecast"])
    df_fc["ts"] = pd.to_datetime(df_fc["ts"])

    return df_hist, df_fc, j.get("currency", "")


# ───────────────────────── main graphs callback ───────────────────────────
@app.callback(
    Output("history-graph",  "figure"),
    Output("forecast-graph", "figure"),
    Output("ma-graph",       "figure"),
    Output("vol-graph",      "figure"),
    Output("toast",          "children"),
    Input("coin-dropdown",   "value"),
    Input("refresh-int",     "n_intervals"),
    State("history-graph",   "figure"),
    State("forecast-graph",  "figure"),
)
def update_graphs(
    coin: str,
    _tick: int,
    prev_hist: dict | None,
    prev_fc:   dict | None,
) -> Tuple[Any, Any, Any, Any, str]:
    """
    Fetch fresh data and return four Plotly figures:
      1. History price (last 12h)
      2. 24h forecast
      3. 3-point moving average
      4. Annualized volatility (3-point)
    On error, preserves previous price/forecast graphs and shows toast.
    """
    try:
        hist, fc, _ = fetch_data(coin)

        # -- Shared layout template --
        base_layout = dict(
            margin=dict(l=40, r=20, t=40, b=40),
            xaxis=dict(title="Time", showgrid=False),
            yaxis=dict(title="Price (USD)", showgrid=True),
            template="plotly_white",
        )

        # 1️⃣ History price
        hist_fig = dict(
            data=[dict(x=hist.ts, y=hist.price, mode="lines", name="Price")],
            layout={**base_layout, "title": f"{coin.capitalize()} – last 12 h"}
        )

        # 2️⃣ 24 h Forecast
        fc_fig = dict(
            data=[dict(
                x=fc.ts, y=fc.price, mode="lines", name="Forecast",
                line=dict(dash="dash")
            )],
            layout={**base_layout, "title": f"{coin.capitalize()} – next 24 h forecast"}
        )

        # 3️⃣ Moving average (3-point)
        ma_series = hist.price.rolling(3).mean()
        ma_fig = dict(
            data=[dict(x=hist.ts, y=ma_series, mode="lines", name="3-pt MA")],
            layout={**base_layout, "title": "3-Point Rolling Moving Average"}
        )

        # 4️⃣ Annualized volatility (3-period)
        vol_series = hist.price.pct_change().rolling(3).std().mul((365*24)**0.5)
        vol_fig = dict(
            data=[dict(x=hist.ts, y=vol_series, mode="lines", name="Volatility")],
            layout={**base_layout, "title": "Annualized Volatility (3-pt)"}
        )

        return hist_fig, fc_fig, ma_fig, vol_fig, ""

    except Exception as e:
        err = f"⚠️ API error: {e}"
        print(err)
        return (
            prev_hist or no_update,
            prev_fc   or no_update,
            no_update,
            no_update,
            err
        )



# ───────────────────────── run server ─────────────────────────────────────
if __name__ == "__main__":
    app.run(port=8050)
