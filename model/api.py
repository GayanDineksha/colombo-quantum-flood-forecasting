"""
FastAPI backend for the Quantum-Enhanced Flood Early Warning System.

Fulfills the thesis's FastAPI backend requirement (FR: automated data
ingestion + QLSTM inference via API routing). Loads the trained QLSTM,
and exposes two endpoints:

  GET  /predict/live   - auto-fetches the last 14 days from NASA POWER
                          and returns a flood risk prediction
  POST /predict        - accepts a manually supplied 14-day feature
                          window (useful for testing / offline demo)

Run with:
    uvicorn model.api:app --reload --port 8000

Then visit http://localhost:8000/docs for interactive API documentation.
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import pennylane as qml
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict


# Reproduce the exact QLSTM architecture used in training - must match
# train_qlstm.py exactly, or the saved weights won't load correctly.

HIDDEN_SIZE = 64
N_QUBITS = 4
N_QLAYERS = 2
LOOKBACK = 14
FEATURES = [
    "Rainfall_mm", "Humidity_pct", "Temperature_C",
    "Soil_Moisture", "Wind_Speed_ms", "Atmospheric_Pressure_kPa",
]

MODEL_PATH = "model/qlstm_model.pt"
ENGINEERED_DATA_PATH = "data/engineered_dataset.csv"

qdevice = qml.device("default.qubit", wires=N_QUBITS)


def _circuit(inputs, weights):
    qml.AngleEmbedding(inputs, wires=range(N_QUBITS))
    qml.BasicEntanglerLayers(weights, wires=range(N_QUBITS))
    return [qml.expval(qml.PauliZ(w)) for w in range(N_QUBITS)]


qnode = qml.QNode(_circuit, qdevice, interface="torch")
weight_shapes = {"weights": (N_QLAYERS, N_QUBITS)}


class QuantumGate(nn.Module):
    def __init__(self, concat_dim, n_qubits=N_QUBITS, hidden_size=HIDDEN_SIZE):
        super().__init__()
        self.clayer_in = nn.Linear(concat_dim, n_qubits)
        self.vqc = qml.qnn.TorchLayer(qnode, weight_shapes)
        self.clayer_out = nn.Linear(n_qubits, hidden_size)

    def forward(self, v):
        x = torch.tanh(self.clayer_in(v))
        x = self.vqc(x)
        return self.clayer_out(x)


class QLSTMCell(nn.Module):
    def __init__(self, input_size, hidden_size=HIDDEN_SIZE):
        super().__init__()
        self.hidden_size = hidden_size
        concat_dim = input_size + hidden_size
        self.forget_gate = QuantumGate(concat_dim, hidden_size=hidden_size)
        self.input_gate = QuantumGate(concat_dim, hidden_size=hidden_size)
        self.update_gate = QuantumGate(concat_dim, hidden_size=hidden_size)
        self.output_gate = QuantumGate(concat_dim, hidden_size=hidden_size)

    def forward(self, x_t, state):
        h_prev, c_prev = state
        v_t = torch.cat([x_t, h_prev], dim=-1)
        f_t = torch.sigmoid(self.forget_gate(v_t))
        i_t = torch.sigmoid(self.input_gate(v_t))
        g_t = torch.tanh(self.update_gate(v_t))
        o_t = torch.sigmoid(self.output_gate(v_t))
        c_t = f_t * c_prev + i_t * g_t
        h_t = o_t * torch.tanh(c_t)
        return h_t, c_t


class QLSTM(nn.Module):
    def __init__(self, input_size, hidden_size=HIDDEN_SIZE, dropout=0.2):
        super().__init__()
        self.hidden_size = hidden_size
        self.cell = QLSTMCell(input_size, hidden_size)
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 32), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(32, 1), nn.Sigmoid(),
        )

    def forward(self, x):
        batch_size, seq_len, _ = x.shape
        h_t = torch.zeros(batch_size, self.hidden_size)
        c_t = torch.zeros(batch_size, self.hidden_size)
        for t in range(seq_len):
            h_t, c_t = self.cell(x[:, t, :], (h_t, c_t))
        return self.fc(h_t)



# Load model + reconstruct scalers at startup (once, not per-request)
model = QLSTM(input_size=len(FEATURES))
model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu"))
model.eval()

_engineered = pd.read_csv(ENGINEERED_DATA_PATH)
SCALERS = {
    col: {"min": float(_engineered[col].min()), "max": float(_engineered[col].max())}
    for col in FEATURES
}


def scale_window(df_window: pd.DataFrame) -> np.ndarray:
    scaled = np.zeros((LOOKBACK, len(FEATURES)), dtype=np.float32)
    for j, col in enumerate(FEATURES):
        mn, mx = SCALERS[col]["min"], SCALERS[col]["max"]
        scaled[:, j] = (df_window[col].values - mn) / (mx - mn)
    return scaled


def predict_from_window(df_window: pd.DataFrame) -> float:
    X = scale_window(df_window)
    X_tensor = torch.tensor(X, dtype=torch.float32).unsqueeze(0)
    with torch.no_grad():
        pred = model(X_tensor).item()
    return round(min(pred * 100.0, 99.9), 1)



# Live data sources: Open-Meteo (real-time, primary) and NASA POWER
# (validated but ~3 day lag, automatic fallback). Supervisor-approved
# dual-source setup - Open-Meteo prioritized because real-time data
# matters more for an early-warning system than NASA POWER's ~3 day
# processing lag, per the thesis's own stated "prediction lag" problem.

COLOMBO_LAT, COLOMBO_LON = 6.9271, 79.8612


def fetch_openmeteo_features(days_back=14):
    """
    Fetches the 6 model features from Open-Meteo's hourly API, then
    resamples to daily values (rainfall summed, everything else
    averaged) to match the daily granularity the model was trained on.
    Genuinely near real-time - includes up to the current hour.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": COLOMBO_LAT,
        "longitude": COLOMBO_LON,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,"
                  "windspeed_10m,surface_pressure,soil_moisture_0_to_1cm",
        "past_days": days_back,
        "forecast_days": 1,
        "timezone": "Asia/Colombo",
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    hourly = resp.json()["hourly"]

    df = pd.DataFrame({
        "timestamp": pd.to_datetime(hourly["time"]),
        "Temperature_C": hourly["temperature_2m"],
        "Humidity_pct": hourly["relative_humidity_2m"],
        "Rainfall_mm": hourly["precipitation"],
        "Wind_Speed_ms": hourly["windspeed_10m"],
        # Open-Meteo returns pressure in hPa; NASA POWER (used for
        # training) reports in kPa - convert for consistency.
        "Atmospheric_Pressure_kPa": [p / 10.0 for p in hourly["surface_pressure"]],
        "Soil_Moisture": hourly["soil_moisture_0_to_1cm"],
    })
    df["Date"] = df["timestamp"].dt.date

    daily = df.groupby("Date").agg({
        "Temperature_C": "mean",
        "Humidity_pct": "mean",
        "Rainfall_mm": "sum",
        "Wind_Speed_ms": "mean",
        "Atmospheric_Pressure_kPa": "mean",
        "Soil_Moisture": "mean",
    }).reset_index()
    daily["Date"] = pd.to_datetime(daily["Date"])
    daily = daily.dropna().sort_values("Date").reset_index(drop=True)
    return daily.tail(LOOKBACK)


