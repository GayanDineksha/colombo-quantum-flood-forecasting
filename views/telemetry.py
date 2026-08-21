import streamlit as st
import plotly.graph_objects as go
from utils.weather_api import get_live_data, get_historical_data


def _minmax_scale(series):
    """Manual MinMax scaling to [0, 1] — avoids adding scikit-learn as a dependency."""
    min_val, max_val = series.min(), series.max()
    if max_val - min_val == 0:
        return series * 0
    return (series - min_val) / (max_val - min_val)


def show():
    st.title("📊 Telemetry Analytics")
    st.caption("Live Open-Meteo readings vs NASA POWER historical baseline — Colombo, Sri Lanka")

    with st.spinner("Fetching live weather data..."):
        live_df, live_is_real = get_live_data()
        hist_df, hist_is_real = get_historical_data()

    # ---- Data source status ----
    s1, s2 = st.columns(2)
    with s1:
        if live_is_real:
            st.success("🟢 Open-Meteo: Live data connected")
        else:
            st.warning("🟡 Open-Meteo: Unreachable — showing simulated fallback data")
    with s2:
        if hist_is_real:
            st.success("🟢 NASA POWER: Live data connected")
        else:
            st.warning("🟡 NASA POWER: Unreachable — showing simulated fallback data")

    if hist_is_real:
        st.caption("ℹ️ NASA POWER data has an inherent ~3 day processing lag — this is expected, not an error.")

    st.divider()

    # ---- Controls ----
    c1, c2 = st.columns([2, 1])
    with c1:
        metric = st.selectbox("Metric", ["Rainfall (mm/h)", "Temperature (°C)", "Humidity (%)"])
    with c2:
        scale_mode = st.radio("Data View", ["Raw Data", "MinMax Scaled Data"], horizontal=True)

    metric_key = {
        "Rainfall (mm/h)": "rainfall",
        "Temperature (°C)": "temperature",
        "Humidity (%)": "humidity",
    }[metric]

    live_y = live_df[metric_key]
    hist_y = hist_df[metric_key]

    if scale_mode == "MinMax Scaled Data":
        live_y = _minmax_scale(live_y)
        hist_y = _minmax_scale(hist_y)
        y_title = f"{metric} — scaled [0,1]"
    else:
        y_title = metric

    # ---- Plotly chart ----
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=live_df["timestamp"], y=live_y, mode="lines",
        name="Open-Meteo (Live)", line=dict(color="#00CFFF", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=hist_df["timestamp"], y=hist_y, mode="lines",
        name="NASA POWER (Historical)", line=dict(color="#FF7A00", width=2, dash="dot"),
    ))
    fig.update_layout(
        template="plotly_dark",
        height=500,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_title="Time",
        yaxis_title=y_title,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ---- Summary stats ----
    st.subheader("📈 Summary Statistics")
    s1, s2 = st.columns(2)
    with s1:
        st.markdown("**Open-Meteo (Live)**")
        st.write(live_df[metric_key].describe().round(2))
    with s2:
        st.markdown("**NASA POWER (Historical)**")
        st.write(hist_df[metric_key].describe().round(2))

    with st.expander("ℹ️ About this comparison"):
        st.markdown(
            "- **Open-Meteo** provides near real-time forecast/observation data, refreshed every 30 minutes.\n"
            "- **NASA POWER** provides validated historical meteorological data (MERRA-2 reanalysis), "
            "with an inherent ~3 day processing lag, refreshed every 6 hours.\n"
            "- **MinMax scaling** normalizes both series to a [0, 1] range — the preprocessing step "
            "used before feeding data into the quantum forecasting model.\n\n"
            "*Data source status is shown above — simulated fallback activates automatically if either API is unreachable.*"
        )