import streamlit as st
import pandas as pd


def show():
    st.title("📋 Dispatch Logs")
    st.caption("History of triggered SMS alerts — simulated Twilio + Supabase log")

    logs = st.session_state.get("dispatch_logs", [])

    if not logs:
        st.info("No alerts have been dispatched yet. Trigger one from the Command Center.")
        return

    df = pd.DataFrame(logs)
    df = df.sort_values("timestamp", ascending=False).reset_index(drop=True)
    df.index += 1

    #Summary row 
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Alerts Sent", len(df))
    with c2:
        critical_count = (df["risk_at_trigger"] >= 75).sum()
        st.metric("Critical-Level Alerts", int(critical_count))
    with c3:
        st.metric("Last Alert", df.iloc[0]["timestamp"].strftime("%b %d, %H:%M"))

    st.divider()

    #Filter
    zone_filter = st.multiselect(
        "Filter by zone",
        options=sorted(df["zone"].unique()),
        default=[],
    )
    if zone_filter:
        df = df[df["zone"].isin(zone_filter)]

    #Table
    display_df = df.copy()
    display_df["timestamp"] = display_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    display_df["risk_at_trigger"] = display_df["risk_at_trigger"].round(1).astype(str) + "%"
    display_df = display_df.rename(columns={
        "timestamp": "Timestamp",
        "zone": "Zone",
        "risk_at_trigger": "Risk at Trigger",
        "recipient_count": "SMS Recipients",
        "status": "Status",
    })

    st.dataframe(display_df, use_container_width=True)

    if st.button("🗑️ Clear Log History"):
        st.session_state["dispatch_logs"] = []
        st.rerun()