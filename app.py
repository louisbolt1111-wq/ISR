import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os

st.set_page_config(page_title="NSE + NSDL Sector Rotation", layout="wide")
st.title("Indian Market Sector Rotation: NSE Price + NSDL FPI Flow")

tab1, tab2 = st.tabs(["1. NSE Price Rotation (RRG)", "2. NSDL FPI Sectoral Flow"])

with tab1:
    SECTORS = {
        "Nifty Bank": "^NSEBANK",
        "Nifty IT": "^CNXIT",
        "Nifty Auto": "^CNXAUTO",
        "Nifty Pharma": "^CNXPHARMA",
        "Nifty FMCG": "^CNXFMCG",
        "Nifty Metal": "^CNXMETAL",
        "Nifty Realty": "^CNXREALTY",
        "Nifty Energy": "^CNXENERGY",
        "Nifty PSU Bank": "^CNXPSUBANK",
        "Nifty Infra": "^CNXINFRA"
    }
    BENCHMARK = "^NSEI"

    timeframe = st.radio("Select Timeframe", ["Weekly (Last 8 Weeks)", "Daily (Last 10 Days)"], horizontal=True)
    is_weekly = "Weekly" in timeframe
    tail_length = 8 if is_weekly else 10
    interval = "1wk" if is_weekly else "1d"
    period = "2y" if is_weekly else "6mo"

    @st.cache_data(ttl=3600)
    def get_nse_rrg(interval, period):
        tickers = [BENCHMARK] + list(SECTORS.values())
        raw = yf.download(tickers, period=period, interval=interval, progress=False)["Close"].dropna()
        results, summary = {}, []
        for name, ticker in SECTORS.items():
            rs = raw[ticker] / raw[BENCHMARK]
            rs_smooth = rs.rolling(10).mean()
            rs_ratio = 100 + ((rs_smooth - rs_smooth.rolling(26).mean()) / rs_smooth.rolling(26).std()) * 2
            rs_roc = rs_ratio.pct_change(1)
            rs_momentum = 100 + ((rs_roc - rs_roc.rolling(26).mean()) / rs_roc.rolling(26).std()) * 2
            df_sec = pd.DataFrame({"RS_Ratio": rs_ratio, "RS_Momentum": rs_momentum}).dropna()
            results[name] = df_sec

            r, m = df_sec["RS_Ratio"].iloc[-1], df_sec["RS_Momentum"].iloc[-1]
            quad = "Leading" if (r >= 100 and m >= 100) else "Improving" if (r < 100 and m >= 100) else "Lagging" if (r < 100 and m < 100) else "Weakening"
            summary.append({"Sector": name, "Quadrant": quad, "RS-Ratio": round(r, 2), "RS-Momentum": round(m, 2)})
        return results, pd.DataFrame(summary)

    rrg_data, rrg_table = get_nse_rrg(interval, period)
    fig = go.Figure()

    fig.add_shape(type="rect", x0=100, y0=100, x1=106, y1=106, fillcolor="rgba(0,200,83,0.1)", line_width=0)
    fig.add_shape(type="rect", x0=94, y0=100, x1=100, y1=106, fillcolor="rgba(33,150,243,0.1)", line_width=0)
    fig.add_shape(type="rect", x0=94, y0=94, x1=100, y1=100, fillcolor="rgba(244,67,54,0.1)", line_width=0)
    fig.add_shape(type="rect", x0=100, y0=94, x1=106, y1=100, fillcolor="rgba(255,193,7,0.1)", line_width=0)

    for name, df_sec in rrg_data.items():
        tail = df_sec.tail(tail_length)
        sizes = [6] * (len(tail) - 1) + [12]
        fig.add_trace(go.Scatter(
            x=tail["RS_Ratio"], y=tail["RS_Momentum"], mode="lines+markers+text", name=name,
            text=[""]*(len(tail)-1) + [name], textposition="top center",
            marker=dict(size=sizes)
        ))
    fig.add_hline(y=100, line_dash="dash", line_color="gray")
    fig.add_vline(x=100, line_dash="dash", line_color="gray")
    fig.update_layout(xaxis_title="RS-Ratio (Price Strength vs Nifty 50)", yaxis_title="RS-Momentum", height=550)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(rrg_table.sort_values(by=["RS-Ratio", "RS-Momentum"], ascending=False), use_container_width=True)

with tab2:
    st.subheader("Fortnightly FPI Sectoral Inflows & Outflows (NSDL)")
    if os.path.exists("nsdl_fpi_latest.csv"):
        fpi_df = pd.read_csv("nsdl_fpi_latest.csv")
        st.dataframe(fpi_df, use_container_width=True)
    else:
        st.info("Waiting for first GitHub Action run to populate NSDL FPI data.")
