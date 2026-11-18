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

    col1, col2, col3 = st.columns(3)
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

    def wma(series, period):
        weights = np.arange(1, period + 1)
        return series.rolling(period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

    @st.cache_data(ttl=1800)
    def compute_jdk_rrg(tf):
        tickers = [BENCHMARK] + list(SECTORS.values())
        data = yf.download(tickers, period="2y", interval="1d", progress=False)
        if data.empty:
            return {}, {"Improving": [], "Leading": [], "Weakening": [], "Lagging": []}, pd.DataFrame(), "N/A"
        
        raw = data["Close"] if "Close" in data else data
        if isinstance(raw, pd.Series):
            raw = raw.to_frame()
        raw = raw.ffill().dropna(subset=[BENCHMARK])
        last_date = raw.index[-1].strftime("%d %b %Y")

        len_ratio = 60 if tf == "Weekly" else 14
        len_mom = 25 if tf == "Weekly" else 7
        norm_win = 200 if tf == "Weekly" else 60

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
            if len(df_sec) < 3:
                continue

            step = 5 if tf == "Weekly" else 1
            tail_df = df_sec.iloc[::step].tail(tail_length)
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

    rrg_data, quad_lists, table_df, last_date = compute_jdk_rrg(timeframe)
    st.caption(f"Benchmark: **Nifty 50** | Latest Data: **{last_date}**")

    active_sectors = [s for s in (selected_sectors if selected_sectors else list(rrg_data.keys())) if s in rrg_data]

    if not active_sectors:
        st.warning("Yahoo Finance rate-limited or returned no sector data right now. Click the menu (top-right) -> Clear cache and rerun in 10 seconds.")
    else:
        all_x = pd.concat([rrg_data[s]["RS_Ratio"] for s in active_sectors])
        all_y = pd.concat([rrg_data[s]["RS_Momentum"] for s in active_sectors])
        bound_x = max(abs(all_x.max() - 100), abs(100 - all_x.min()), 3) * 1.15
        bound_y = max(abs(all_y.max() - 100), abs(100 - all_y.min()), 3) * 1.15

        fig = go.Figure()

        fig.add_shape(type="rect", x0=100-bound_x, y0=100, x1=100, y1=100+bound_y, fillcolor="rgba(219, 234, 254, 0.55)", line_width=0, layer="below")
        fig.add_shape(type="rect", x0=100, y0=100, x1=100+bound_x, y1=100+bound_y, fillcolor="rgba(220, 252, 231, 0.55)", line_width=0, layer="below")
        fig.add_shape(type="rect", x0=100-bound_x, y0=100-bound_y, x1=100, y1=100, fillcolor="rgba(254, 226, 226, 0.55)", line_width=0, layer="below")
        fig.add_shape(type="rect", x0=100, y0=100-bound_y, x1=100+bound_x, y1=100, fillcolor="rgba(254, 249, 195, 0.55)", line_width=0, layer="below")

        fig.add_annotation(x=100-bound_x*0.92, y=100+bound_y*0.93, text="<b>Improving</b>", showarrow=False, font=dict(color="#2563EB", size=12))
        fig.add_annotation(x=100+bound_x*0.92, y=100+bound_y*0.93, text="<b>Leading</b>", showarrow=False, font=dict(color="#16A34A", size=12))
        fig.add_annotation(x=100-bound_x*0.92, y=100-bound_y*0.93, text="<b>Lagging</b>", showarrow=False, font=dict(color="#DC2626", size=12))
        fig.add_annotation(x=100+bound_x*0.92, y=100-bound_y*0.93, text="<b>Weakening</b>", showarrow=False, font=dict(color="#CA8A04", size=12))

        for name in active_sectors:
            tail = rrg_data[name]
            sizes = [5] * (len(tail) - 1) + [12]
            fig.add_trace(go.Scatter(
                x=tail["RS_Ratio"],
                y=tail["RS_Momentum"],
                mode="lines+markers+text",
                line_shape="spline",
                line=dict(width=2),
                name=name,
                text=[""] * (len(tail) - 1) + [name],
                textposition="middle right",
                textfont=dict(size=10, color="#1F2937"),
                marker=dict(size=sizes, line=dict(width=1, color="white"))
            ))

        fig.add_hline(y=100, line_width=1.5, line_color="#9CA3AF")
        fig.add_vline(x=100, line_width=1.5, line_color="#9CA3AF")
        fig.update_layout(
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(color="#111827"),
            xaxis_title="Trend (RS-Ratio)",
            yaxis_title="Momentum (RS-Momentum)",
            xaxis=dict(range=[100 - bound_x, 100 + bound_x], gridcolor="#E5E7EB", zeroline=False),
            yaxis=dict(range=[100 - bound_y, 100 + bound_y], gridcolor="#E5E7EB", zeroline=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            height=650,
            margin=dict(l=40, r=40, t=60, b=40)
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

with tab2:
    st.subheader("Fortnightly FPI Sectoral Inflows & Outflows (NSDL)")
    st.markdown(
        "Auto-loads `nsdl_fpi_latest.html` from your repository, or upload a newer report from "
        "[NSDL FPI Monitor](https://www.fpi.nsdl.co.in/web/Reports/Latest.aspx):"
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
        default_idx = inr_cols.index(direct_net_eq[0]) if direct_net_eq else 0

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
