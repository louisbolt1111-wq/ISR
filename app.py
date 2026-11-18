import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os

st.set_page_config(page_title="NSE + NSDL Sector Rotation", layout="wide")
st.title("Indian Market Sector Rotation: NSE Price + NSDL FPI Flow")

tab1, tab2, tab3 = st.tabs([
    "1. NSE Price Rotation (RRG)",
    "2. NSDL FPI Sectoral Flow",
    "3. Stock-Level Sector Drill-Down"
])

def wma(series, period):
    weights = np.arange(1, period + 1)
    return series.rolling(period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

# ==========================================
# TAB 1: NSE PRICE ROTATION (RRG)
# ==========================================
with tab1:
    SECTORS = {
        "BANKNIFTY": "^NSEBANK",
        "IT": "^CNXIT",
        "AUTO": "^CNXAUTO",
        "PHARMA": "^CNXPHARMA",
        "FMCG": "^CNXFMCG",
        "METAL": "^CNXMETAL",
        "REALTY": "^CNXREALTY",
        "ENERGY": "^CNXENERGY",
        "PSU BANK": "^CNXPSUBANK",
        "INFRA": "^CNXINFRA",
        "MEDIA": "^CNXMEDIA",
        "COMMODITIES": "^CNXCMDT",
        "CONSUMPTION": "^CNXCONSUM"
    }
    BENCHMARK = "^NSEI"

    col1, col2, col3 = st.columns([1.2, 1.2, 2])
    with col1:
        timeframe = st.radio("Timeframe", ["Weekly", "Daily"], horizontal=True)
    with col2:
        tail_length = st.slider("Tail Length (Points)", min_value=3, max_value=15, value=8)
    with col3:
        selected_sectors = st.multiselect(
            "Filter Sectors (Leave empty for All)",
            options=list(SECTORS.keys()),
            default=[]
        )

    @st.cache_data(ttl=1800)
    def compute_jdk_rrg(tf, t_len):
        tickers = [BENCHMARK] + list(SECTORS.values())
        raw = yf.download(tickers, period="2y", interval="1d", progress=False)["Close"]
        raw = raw.ffill().dropna(subset=[BENCHMARK])
        last_date = raw.index[-1].strftime("%d %b %Y")

        len_ratio = 60 if tf == "Weekly" else 14
        len_mom = 25 if tf == "Weekly" else 7
        norm_win = 250 if tf == "Weekly" else 60

        results = {}
        quad_lists = {"Improving": [], "Leading": [], "Weakening": [], "Lagging": []}
        table_rows = []

        for name, ticker in SECTORS.items():
            if ticker not in raw.columns or raw[ticker].dropna().empty:
                continue

            rs = (raw[ticker] / raw[BENCHMARK]) * 100
            rs_wma = wma(rs, len_ratio)
            rs_ratio = 100 + ((rs_wma - rs_wma.rolling(norm_win).mean()) / rs_wma.rolling(norm_win).std()) * 2

            roc = (rs_ratio / rs_ratio.shift(1) - 1) * 100
            mom_wma = wma(roc, len_mom)
            rs_momentum = 100 + ((mom_wma - mom_wma.rolling(norm_win).mean()) / mom_wma.rolling(norm_win).std()) * 2

            df_sec = pd.DataFrame({"RS_Ratio": rs_ratio, "RS_Momentum": rs_momentum}).dropna()
            if len(df_sec) < t_len:
                continue

            step = 5 if tf == "Weekly" else 1
            tail_df = df_sec.iloc[::step].tail(t_len)
            if tail_df.index[-1] != df_sec.index[-1]:
                tail_df = pd.concat([tail_df.iloc[1:], df_sec.iloc[[-1]]])

            results[name] = tail_df

            r = round(float(tail_df["RS_Ratio"].iloc[-1]), 2)
            m = round(float(tail_df["RS_Momentum"].iloc[-1]), 2)

            if r >= 100 and m >= 100:
                q = "Leading"
            elif r < 100 and m >= 100:
                q = "Improving"
            elif r >= 100 and m < 100:
                q = "Weakening"
            else:
                q = "Lagging"

            quad_lists[q].append(name)
            table_rows.append({"Sector": name, "Quadrant": q, "Trend (RS-Ratio)": r, "Momentum (RS-Mom)": m})

        return results, quad_lists, pd.DataFrame(table_rows), last_date

    rrg_data, quad_lists, table_df, last_date = compute_jdk_rrg(timeframe, tail_length)
    st.caption(f"Benchmark: **Nifty 50** | Latest Data: **{last_date}**")

    active_sectors = selected_sectors if selected_sectors else list(rrg_data.keys())

    if active_sectors:
        all_x = pd.concat([rrg_data[s]["RS_Ratio"] for s in active_sectors if s in rrg_data])
        all_y = pd.concat([rrg_data[s]["RS_Momentum"] for s in active_sectors if s in rrg_data])
        bound_x = max(abs(all_x.max() - 100), abs(100 - all_x.min()), 3) * 1.18
        bound_y = max(abs(all_y.max() - 100), abs(100 - all_y.min()), 3) * 1.18

        fig = go.Figure()

        fig.add_shape(type="rect", x0=100-bound_x, y0=100, x1=100, y1=100+bound_y, fillcolor="rgba(219, 234, 254, 0.55)", line_width=0, layer="below")
        fig.add_shape(type="rect", x0=100, y0=100, x1=100+bound_x, y1=100+bound_y, fillcolor="rgba(220, 252, 231, 0.55)", line_width=0, layer="below")
        fig.add_shape(type="rect", x0=100-bound_x, y0=100-bound_y, x1=100, y1=100, fillcolor="rgba(254, 226, 226, 0.55)", line_width=0, layer="below")
        fig.add_shape(type="rect", x0=100, y0=100-bound_y, x1=100+bound_x, y1=100, fillcolor="rgba(254, 249, 195, 0.55)", line_width=0, layer="below")

        fig.add_annotation(x=100-bound_x*0.86, y=100+bound_y*0.92, text="<b>Improving</b>", showarrow=False, font=dict(color="#2563EB", size=13))
        fig.add_annotation(x=100+bound_x*0.86, y=100+bound_y*0.92, text="<b>Leading</b>", showarrow=False, font=dict(color="#16A34A", size=13))
        fig.add_annotation(x=100-bound_x*0.86, y=100-bound_y*0.92, text="<b>Lagging</b>", showarrow=False, font=dict(color="#DC2626", size=13))
        fig.add_annotation(x=100+bound_x*0.86, y=100-bound_y*0.92, text="<b>Weakening</b>", showarrow=False, font=dict(color="#CA8A04", size=13))

        for name in active_sectors:
            if name not in rrg_data:
                continue
            tail = rrg_data[name]
            sizes = [5] * (len(tail) - 1) + [12]
            fig.add_trace(go.Scatter(
                x=tail["RS_Ratio"],
                y=tail["RS_Momentum"],
                mode="lines+markers+text",
                line_shape="spline",
                line=dict(width=2.2),
                name=name,
                text=[""] * (len(tail) - 1) + [name],
                textposition="middle right",
                textfont=dict(size=11, color="#111827"),
                marker=dict(size=sizes, line=dict(width=1, color="white"))
            ))

        fig.add_hline(y=100, line_width=1.5, line_color="#6B7280")
        fig.add_vline(x=100, line_width=1.5, line_color="#6B7280")
        fig.update_layout(
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(color="#111827"),
            xaxis=dict(
                title=dict(text="Trend (RS-Ratio)", font=dict(color="#111827", size=13)),
                tickfont=dict(color="#111827", size=11),
                range=[100 - bound_x, 100 + bound_x],
                gridcolor="#E5E7EB",
                zeroline=False
            ),
            yaxis=dict(
                title=dict(text="Momentum (RS-Momentum)", font=dict(color="#111827", size=13)),
                tickfont=dict(color="#111827", size=11),
                range=[100 - bound_y, 100 + bound_y],
                gridcolor="#E5E7EB",
                zeroline=False
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
                font=dict(color="#111827", size=11),
                bgcolor="rgba(255,255,255,0.9)"
            ),
            height=660,
            margin=dict(l=50, r=50, t=70, b=50)
        )

        st.plotly_chart(fig, use_container_width=True)

        q1, q2, q3, q4 = st.columns(4)
        with q1:
            st.info(f"**Improving ({len(quad_lists['Improving'])})**\n\n" + ("\n".join([f"• {s}" for s in quad_lists["Improving"]]) or "No symbols"))
        with q2:
            st.success(f"**Leading ({len(quad_lists['Leading'])})**\n\n" + ("\n".join([f"• {s}" for s in quad_lists["Leading"]]) or "No symbols"))
        with q3:
            st.warning(f"**Weakening ({len(quad_lists['Weakening'])})**\n\n" + ("\n".join([f"• {s}" for s in quad_lists["Weakening"]]) or "No symbols"))
        with q4:
            st.error(f"**Lagging ({len(quad_lists['Lagging'])})**\n\n" + ("\n".join([f"• {s}" for s in quad_lists["Lagging"]]) or "No symbols"))

        with st.expander("View Full Numerical Table"):
            st.dataframe(table_df.sort_values(by=["Trend (RS-Ratio)", "Momentum (RS-Mom)"], ascending=False), use_container_width=True, hide_index=True)

# ==========================================
# TAB 2: NSDL FPI SECTORAL FLOW
# ==========================================
with tab2:
    st.subheader("Fortnightly FPI Sectoral Inflows & Outflows (NSDL)")
    st.markdown(
        "Auto-loads `nsdl_fpi_latest.html` from your repository, or upload a newer report from "
        "[NSDL FPI Monitor](https://www.fpi.nsdl.co.in/web/Reports/FPI_Fortnightly_Selection.aspx):"
    )

    uploaded = st.file_uploader(
        "Upload NSDL Fortnightly Sector Report (.html, .htm, .xls, .xlsx, .csv)",
        type=["html", "htm", "xls", "xlsx", "csv"]
    )

    fpi_df = None
    if uploaded is not None:
        try:
            if uploaded.name.endswith((".html", ".htm")):
                fpi_df = max(pd.read_html(uploaded), key=len)
            elif uploaded.name.endswith(".csv"):
                fpi_df = pd.read_csv(uploaded)
            else:
                fpi_df = pd.read_excel(uploaded)
        except Exception as e:
            st.error(f"Could not read file: {e}")
    elif os.path.exists("nsdl_fpi_latest.html"):
        fpi_df = max(pd.read_html("nsdl_fpi_latest.html"), key=len)

    if fpi_df is not None:
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

        sec_col = [c for c in fpi_df.columns if "sector" in c.lower()][0]
        inr_cols = [c for c in fpi_df.columns if "inr cr" in c.lower()]
        display_cols = [sec_col] + inr_cols if inr_cols else list(fpi_df.columns)
        clean_df = fpi_df[display_cols].copy()
        clean_df = clean_df[~clean_df[sec_col].astype(str).str.lower().str.contains("total|grand|nan")]

        direct_net_eq = [
            c for c in inr_cols
            if "net" in c.lower() and c.lower().endswith("| equity") and "mutual" not in c.lower()
        ]
        default_idx = inr_cols.index(direct_net_eq[-1]) if direct_net_eq else 0

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
                textposition="outside",
                textfont=dict(color="#111827", size=11)
            ))
            fig_fpi.update_layout(
                title=dict(text=f"NSDL FPI Sectoral Flow — {val_col}", font=dict(color="#111827", size=15)),
                xaxis=dict(title="Net Flow (₹ Crore)", tickfont=dict(color="#111827"), title_font=dict(color="#111827"), gridcolor="#E5E7EB"),
                yaxis=dict(title="", tickfont=dict(color="#111827", size=11)),
                height=max(600, len(chart_df) * 28),
                plot_bgcolor="white",
                paper_bgcolor="white",
                margin=dict(l=20, r=70, t=55, b=40)
            )
            st.plotly_chart(fig_fpi, use_container_width=True)

        with st.expander("View Cleaned NSDL Table (₹ Crore)", expanded=False):
            st.dataframe(clean_df, use_container_width=True, hide_index=True)

