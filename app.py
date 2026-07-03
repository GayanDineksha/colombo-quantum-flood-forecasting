import streamlit as st
from views import auth, command_center, telemetry, dispatch_logs

st.set_page_config(
    page_title="Flood Early Warning — Command Center",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Initialize auth state
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

#Not logged in: show login screen, no sidebar
if not st.session_state["authenticated"]:
    st.markdown(
        "<style>[data-testid='stSidebar'] {display: none;}</style>",
        unsafe_allow_html=True,
    )
    auth.show()

#Logged in  show sidebar navigation, selected page
else:
    with st.sidebar:
        st.markdown("### 🌊 Flood EWS")
        st.caption(f"Signed in as: {st.session_state.get('user_email', 'Unknown')}")
        st.divider()

        page = st.radio(
            "Navigate",
            ["Command Center", "Telemetry Analytics", "Dispatch Logs"],
            label_visibility="collapsed",
        )

        st.divider()
        if st.button("Log Out", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()

    if page == "Command Center":
        command_center.show()
    elif page == "Telemetry Analytics":
        telemetry.show()
    elif page == "Dispatch Logs":
        dispatch_logs.show()