def fetch_nasa_power_features(days_back=20):
    """
    Fetches the 6 model features from NASA POWER's daily point API.
    community=AG includes soil moisture (GWETTOP). Used as an automatic
    fallback when Open-Meteo is unreachable - validated data, but has
    an inherent ~3 day processing lag.
    """
    end_date = datetime.utcnow() - timedelta(days=3)  # NASA POWER processing lag
    start_date = end_date - timedelta(days=days_back)

    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": "T2M,RH2M,PRECTOTCORR,WS10M,PS,GWETTOP",
        "community": "AG",
        "longitude": COLOMBO_LON,
        "latitude": COLOMBO_LAT,
        "start": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
        "format": "JSON",
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    p = resp.json()["properties"]["parameter"]

    dates = list(p["T2M"].keys())
    df = pd.DataFrame({
        "Date": pd.to_datetime(dates, format="%Y%m%d"),
        "Temperature_C": list(p["T2M"].values()),
        "Humidity_pct": list(p["RH2M"].values()),
        "Rainfall_mm": list(p["PRECTOTCORR"].values()),
        "Wind_Speed_ms": list(p["WS10M"].values()),
        "Atmospheric_Pressure_kPa": list(p["PS"].values()),
        "Soil_Moisture": list(p["GWETTOP"].values()),
    })
    df = df.replace(-999, np.nan).dropna().sort_values("Date").reset_index(drop=True)
    return df.tail(LOOKBACK)


