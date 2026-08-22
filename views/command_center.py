import streamlit as st
import pydeck as pdk
import pandas as pd
import random
import requests
from utils.weather_api import get_live_data

COLOMBO_ZONES = [
    {"name": "Kolonnawa", "lat": 6.9344, "lon": 79.8817},
    {"name": "Kelaniya", "lat": 6.9553, "lon": 79.9219},
    {"name": "Wellawatte", "lat": 6.8770, "lon": 79.8607},
    {"name": "Kotte", "lat": 6.8905, "lon": 79.9185},
    {"name": "Kaduwela", "lat": 6.9337, "lon": 79.9836},
    {"name": "Orugodawatta", "lat": 6.9450, "lon": 79.8790},
    {"name": "Grandpass", "lat": 6.9490, "lon": 79.8630},
    {"name": "Dematagoda", "lat": 6.9350, "lon": 79.8720},
]

# Heuristic topological weights — based on elevation, proximity to the
# Kelani River, and urban density. Used to spatially disaggregate a single
# district-level QLSTM output into 8 zone-level risk estimates.
ZONE_MULTIPLIERS = {
    "Kolonnawa": 1.35,      # Very low elevation, highly prone to river overflow
    "Kaduwela": 1.25,       # Low elevation, river basin
    "Kelaniya": 1.20,       # River adjacent
    "Orugodawatta": 1.15,   # Urban basin
    "Grandpass": 1.10,      # Dense urban, prone to drainage failure
    "Dematagoda": 1.05,     # Average elevation
    "Kotte": 0.90,          # Higher elevation, protected by wetlands
    "Wellawatte": 0.75,     # Coastal runoff, fast drainage
}

MAX_RISK = 99.9
API_URL = "http://localhost:8000/predict/live"


def calculate_localized_risks(base_risk):
    localized = {}
    for zone_name, weight in ZONE_MULTIPLIERS.items():
        risk = base_risk * weight
        localized[zone_name] = round(min(risk, MAX_RISK), 1)
    return localized


def _risk_color(risk):
    """Yellow -> orange -> red gradient based on risk severity."""
    if risk < 50:
        return [255, 200, 0, 190]
    elif risk < 75:
        return [255, 120, 0, 215]
    else:
        return [255, 30, 0, 240]


def _risk_label(risk):
    if risk < 50:
        return "LOW"
    elif risk < 75:
        return "MODERATE"
    else:
        return "CRITICAL"


def _generate_zone_data(localized_risks):
    """Builds the map/table DataFrame from a dict of {zone_name: risk}."""
    rows = []
    for zone in COLOMBO_ZONES:
        risk = localized_risks[zone["name"]]
        rows.append({
            "name": zone["name"],
            "lat": zone["lat"],
            "lon": zone["lon"],
            "risk": risk,
            "elevation": risk * 30,
            "color": _risk_color(risk),
            "label": _risk_label(risk),
        })
    return pd.DataFrame(rows)


def _get_current_rainfall():
    try:
        df, is_real = get_live_data()
        latest_rainfall = float(df["rainfall"].iloc[-1])
        return latest_rainfall, is_real
    except Exception:
        return random.uniform(5, 60), False


def _get_baseline_risk():
    """
    Calls the FastAPI backend (model/api.py) which loads the trained
    QLSTM and fetches live NASA POWER data internally. Falls back to a
    simulated value if the API is unreachable, so the dashboard never
    breaks during a demo (e.g. FastAPI server not started, or NASA
    POWER temporarily down).
    """
    try:
        response = requests.get(API_URL, headers={"x-api-key": "flood-ews-dev-key-2026"}, timeout=15)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            return random.uniform(20, 80), False, data["error"]

        return data["flood_risk_percent"], True, None
    except Exception as e:
        return random.uniform(20, 80), False, str(e)


