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

    col_ctrl1, col_ctrl2 = st.columns([2, 1])
    with col_ctrl1:
        timeframe = st.radio("Select Timeframe", ["Weekly (Last 8 Weeks)", "Daily (Last 10 Days)"], horizontal=True)
    is_weekly = "Weekly" in timeframe
    tail_length = 8 if is_weekly else 10
    interval = "1wk" if is_weekly else "1d"
    period = "2y" if is_weekly else "6mo"

    @st.cache_data(ttl=3600)
    def get_nse_rrg(interval, period):
        tickers = [BENCHMARK] + list(SECTORS.values())
        raw = yf.download(tickers, period=period, interval=interval, progress=False)["Close"].dropna()
        last_date = raw.index[-1].strftime("%d %b %Y")
        results, summary = {}, []

        for name, ticker in SECTORS.items():
            # 1. Raw Relative Strength vs Nifty 50
            rs = (raw[ticker] / raw[BENCHMARK]) * 100
            
            # 2. Smooth RS-Ratio using EMA (eliminates sawtooth zigzags)
            rs_ema1 = rs.ewm(span=10, adjust=False).mean()
            rs_ema2 = rs_ema1.ewm(span=10, adjust=False).mean()
            rs_ratio = 100 + ((rs_ema1 - rs_ema2) / rs_ema2.rolling(26).std()) * 10

            # 3. Smooth RS-Momentum (rate of change of RS-Ratio, smoothed with EMA)
            mom_raw = rs_ratio.diff(1)
            mom_ema = mom_raw.ewm(span=5, adjust=False).mean()
            rs_momentum = 100 + (mom_ema / mom_ema.rolling(26).std()) * 2

            df_sec = pd.DataFrame({"RS_Ratio": rs_ratio, "RS_Momentum": rs_momentum}).dropna()
            results[name] = df_sec

            r, m = df_sec["RS_Ratio"].iloc[-1], df_sec["RS_Momentum"].iloc[-1]
            lookback = 4 if is_weekly else 21
            ret_1m = ((raw[ticker].iloc[-1] / raw[ticker].iloc[-lookback]) - 1) * 100

            if r >= 100 and m >= 100:
                quad = "Leading"
            elif r < 100 and m >= 100:
                quad = "Improving"
            elif r < 100 and m < 100:
                quad = "Lagging"
            else:
                quad = "Weakening"

            summary.append({
                "Sector": name,
                "Quadrant": quad,
                "RS-Ratio": round(r, 2),
                "RS-Momentum": round(m, 2),
                "1M Return (%)": round(ret_1m, 2)
            })
        return results, pd.DataFrame(summary), last_date

    rrg_data, rrg_table, last_date = get_nse_rrg(interval, period)

    with col_ctrl2:
        st.caption(f"Latest NSE Candle Date: **{last_date}** (Auto-refreshes hourly)")

    # Dynamic axis bounds so all tails fit cleanly with breathing room
    all_x = pd.concat([df.tail(tail_length)["RS_Ratio"] for df in rrg_data.values()])
    all_y = pd.concat([df.tail(tail_length)["RS_Momentum"] for df in rrg_data.values()])
    pad_x = max(abs(all_x.max() - 100), abs(100 - all_x.min()), 2) * 1.2
    pad_y = max(abs(all_y.max() - 100), abs(100 - all_y.min()), 2) * 1.2

    fig = go.Figure()

    # Quadrant background shading
    fig.add_shape(type="rect", x0=100, y0=100, x1=100+pad_x, y1=100+pad_y, fillcolor="rgba(0,200,83,0.12)", line_width=0)
    fig.add_shape(type="rect", x0=100-pad_x, y0=100, x1=100, y1=100+pad_y, fillcolor="rgba(33,150,243,0.12)", line_width=0)
    fig.add_shape(type="rect", x0=100-pad_x, y0=100-pad_y, x1=100, y1=100, fillcolor="rgba(244,67,54,0.12)", line_width=0)
    fig.add_shape(type="rect", x0=100, y0=100-pad_y, x1=100+pad_x, y1=100, fillcolor="rgba(255,193,7,0.12)", line_width=0)

    # Quadrant corner labels (matching your PDF)
    fig.add_annotation(x=100+pad_x*0.85, y=100+pad_y*0.9, text="<b>LEADING</b>", showarrow=False, font=dict(color="#00C853", size=13))
    fig.add_annotation(x=100-pad_x*0.85, y=100+pad_y*0.9, text="<b>IMPROVING</b>", showarrow=False, font=dict(color="#2196F3", size=13))
    fig.add_annotation(x=100-pad_x*0.85, y=100-pad_y*0.9, text="<b>LAGGING</b>", showarrow=False, font=dict(color="#F44336", size=13))
    fig.add_annotation(x=100+pad_x*0.85, y=100-pad_y*0.9, text="<b>WEAKENING</b>", showarrow=False, font=dict(color="#FFC107", size=13))

    for name, df_sec in rrg_data.items():
        tail = df_sec.tail(tail_length)
        # Small dots for past weeks, large dot for current week
        marker_sizes = [5] * (len(tail) - 1) + [13]
        fig.add_trace(go.Scatter(
            x=tail["RS_Ratio"],
            y=tail["RS_Momentum"],
            mode="lines+markers+text",
            line_shape="spline",
            line=dict(width=2.5),
            name=name,
            text=[""] * (len(tail) - 1) + [name],
            textposition="top center",
            marker=dict(size=marker_sizes, line=dict(width=1, color="white"))
        ))

    fig.add_hline(y=100, line_dash="dash", line_color="rgba(255,255,255,0.4)")
    fig.add_vline(x=100, line_dash="dash", line_color="rgba(255,255,255,0.4)")
    fig.update_layout(
        xaxis_title="RS-Ratio (Relative Strength vs Nifty 50)",
        yaxis_title="RS-Momentum",
        xaxis=dict(range=[100 - pad_x, 100 + pad_x], zeroline=False),
        yaxis=dict(range=[100 - pad_y, 100 + pad_y], zeroline=False),
        height=680
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Sector Strength Table")
    st.dataframe(rrg_table.sort_values(by=["RS-Ratio", "RS-Momentum"], ascending=False), use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Fortnightly FPI Sectoral Inflows & Outflows (NSDL)")
    st.markdown(
        "Download the latest fortnightly report from [NSDL FPI Monitor](https://nsdl.co.in) "
        "(click **View Report**, then press `Ctrl+S` to save as HTML) and drop it below:"
    )

    uploaded = st.file_uploader(
        "Upload NSDL Fortnightly Sector Report (.html, .htm, .xls, .xlsx, .csv)",
        type=["html", "htm", "xls", "xlsx", "csv"]
    )

    fpi_df = None
    if uploaded is not None:
        try:
            if uploaded.name.endswith((".html", ".htm")):
                tables = pd.read_html(uploaded)
                fpi_df = max(tables, key=len)
            elif uploaded.name.endswith(".csv"):
                fpi_df = pd.read_csv(uploaded)
            else:
                fpi_df = pd.read_excel(uploaded)
        except Exception as e:
            st.error(f"Could not read file: {e}")

    if fpi_df is not None:
        # Detect NSDL's 4-row embedded header (where 'Sectors' is inside the first few rows)
        header_row_idx = None
        for i in range(min(6, len(fpi_df))):
            row_vals = [str(v).strip().lower() for v in fpi_df.iloc[i].values]
            if "sectors" in row_vals:
                header_row_idx = i
                break

        if header_row_idx is not None:
            new_cols = []
            for col_idx in range(len(fpi_df.columns)):
                parts = []
                for r in range(header_row_idx + 1):
                    val = str(fpi_df.iloc[r, col_idx]).strip()
                    if val and val.lower() not in ["none", "nan", ""]:
                        if not parts or parts[-1] != val:
                            parts.append(val)
                new_cols.append(" | ".join(parts) if parts else f"Col_{col_idx}")
            fpi_df.columns = new_cols
            fpi_df = fpi_df.iloc[header_row_idx + 1:].reset_index(drop=True)

        # Keep Sector column + INR Cr. columns (filter out USD Mn columns for clarity)
        sec_col = [c for c in fpi_df.columns if "sector" in c.lower()][0]
        inr_cols = [c for c in fpi_df.columns if "inr cr" in c.lower()]
        display_cols = [sec_col] + inr_cols if inr_cols else list(fpi_df.columns)
        clean_df = fpi_df[display_cols].copy()

        # Filter out Total / Grand Total rows
        clean_df = clean_df[~clean_df[sec_col].astype(str).str.lower().str.contains("total|grand|nan")]

        # Default to Net Investment Equity column if present
        net_eq_cols = [c for c in inr_cols if "net" in c.lower() and "equity" in c.lower()]
        default_idx = inr_cols.index(net_eq_cols[-1]) if net_eq_cols else 0

        if inr_cols:
            val_col = st.selectbox("Select Metric to Visualize (₹ Crore)", options=inr_cols, index=default_idx)

            chart_df = clean_df[[sec_col, val_col]].copy()
            chart_df[val_col] = (
                chart_df[val_col]
                .astype(str)
                .str.replace(",", "")
                .str.replace("(", "-", regex=False)
                .str.replace(")", "", regex=False)
            )
            chart_df[val_col] = pd.to_numeric(chart_df[val_col], errors="coerce")
            chart_df = chart_df.dropna().sort_values(by=val_col, ascending=True)

            colors = ["#EF4444" if v < 0 else "#10B981" for v in chart_df[val_col]]
            fig_fpi = go.Figure(go.Bar(
                x=chart_df[val_col],
                y=chart_df[sec_col],
                orientation="h",
                marker_color=colors,
                text=chart_df[val_col].apply(lambda x: f"{x:,.0f}"),
                textposition="outside"
            ))
            fig_fpi.update_layout(
                title=f"NSDL FPI Sectoral Flow — {val_col}",
                xaxis_title="Value (₹ Crore)",
                yaxis_title="",
                height=max(550, len(chart_df) * 26),
                plot_bgcolor="white",
                paper_bgcolor="white",
                font=dict(color="#111827"),
                margin=dict(l=20, r=60, t=50, b=40)
            )
            st.plotly_chart(fig_fpi, use_container_width=True)

        with st.expander("View Cleaned NSDL Table (₹ Crore)", expanded=False):
            st.dataframe(clean_df, use_container_width=True, hide_index=True)
width=True, hide_index=True)
