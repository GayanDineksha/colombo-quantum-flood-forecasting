import requests
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta

# Colombo, Sri Lanka
COLOMBO_LAT = 6.9271
COLOMBO_LON = 79.8612


@st.cache_data(ttl=1800)  # refresh every 30 minutes
def fetch_openmeteo_data(days_back=3):
    """
    Fetches near real-time hourly weather data from Open-Meteo.
    Returns a DataFrame with columns: timestamp, temperature, humidity, rainfall.
    Raises an exception on failure — caller should handle it.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": COLOMBO_LAT,
        "longitude": COLOMBO_LON,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation",
        "past_days": days_back,
        "forecast_days": 1,
        "timezone": "Asia/Colombo",
    }
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    hourly = response.json()["hourly"]

    df = pd.DataFrame({
        "timestamp": pd.to_datetime(hourly["time"]),
        "temperature": hourly["temperature_2m"],
        "humidity": hourly["relative_humidity_2m"],
        "rainfall": hourly["precipitation"],
    })
    return df.dropna()


@st.cache_data(ttl=21600)  # refresh every 6 hours — this data updates slowly anyway
def fetch_nasa_power_data(days_back=5):
    """
    Fetches hourly historical weather data from NASA POWER.
    Note: NASA POWER has a ~3 day processing lag, so 'end date' is
    deliberately set a few days in the past, not today.
    Returns a DataFrame with columns: timestamp, temperature, humidity, rainfall.
    Raises an exception on failure — caller should handle it.
    """
    end_date = datetime.utcnow() - timedelta(days=3)
    start_date = end_date - timedelta(days=days_back)

    url = "https://power.larc.nasa.gov/api/temporal/hourly/point"
    params = {
        "parameters": "T2M,RH2M,PRECTOTCORR",
        "community": "RE",
        "longitude": COLOMBO_LON,
        "latitude": COLOMBO_LAT,
        "start": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
        "format": "JSON",
    }
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    param_data = response.json()["properties"]["parameter"]

    timestamps = list(param_data["T2M"].keys())
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(timestamps, format="%Y%m%d%H"),
        "temperature": list(param_data["T2M"].values()),
        "humidity": list(param_data["RH2M"].values()),
        "rainfall": list(param_data["PRECTOTCORR"].values()),
    })

    # NASA POWER uses -999 as a missing-value sentinel — clean it up
    df = df.replace(-999, np.nan).dropna()
    return df


def _simulate_fallback(hours=72, seed_offset=0):
    """Fallback simulated data — used only if a live API call fails."""
    now = datetime.now()
    timestamps = [now - timedelta(hours=i) for i in range(hours)][::-1]
    rng = np.random.default_rng(seed_offset)

    rain = np.abs(np.sin(np.linspace(0, 6, hours)) * 14 + rng.normal(0, 3, hours))
    temp = 27 + np.sin(np.linspace(0, 4, hours)) * 3 + rng.normal(0, 0.6, hours)
    humidity = 70 + np.sin(np.linspace(0, 5, hours)) * 14 + rng.normal(0, 2, hours)

    return pd.DataFrame({
        "timestamp": timestamps,
        "rainfall": np.clip(rain, 0, None),
        "temperature": temp,
        "humidity": np.clip(humidity, 30, 100),
    })


def get_live_data():
    """Returns (dataframe, is_live: bool). Falls back to simulation on failure."""
    try:
        return fetch_openmeteo_data(), True
    except Exception:
        return _simulate_fallback(seed_offset=1), False


def get_historical_data():
    """Returns (dataframe, is_live: bool). Falls back to simulation on failure."""
    try:
        return fetch_nasa_power_data(), True
    except Exception:
        return _simulate_fallback(seed_offset=2), False