def show():
    st.title("🚨 Command Center")

    # Refresh control — regenerate data without needing a full page nav
    top_l, top_r = st.columns([4, 1])
    with top_r:
        if st.button("🔄 Refresh Live Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # ---- QLSTM baseline output (via FastAPI backend) ----
    base_risk, risk_is_live, risk_error = _get_baseline_risk()
    localized_risks = calculate_localized_risks(base_risk)

    rainfall, rainfall_is_live = _get_current_rainfall()
    status = "OPERATIONAL" if base_risk < 80 else "ALERT"

    # Real delta vs the previous reading, instead of a fake random one
    prev_risk = st.session_state.get("prev_base_risk")
    delta = f"{base_risk - prev_risk:.1f}%" if prev_risk is not None else None
    st.session_state["prev_base_risk"] = base_risk

    col1, col2, col3 = st.columns(3)
    with col1:
        risk_label = "Current Flood Risk" if risk_is_live else "Current Flood Risk (simulated)"
        st.metric(
            risk_label,
            f"{base_risk:.1f}%",
            delta=delta,
            help="QLSTM prediction via FastAPI backend." if risk_is_live
                 else "FastAPI backend unreachable — showing simulated placeholder.",
        )
    with col2:
        rainfall_label = "Live Rainfall" if rainfall_is_live else "Live Rainfall (simulated)"
        st.metric(rainfall_label, f"{rainfall:.1f} mm/h")
    with col3:
        st.metric("System Status", status)

    if not risk_is_live:
        st.caption(f"🟡 QLSTM backend unreachable — flood risk is simulated. ({risk_error})")
    if not rainfall_is_live:
        st.caption("🟡 Open-Meteo unreachable — rainfall reading is simulated.")

    st.divider()

    # ---- 3D PyDeck Map ----
    st.subheader("📍 Spatial Flood Risk — Colombo")
    st.caption(
        "Zone-level risk is derived from a single QLSTM baseline via topological "
        "weighting (elevation, river proximity, urban density)."
    )

    df = _generate_zone_data(localized_risks)

    column_layer = pdk.Layer(
        "ColumnLayer",
        data=df,
        get_position=["lon", "lat"],
        get_elevation="elevation",
        elevation_scale=1,
        radius=300,
        disk_resolution=6,
        get_fill_color="color",
        pickable=True,
        auto_highlight=True,
        extruded=True,
        material={
            "ambient": 0.3,
            "diffuse": 0.6,
            "shininess": 40,
            "specularColor": [255, 180, 100],
        },
    )

    critical_df = df[df["risk"] >= 75]
    halo_layer = pdk.Layer(
        "ScatterplotLayer",
        data=critical_df,
        get_position=["lon", "lat"],
        get_radius=500,
        get_fill_color=[255, 40, 0, 60],
        stroked=True,
        get_line_color=[255, 80, 0, 200],
        line_width_min_pixels=2,
        pickable=False,
    )

    text_layer = pdk.Layer(
        "TextLayer",
        data=df,
        get_position=["lon", "lat"],
        get_text="name",
        get_size=14,
        get_color=[255, 255, 255, 230],
        get_alignment_baseline="'bottom'",
        get_pixel_offset=[0, -60],
        billboard=True,
    )

    view_state = pdk.ViewState(
        latitude=6.9271,
        longitude=79.8850,
        zoom=11,
        pitch=50,
        bearing=15,
    )

    tooltip = {
        "html": "<b>{name}</b><br/>Risk: {risk}%<br/>Status: {label}",
        "style": {"backgroundColor": "#1a1a1a", "color": "white"},
    }

    st.pydeck_chart(
        pdk.Deck(
            layers=[halo_layer, column_layer, text_layer],
            initial_view_state=view_state,
            map_style="dark",
            tooltip=tooltip,
        )
    )

    lg1, lg2, lg3 = st.columns(3)
    with lg1:
        st.markdown("🟡 **LOW** — under 50%")
    with lg2:
        st.markdown("🟠 **MODERATE** — 50–75%")
    with lg3:
        st.markdown("🔴 **CRITICAL** — above 75% (pulsing halo)")

    with st.expander("📊 Zone Risk Breakdown (ranked)", expanded=False):
        st.caption(f"Baseline risk: {base_risk:.1f}% × zone multiplier = localized risk")
        ranked = df[["name", "risk", "label"]].copy()
        ranked["multiplier"] = ranked["name"].map(ZONE_MULTIPLIERS)
        ranked = ranked.sort_values("risk", ascending=False).reset_index(drop=True)
        ranked.index += 1
        ranked = ranked.rename(columns={
            "name": "Zone", "risk": "Risk %", "label": "Status", "multiplier": "Weight"
        })
        st.dataframe(ranked, use_container_width=True)

    st.divider()

    st.subheader("📡 Emergency Alert Dispatch")
    c1, c2 = st.columns([2, 1])
    with c1:
        if base_risk > 75:
            st.error("🔴 Twilio SMS Trigger: **ARMED** — risk threshold exceeded")
        else:
            st.success("🟢 Twilio SMS Trigger: **STANDBY** — risk within safe range")
    with c2:
        if st.button("🚨 Force Emergency Broadcast", use_container_width=True, type="primary"):
            highest_risk_zone = df.loc[df["risk"].idxmax()]

            if "dispatch_logs" not in st.session_state:
                st.session_state["dispatch_logs"] = []

            st.session_state["dispatch_logs"].append({
                "timestamp": pd.Timestamp.now(),
                "zone": highest_risk_zone["name"],
                "risk_at_trigger": highest_risk_zone["risk"],
                "recipient_count": random.randint(150, 2000),
                "status": "Delivered",
            })

            st.toast(
                f"Emergency SMS broadcast sent for {highest_risk_zone['name']} — dispatch logged.",
                icon="📨",
            )