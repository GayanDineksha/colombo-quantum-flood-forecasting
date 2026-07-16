import streamlit as st
import pydeck as pdk
import pandas as pd
import random

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


def calculate_localized_risks(base_risk):
    """
    Distributes a single baseline (district-level) flood risk value across
    all 8 zones using static heuristic multipliers. Mirrors the topological
    weighting approach that will be used once the real QLSTM model — which
    can only output one city-wide baseline from unified NASA POWER /
    Open-Meteo data — is connected.
    """
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


def show():
    st.title("🚨 Command Center")

    # Refresh control — regenerate data without needing a full page nav
    top_l, top_r = st.columns([4, 1])
    with top_r:
        if st.button("🔄 Refresh Live Data", use_container_width=True):
            st.rerun()

    # ---- Simulated QLSTM baseline output ----
    # This single value stands in for the real model's district-level output
    # once NASA POWER / Open-Meteo data is wired in.
    simulated_base_risk = random.uniform(20, 80)
    localized_risks = calculate_localized_risks(simulated_base_risk)

    rainfall = random.uniform(5, 60)
    status = "OPERATIONAL" if simulated_base_risk < 80 else "ALERT"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Current Flood Risk",
            f"{simulated_base_risk:.1f}%",
            delta=f"{random.uniform(-5, 5):.1f}%",
            help="Simulated district-level baseline output (stand-in for the QLSTM model).",
        )
    with col2:
        st.metric("Live Rainfall", f"{rainfall:.1f} mm/h", delta=f"{random.uniform(-3, 3):.1f} mm/h")
    with col3:
        st.metric("System Status", status)

    st.divider()

    # ---- 3D PyDeck Map ----
    st.subheader("📍 Spatial Flood Risk — Colombo")
    st.caption(
        "Zone-level risk is derived from a single baseline via topological "
        "weighting (elevation, river proximity, urban density)."
    )

    df = _generate_zone_data(localized_risks)

    # Main hexagonal risk pillars
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

    # Pulsing ground halo under critical-risk zones only
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

    # Floating zone-name + risk labels above each pillar
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

    # Legend
    lg1, lg2, lg3 = st.columns(3)
    with lg1:
        st.markdown("🟡 **LOW** — under 50%")
    with lg2:
        st.markdown("🟠 **MODERATE** — 50–75%")
    with lg3:
        st.markdown("🔴 **CRITICAL** — above 75% (pulsing halo)")

    # ---- Ranked risk table ----
    with st.expander("📊 Zone Risk Breakdown (ranked)", expanded=False):
        st.caption(f"Baseline risk: {simulated_base_risk:.1f}% × zone multiplier = localized risk")
        ranked = df[["name", "risk", "label"]].copy()
        ranked["multiplier"] = ranked["name"].map(ZONE_MULTIPLIERS)
        ranked = ranked.sort_values("risk", ascending=False).reset_index(drop=True)
        ranked.index += 1
        ranked = ranked.rename(columns={
            "name": "Zone", "risk": "Risk %", "label": "Status", "multiplier": "Weight"
        })
        st.dataframe(ranked, use_container_width=True)

    st.divider()

    # Twilio SMS Trigger
    st.subheader("📡 Emergency Alert Dispatch")
    c1, c2 = st.columns([2, 1])
    with c1:
        if simulated_base_risk > 75:
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