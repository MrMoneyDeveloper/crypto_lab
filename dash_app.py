from __future__ import annotations

"""
Dash dashboard for Crypto-Lab
─────────────────────────────
Launch →  python dash_app.py
Visit  →  http://127.0.0.1:8050/
"""

import logging
import os
from typing import Any, Tuple

import pandas as pd
import requests
from dash import Dash, dcc, html, Input, Output, State, no_update
import dash_bootstrap_components as dbc
from report import generate_report

# ---------------------- Logging Setup ----------------------
logger = logging.getLogger("dash_app")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(ch)

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
app: Dash = Dash(
    __name__,
    title="Crypto-Lab",
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)
server = app.server

# ───────────────────────── shared card style ──────────────────────────────
CARD_STYLE = {
    "padding": "1rem",
    "borderRadius": "8px",
    "boxShadow": "0 2px 6px rgba(0,0,0,0.2)",
    "backgroundColor": "rgba(0, 0, 0, 0.6)",
    "color": "#fff",
    "display": "flex",
    "flexDirection": "column",
    "minHeight": 0,              # allow flex children to shrink
}

# ───────────────────────── layout ─────────────────────────────────────────
app.layout = html.Div(
    [
        dcc.Store(id="alerts-store", data=[]),
        html.Div(id="toast-container"),

        # HEADER
html.Header(
    children=[
        DashIconify(
            icon="logos:bitcoin",
            width=30,
            style={
                "marginRight": "0.5rem",
                "color": "#f2a900",
            },
        ),
        html.Span(
            "Crypto-Lab Dashboard",
            style={
                "fontSize": "1.5rem",
                "color": "#fff",
                "fontWeight": "600",
            },
        ),
    ],
    style={
        "display":         "flex",
        "alignItems":      "center",
        "padding":         "0.75rem 2rem",
        "backgroundColor": "rgba(0, 0, 0, 0.7)",
        "borderBottom":    "1px solid rgba(255, 255, 255, 0.2)",
        "backdropFilter":  "blur(4px)",
    },
),

        # HERO INTRO
        html.Div(
            html.Div(
                [
                    html.H1("Welcome to Crypto-Lab", style={"color": "#fff", "marginBottom": "0.25rem"}),
                    html.H4("Live insights into Bitcoin & Ethereum", style={"color": "#ddd", "marginTop": 0}),
                    html.P(
                        "Bitcoin (BTC) is the original cryptocurrency, launched in 2009. "
                        "Ethereum (ETH) introduced smart contracts in 2015, powering DeFi, NFTs, and more. "
                        "Use the selector below to switch between them and explore price history, forecasts, "
                        "moving averages, and volatility—all in one place.",
                        style={"color": "#eee", "maxWidth": "600px", "lineHeight": "1.4", "margin": "0 auto"},
                    ),
                ],
                style={"textAlign": "center", "padding": "2rem 1rem",
                       "backgroundColor": "rgba(0,0,0,0.5)", "borderRadius": "10px", "maxWidth": "800px"},
            ),
            style={"display": "flex", "justifyContent": "center", "padding": "2rem 0"},
        ),

        # CONTROLS
        html.Div(
            [
                html.Label("Select Coin:",
                           style={"marginRight": "0.5rem", "fontWeight": 600, "color": "#eee"}),
                dcc.Dropdown(
                    id="coin-dropdown",
                    options=[{"label": c.capitalize(), "value": c} for c in COINS],
                    value=COINS[0],
                    clearable=False,
                    style={"width": "160px"},
                ),
            ],
            style={"display": "flex", "justifyContent": "flex-end",
                   "padding": "1rem 2rem", "backgroundColor": "rgba(0,0,0,0.4)"},
        ),

        # CHART GRID
        html.Div(
            [
                # Price History
                html.Div(
                    [
                        html.Div(
                            [
                                html.Span("Price History", style={"color": "#fff", "fontWeight": "600"}),
                                html.Span(" ℹ️",
                                          title="Last 12h of prices",
                                          style={"cursor": "help", "marginLeft": "0.25rem"}),
                            ],
                            style={"marginBottom": "0.5rem", "display": "flex", "alignItems": "center"},
                        ),
                        # make the loader + graph flex to fill the card
                        html.Div(
                            dcc.Loading(
                                id="loading-history",
                                type="circle",
                                children=[dcc.Graph(
                                    id="history-graph",
                                    config={"displayModeBar": False, "responsive": True},
                                    style={"width": "100%", "height": "100%"},
                                )],
                            ),
                            style={"flex": 1, "minHeight": 0},
                        ),
                    ],
                    style={**CARD_STYLE, "gridArea": "history"},
                ),

                # 24h Forecast
                html.Div(
                    [
                        html.Div(
                            [
                                html.Span("24 h Forecast", style={"color": "#fff", "fontWeight": "600"}),
                                html.Span(" ℹ️",
                                          title="Next 24 h forecast",
                                          style={"cursor": "help", "marginLeft": "0.25rem"}),
                            ],
                            style={"marginBottom": "0.5rem", "display": "flex", "alignItems": "center"},
                        ),
                        html.Div(
                            dcc.Loading(
                                id="loading-forecast",
                                type="circle",
                                children=[dcc.Graph(
                                    id="forecast-graph",
                                    config={"displayModeBar": False, "responsive": True},
                                    style={"width": "100%", "height": "100%"},
                                )],
                            ),
                            style={"flex": 1, "minHeight": 0},
                        ),
                    ],
                    style={**CARD_STYLE, "gridArea": "forecast"},
                ),

                # 3-Point MA
                html.Div(
                    [
                        html.Div(
                            [
                                html.Span("3-Point MA", style={"color": "#fff", "fontWeight": "600"}),
                                html.Span(" ℹ️",
                                          title="3-period rolling MA",
                                          style={"cursor": "help", "marginLeft": "0.25rem"}),
                            ],
                            style={"marginBottom": "0.5rem", "display": "flex", "alignItems": "center"},
                        ),
                        html.Div(
                            dcc.Loading(
                                id="loading-ma",
                                type="circle",
                                children=[dcc.Graph(
                                    id="ma-graph",
                                    config={"displayModeBar": False, "responsive": True},
                                    style={"width": "100%", "height": "100%"},
                                )],
                            ),
                            style={"flex": 1, "minHeight": 0},
                        ),
                    ],
                    style={**CARD_STYLE, "gridArea": "ma"},
                ),

                # Volatility
                html.Div(
                    [
                        html.Div(
                            [
                                html.Span("Volatility", style={"color": "#fff", "fontWeight": "600"}),
                                html.Span(" ℹ️",
                                          title="Annualized volatility",
                                          style={"cursor": "help", "marginLeft": "0.25rem"}),
                            ],
                            style={"marginBottom": "0.5rem", "display": "flex", "alignItems": "center"},
                        ),
                        html.Div(
                            dcc.Loading(
                                id="loading-vol",
                                type="circle",
                                children=[dcc.Graph(
                                    id="vol-graph",
                                    config={"displayModeBar": False, "responsive": True},
                                    style={"width": "100%", "height": "100%"},
                                )],
                            ),
                            style={"flex": 1, "minHeight": 0},
                        ),
                    ],
                    style={**CARD_STYLE, "gridArea": "vol"},
                ),
            ],
            style={
                "display": "grid",
                "gridTemplateAreas": """
                    "history   forecast"
                    "ma        vol"
                """,
                "gridAutoRows": "minmax(0, 1fr)",   # ensure each row is at least 0 and then equal fraction
                "gridGap": "1rem",
                "padding": "0 2rem 2rem",
                # remove any fixed height so footer stays pinned
            },
        ),

        # DOWNLOAD CONTROLS
        html.Div(
            [
                html.Button("📥 Download CSV", id="btn-download", n_clicks=0,
                            style={"backgroundColor": "#007bff", "color": "#fff", "border": "none",
                                   "padding": "0.5rem 1rem", "borderRadius": "4px", "cursor": "pointer"}),
                html.Button("📝 Generate PDF", id="btn-report", n_clicks=0,
                            style={"backgroundColor": "#28a745", "color": "#fff", "border": "none",
                                   "padding": "0.5rem 1rem", "borderRadius": "4px", "cursor": "pointer",
                                   "marginLeft": "0.5rem"}),
                dcc.Download(id="download-data"),
                dcc.Download(id="download-report"),
            ],
            style={"display": "flex", "alignItems": "center", "padding": "1rem 2rem",
                   "backgroundColor": "rgba(0,0,0,0.4)"},
        ),

        # invisible div to trigger clientside resize
        html.Div(id="resize-trigger", style={"display": "none"}),

        # INTERVAL
        dcc.Interval(id="refresh-int", interval=REFRESH_MS, n_intervals=0),

        # FOOTER
        html.Footer(
            [
                html.Span("© 2025 Crypto-Lab", style={"color": "#ccc"}), html.Span(" • "),
                DashIconify(icon="akar-icons:github-fill", width=16, style={"color": "#ccc"}),
                html.A("Source",
                       href="https://github.com/MrMoneyDeveloper/crypto_lab",
                       target="_blank",
                       style={"color": "#ccc", "marginLeft": "0.25rem", "textDecoration": "none"}),
            ],
            style={"textAlign": "center", "padding": "0.75rem 2rem",
                   "backgroundColor": "rgba(0,0,0,0.7)", "borderTop": "1px solid rgba(255,255,255,0.2)",
                   "backdropFilter": "blur(4px)", "fontSize": "0.85rem"},
        ),
    ],
    style={"minHeight": "100vh",
           "backgroundImage": "url('/assets/background.gif')",
           "backgroundSize": "cover", "backgroundPosition": "center",
           "backgroundAttachment": "fixed", "fontFamily": "Arial, sans-serif"},
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

# ───────────────────────── callbacks ──────────────────────────────────────
@app.callback(
    Output("history-graph","figure"),
    Output("forecast-graph","figure"),
    Output("ma-graph","figure"),
    Output("vol-graph","figure"),
    Output("alerts-store","data"),
    Input("coin-dropdown","value"),
    Input("refresh-int","n_intervals"),
    State("history-graph","figure"),
    State("forecast-graph","figure"),
    State("alerts-store","data"),
)
def update_graphs(coin, tick, prev_h, prev_f, alerts):
    logger.info(f"update_graphs fired for {coin!r}, tick={tick}")
    alerts = alerts or []
    try:
        hist, fc, _ = fetch_data(coin)
        logger.info(f"Fetched {len(hist)} history rows, {len(fc)} forecast rows")

        base_layout = dict(
            template="plotly_dark",
            margin=dict(l=50, r=20, t=50, b=50),
            xaxis=dict(title="Time", showgrid=True, automargin=True),
            yaxis=dict(title="Price (USD)", showgrid=True, automargin=True),
        )

        hist_fig = dict(
            data=[dict(x=hist.ts, y=hist.price, mode="lines", line=dict(width=2))],
            layout={**base_layout, "title": f"{coin.capitalize()} – last 12 h"},
        )
        fc_fig = dict(
            data=[dict(x=fc.ts, y=fc.price, mode="lines", line=dict(dash="dash", width=2))],
            layout={**base_layout, "title": f"{coin.capitalize()} – next 24 h forecast"},
        )
        ma_fig = dict(
            data=[dict(x=hist.ts, y=hist.price.rolling(3).mean(), mode="lines", line=dict(width=2))],
            layout={**base_layout, "title": "3-Point Rolling Moving Average"},
        )
        vol_fig = dict(
            data=[dict(
                x=hist.ts,
                y=hist.price.pct_change().rolling(3).std().mul((365*24)**0.5),
                mode="lines", line=dict(width=2)
            )],
            layout={**base_layout, "title": "Annualized Volatility (3-pt)"},
        )

        # example alert:
        if coin == "bitcoin":
            last = hist.price.iloc[-1]
            if last > 60000 and not any(a["id"]=="btc-alert" for a in alerts):
                alerts.append({
                    "id":"btc-alert","header":"Price Alert",
                    "message":f"Bitcoin crossed $60k: ${last:.2f}",
                    "status":"warning","duration":4000
                })

        return hist_fig, fc_fig, ma_fig, vol_fig, alerts

    except Exception:
        logger.exception("Error in update_graphs")
        return (
            prev_h or no_update,
            prev_f or no_update,
            no_update,
            no_update,
            alerts
        )

@app.callback(
    Output("toast-container","children"),
    Input("alerts-store","data"),
)
def render_toasts(alerts):
    return [
        dbc.Toast(
            a["message"],
            id=a["id"],
            header=a["header"],
            icon=a["status"],
            duration=a["duration"],
            is_open=True,
            dismissable=True,
            style={"position":"fixed","top":10,"right":10,"width":350},
        ) for a in (alerts or [])
    ]

@app.callback(  
    Output("download-data","data"),
    Input("btn-download","n_clicks"),
    State("coin-dropdown","value"),
    prevent_initial_call=True,
)
def download_csv(n, coin):
    try:
        df, _, _ = fetch_data(coin)
        return dcc.send_data_frame(df.to_csv, filename=f"{coin}_history.csv")
    except:
        logger.exception("Error generating CSV")
        return no_update

@app.callback(
    Output("download-report","data"),
    Input("btn-report","n_clicks"),
    State("coin-dropdown","value"),
    prevent_initial_call=True,
)
def download_pdf(n, coin):
    try:
        pdf_path = generate_report(coin)
        return dcc.send_file(pdf_path)
    except:
        logger.exception("Error generating PDF")
        return no_update

# ───────────────────────── clientside resize trigger ───────────────────────
app.clientside_callback(
    """
    function(n) {
        ['history-graph','forecast-graph','ma-graph','vol-graph'].forEach(function(id){
            var gd = document.getElementById(id);
            if(gd && window.Plotly) {
                window.Plotly.Plots.resize(gd);
            }
        });
        return '';
    }
    """,
    Output("resize-trigger", "children"),
    Input("refresh-int", "n_intervals"),
)

if __name__ == "__main__":
    app.run(port=8050)