# ==========================================
# TAB 3: STOCK-LEVEL SECTOR DRILL-DOWN
# ==========================================
with tab3:
    st.subheader("Stock-Level Institutional Accumulation Drill-Down")
    st.markdown(
        "Pick an NSDL sector below to inspect its top NSE stocks on a **Stock RRG vs. Nifty 50**, "
        "**Volume Surge Ratio** (institutional footprint), and direct links to **FII Shareholding %**."
    )

    SECTOR_STOCKS = {
        "Telecommunication": {
            "Bharti Airtel": "BHARTIARTL.NS",
            "Indus Towers": "INDUSTOWER.NS",
            "Vodafone Idea": "IDEA.NS",
            "Tata Communications": "TATACOMM.NS",
            "Tejas Networks": "TEJASNET.NS",
            "HFCL": "HFCL.NS"
        },
        "Information Technology": {
            "TCS": "TCS.NS",
            "Infosys": "INFY.NS",
            "HCL Tech": "HCLTECH.NS",
            "Wipro": "WIPRO.NS",
            "Tech Mahindra": "TECHM.NS",
            "LTIMindtree": "LTIM.NS",
            "Persistent Systems": "PERSISTENT.NS",
            "Coforge": "COFORGE.NS"
        },
        "Financial Services": {
            "HDFC Bank": "HDFCBANK.NS",
            "ICICI Bank": "ICICIBANK.NS",
            "SBI": "SBIN.NS",
            "Axis Bank": "AXISBANK.NS",
            "Kotak Bank": "KOTAKBANK.NS",
            "Bajaj Finance": "BAJFINANCE.NS",
            "Jio Financial": "JIOFIN.NS",
            "Bank of Baroda": "BANKBARODA.NS"
        },
        "Healthcare": {
            "Sun Pharma": "SUNPHARMA.NS",
            "Cipla": "CIPLA.NS",
            "Dr Reddys": "DRREDDY.NS",
            "Apollo Hospitals": "APOLLOHOSP.NS",
            "Divis Labs": "DIVISLAB.NS",
            "Lupin": "LUPIN.NS",
            "Max Healthcare": "MAXHEALTH.NS"
        },
        "Automobile and Auto Components": {
            "M&M": "M&M.NS",
            "Maruti Suzuki": "MARUTI.NS",
            "Tata Motors": "TATAMOTORS.NS",
            "Bajaj Auto": "BAJAJ-AUTO.NS",
            "Eicher Motors": "EICHERMOT.NS",
            "TVS Motor": "TVSMOTOR.NS",
            "Motherson": "MOTHERSON.NS"
        },
        "Capital Goods": {
            "L&T": "LT.NS",
            "Siemens": "SIEMENS.NS",
            "ABB India": "ABB.NS",
            "HAL": "HAL.NS",
            "BEL": "BEL.NS",
            "Cummins India": "CUMMINSIND.NS",
            "Polycab": "POLYCAB.NS"
        },
        "Oil, Gas & Consumable Fuels": {
            "Reliance": "RELIANCE.NS",
            "ONGC": "ONGC.NS",
            "NTPC": "NTPC.NS",
            "Power Grid": "POWERGRID.NS",
            "Coal India": "COALINDIA.NS",
            "IOC": "IOC.NS",
            "GAIL": "GAIL.NS"
        },
        "Fast Moving Consumer Goods": {
            "ITC": "ITC.NS",
            "HUL": "HINDUNILVR.NS",
            "Nestle India": "NESTLEIND.NS",
            "Varun Beverages": "VBL.NS",
            "Trent": "TRENT.NS",
            "Britannia": "BRITANNIA.NS",
            "Godrej Consumer": "GODREJCP.NS"
        },
        "Metals & Mining": {
            "Tata Steel": "TATASTEEL.NS",
            "JSW Steel": "JSWSTEEL.NS",
            "Hindalco": "HINDALCO.NS",
            "Vedanta": "VEDL.NS",
            "Jindal Steel": "JINDALSTEL.NS",
            "NMDC": "NMDC.NS"
        }
    }

    chosen_sec = st.selectbox("Select Sector to Inspect Constituent Stocks", options=list(SECTOR_STOCKS.keys()))
    stocks_map = SECTOR_STOCKS[chosen_sec]

    @st.cache_data(ttl=1800)
    def analyze_sector_stocks(stock_dict):
        tickers = ["^NSEI"] + list(stock_dict.values())
        data = yf.download(tickers, period="1y", interval="1d", progress=False)
        close = data["Close"].ffill().dropna(subset=["^NSEI"])
        vol = data["Volume"].ffill()

        rows = []
        tails = {}
        for s_name, sym in stock_dict.items():
            if sym not in close.columns or close[sym].dropna().empty:
                continue
            rs = (close[sym] / close["^NSEI"]) * 100
            rs_wma = wma(rs, 30)
            rs_ratio = 100 + ((rs_wma - rs_wma.rolling(120).mean()) / rs_wma.rolling(120).std()) * 2
            roc = (rs_ratio / rs_ratio.shift(1) - 1) * 100
            mom_wma = wma(roc, 12)
            rs_mom = 100 + ((mom_wma - mom_wma.rolling(120).mean()) / mom_wma.rolling(120).std()) * 2

            df_s = pd.DataFrame({"RS_Ratio": rs_ratio, "RS_Momentum": rs_mom}).dropna()
            if len(df_s) < 6:
                continue

            tail = df_s.iloc[::5].tail(6)
            tails[s_name] = tail

            r = round(float(tail["RS_Ratio"].iloc[-1]), 2)
            m = round(float(tail["RS_Momentum"].iloc[-1]), 2)
            quad = "Leading" if (r >= 100 and m >= 100) else "Improving" if (r < 100 and m >= 100) else "Weakening" if (r >= 100 and m < 100) else "Lagging"

            avg_vol_20 = vol[sym].iloc[-21:-1].mean()
            curr_vol = vol[sym].iloc[-1]
            vol_ratio = round(float(curr_vol / avg_vol_20), 2) if avg_vol_20 > 0 else 0.0
            ret_1m = round(float((close[sym].iloc[-1] / close[sym].iloc[-21] - 1) * 100), 2)

            nse_code = sym.replace(".NS", "")
            rows.append({
                "Stock": s_name,
                "Quadrant": quad,
                "RS-Ratio": r,
                "RS-Momentum": m,
                "1M Return (%)": ret_1m,
                "Volume Surge (vs 20D Avg)": f"{vol_ratio}x",
                "Check FII %": f"https://www.screener.in/company/{nse_code}/consolidated/#shareholding"
            })
        return tails, pd.DataFrame(rows)

    stock_tails, stock_table = analyze_sector_stocks(stocks_map)

    if not stock_table.empty:
        st.dataframe(
            stock_table.sort_values(by=["RS-Ratio", "RS-Momentum"], ascending=False),
            column_config={
                "Check FII %": st.column_config.LinkColumn("FII Shareholding Trend", display_text="Open Screener FII %")
            },
            use_container_width=True,
            hide_index=True
        )

        fig_s = go.Figure()
        for s_name, tail in stock_tails.items():
            sizes = [5] * (len(tail) - 1) + [12]
            fig_s.add_trace(go.Scatter(
                x=tail["RS_Ratio"],
                y=tail["RS_Momentum"],
                mode="lines+markers+text",
                line_shape="spline",
                name=s_name,
                text=[""] * (len(tail) - 1) + [s_name],
                textposition="top center",
                textfont=dict(color="#111827", size=11),
                marker=dict(size=sizes)
            ))
        fig_s.add_hline(y=100, line_dash="dash", line_color="#6B7280")
        fig_s.add_vline(x=100, line_dash="dash", line_color="#6B7280")
        fig_s.update_layout(
            title=dict(text=f"{chosen_sec} — Constituent Stocks Relative Rotation vs Nifty 50", font=dict(color="#111827")),
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(color="#111827"),
            xaxis=dict(title="Trend (RS-Ratio)", tickfont=dict(color="#111827"), title_font=dict(color="#111827"), gridcolor="#E5E7EB"),
            yaxis=dict(title="Momentum (RS-Momentum)", tickfont=dict(color="#111827"), title_font=dict(color="#111827"), gridcolor="#E5E7EB"),
            legend=dict(font=dict(color="#111827")),
            height=520
        )
        st.plotly_chart(fig_s, use_container_width=True)
