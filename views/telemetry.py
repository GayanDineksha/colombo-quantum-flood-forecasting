import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta


def _generate_openmeteo_series(hours=72):
    """Simulates live Open-Meteo data — hourly, last 72 hours."""
    now = datetime.now()
    timestamps = [now - timedelta(hours=i) for i in range(hours)][::-1]

    base_rain = np.abs(np.sin(np.linspace(0, 6, hours)) * 15 + np.random.normal(0, 4, hours))
    base_temp = 27 + np.sin(np.linspace(0, 4, hours)) * 3 + np.random.normal(0, 0.8, hours)
    base_humidity = 70 + np.sin(np.linspace(0, 5, hours)) * 15 + np.random.normal(0, 3, hours)

    return pd.DataFrame({
        "timestamp": timestamps,
        "rainfall": np.clip(base_rain, 0, None),
        "temperature": base_temp,
        "humidity": np.clip(base_humidity, 30, 100),
    })


def _generate_nasa_power_series(hours=72):
    """Simulates historical NASA POWER data — same window, smoother/less noisy."""
    now = datetime.now()
    timestamps = [now - timedelta(hours=i) for i in range(hours)][::-1]

    base_rain = np.abs(np.sin(np.linspace(0.3, 6.3, hours)) * 13 + np.random.normal(0, 2, hours))
    base_temp = 26.5 + np.sin(np.linspace(0.3, 4.3, hours)) * 2.5 + np.random.normal(0, 0.4, hours)
    base_humidity = 68 + np.sin(np.linspace(0.3, 5.3, hours)) * 13 + np.random.normal(0, 1.5, hours)

    return pd.DataFrame({
        "timestamp": timestamps,
        "rainfall": np.clip(base_rain, 0, None),
        "temperature": base_temp,
        "humidity": np.clip(base_humidity, 30, 100),
    })


def _minmax_scale(series):
    """Manual MinMax scaling to [0, 1] — avoids adding scikit-learn as a dependency."""
    min_val, max_val = series.min(), series.max()
    if max_val - min_val == 0:
        return series * 0
    return (series - min_val) / (max_val - min_val)


def show():
    st.title("📊 Telemetry Analytics")
    st.caption("Live Open-Meteo readings vs NASA POWER historical baseline — Colombo, Sri Lanka")

    #Controls
    c1, c2 = st.columns([2, 1])
    with c1:
        metric = st.selectbox(
            "Metric",
            ["Rainfall (mm/h)", "Temperature (°C)", "Humidity (%)"],
        )
    with c2:
        scale_mode = st.radio(
            "Data View",
            ["Raw Data", "MinMax Scaled Data"],
            horizontal=True,
        )

    metric_key = {
        "Rainfall (mm/h)": "rainfall",
        "Temperature (°C)": "temperature",
        "Humidity (%)": "humidity",
    }[metric]

    live_df = _generate_openmeteo_series()
    hist_df = _generate_nasa_power_series()

    live_y = live_df[metric_key]
    hist_y = hist_df[metric_key]

    if scale_mode == "MinMax Scaled Data":
        live_y = _minmax_scale(live_y)
        hist_y = _minmax_scale(hist_y)
        y_title = f"{metric} — scaled [0,1]"
    else:
        y_title = metric

    #Plotly chart
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=live_df["timestamp"], y=live_y,
        mode="lines", name="Open-Meteo (Live)",
        line=dict(color="#00CFFF", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=hist_df["timestamp"], y=hist_y,
        mode="lines", name="NASA POWER (Historical)",
        line=dict(color="#FF7A00", width=2, dash="dot"),
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

    #Summary stats
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
            "- **Open-Meteo** provides near real-time forecast/observation data, refreshed hourly.\n"
            "- **NASA POWER** provides validated historical meteorological data, used here as a "
            "ground-truth baseline for model training and calibration.\n"
            "- **MinMax scaling** normalizes both series to a [0, 1] range, which is the "
            "preprocessing step used before feeding data into the quantum forecasting model.\n\n"
            "*Currently showing simulated data pending live API key configuration.*"
        )