def fetch_live_features_with_fallback():
    """
    Tries Open-Meteo first (real-time). Falls back to NASA POWER
    (validated, ~3 day lag) if Open-Meteo fails or returns an
    incomplete window. Returns (dataframe, source_name).
    """
    try:
        df = fetch_openmeteo_features()
        if len(df) >= LOOKBACK:
            return df, "Open-Meteo (real-time)"
    except Exception:
        pass

    df = fetch_nasa_power_features()
    return df, "NASA POWER (fallback, ~3 day lag)"



# FastAPI app

app = FastAPI(title="Flood Risk QLSTM API", version="1.0")


class ManualWindow(BaseModel):
    days: List[Dict[str, float]]  # each dict has the 6 FEATURES as keys


@app.get("/")
def root():
    return {
        "status": "ok",
        "model": "QLSTM",
        "features": FEATURES,
        "lookback_days": LOOKBACK,
    }


@app.get("/predict/live")
def predict_live():
    """
    Primary endpoint. Tries Open-Meteo (real-time) first, automatically
    falls back to NASA POWER (validated, ~3 day lag) if unavailable.
    """
    try:
        df, source = fetch_live_features_with_fallback()
    except Exception as e:
        return {"error": f"Both live sources failed: {e}"}

    if len(df) < LOOKBACK:
        return {"error": f"Only {len(df)} valid days available from {source}, need {LOOKBACK}"}

    risk = predict_from_window(df)
    return {
        "flood_risk_percent": risk,
        "data_source": source,
        "window_start": str(df["Date"].iloc[0].date()),
        "window_end": str(df["Date"].iloc[-1].date()),
    }


@app.get("/predict/live/openmeteo")
def predict_live_openmeteo():
    """Explicit Open-Meteo-only endpoint - useful for testing/comparison."""
    try:
        df = fetch_openmeteo_features()
    except Exception as e:
        return {"error": f"Open-Meteo fetch failed: {e}"}
    if len(df) < LOOKBACK:
        return {"error": f"Only {len(df)} valid days from Open-Meteo, need {LOOKBACK}"}
    risk = predict_from_window(df)
    return {
        "flood_risk_percent": risk,
        "data_source": "Open-Meteo (forced)",
        "window_start": str(df["Date"].iloc[0].date()),
        "window_end": str(df["Date"].iloc[-1].date()),
    }


@app.get("/predict/live/nasa")
def predict_live_nasa():
    """Explicit NASA POWER-only endpoint - useful for testing/comparison."""
    try:
        df = fetch_nasa_power_features()
    except Exception as e:
        return {"error": f"NASA POWER fetch failed: {e}"}
    if len(df) < LOOKBACK:
        return {"error": f"Only {len(df)} valid days from NASA POWER, need {LOOKBACK}"}
    risk = predict_from_window(df)
    return {
        "flood_risk_percent": risk,
        "data_source": "NASA POWER (forced)",
        "window_start": str(df["Date"].iloc[0].date()),
        "window_end": str(df["Date"].iloc[-1].date()),
    }


@app.post("/predict")
def predict_manual(payload: ManualWindow):
    df = pd.DataFrame(payload.days)
    if len(df) != LOOKBACK:
        return {"error": f"Expected exactly {LOOKBACK} days, got {len(df)}"}
    missing = [c for c in FEATURES if c not in df.columns]
    if missing:
        return {"error": f"Missing required feature columns: {missing}"}

    risk = predict_from_window(df)
    return {"flood_risk_percent": risk, "data_source": "manual input"}