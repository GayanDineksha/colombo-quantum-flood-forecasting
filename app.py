import streamlit as st
from views import auth, command_center, telemetry, dispatch_logs


def _inject_custom_css():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Space Grotesk', sans-serif;
        }

        /* Metric cards */
        [data-testid="stMetric"] {
            background: linear-gradient(145deg, #131A24, #0F141C);
            border: 1px solid #1E2A38;
            border-radius: 12px;
            padding: 16px 20px;
            box-shadow: 0 0 20px rgba(0, 207, 255, 0.05);
        }
        [data-testid="stMetricValue"] {
            color: #00CFFF;
        }

        /* Sidebar */
        [data-testid="stSidebar"] {
            background-color: #0D1219;
            border-right: 1px solid #1E2A38;
        }

        /* Buttons */
        .stButton > button {
            border-radius: 8px;
            transition: all 0.2s ease;
        }
        .stButton > button[kind="primary"] {
            box-shadow: 0 0 15px rgba(0, 207, 255, 0.25);
        }
        .stButton > button[kind="primary"]:hover {
            box-shadow: 0 0 25px rgba(0, 207, 255, 0.45);
            transform: translateY(-1px);
        }

        /* Containers with border (login card, etc.) */
        [data-testid="stContainer"] {
            border-radius: 14px;
        }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #0A0E14; }
        ::-webkit-scrollbar-thumb { background: #1E2A38; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #00CFFF44; }

        /* Divider */
        hr { border-color: #1E2A38 !important; }
        </style>
    """, unsafe_allow_html=True)


st.set_page_config(
    page_title="Flood Early Warning — Command Center",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

_inject_custom_css()

# Initialize auth state
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# Not logged in: show login screen, no sidebar
if not st.session_state["authenticated"]:
    st.markdown(
        """<style>
        [data-testid='stSidebar'] {display: none;}
        [data-testid='collapsedControl'] {display: none;}
        </style>""",
        unsafe_allow_html=True,
    )
    auth.show()

# Logged in: show sidebar navigation, selected page
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