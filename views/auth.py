import streamlit as st
import time

def show():
    """Renders the login/auth screen (View 1)."""

    left, center, right = st.columns([1, 1.2, 1])

    with center:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            "<h1 style='text-align: center;'>🌊 Flood Early Warning</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align: center; color: gray;'>"
            "Quantum-Enhanced Command Center</p>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)

        with st.container(border=True):
            st.subheader("Secure Sign In")
            email = st.text_input("Email", placeholder="officer@disaster-mgmt.lk")
            password = st.text_input("Password", type="password", placeholder="••••••••")

            st.markdown("<br>", unsafe_allow_html=True)
            login_clicked = st.button("Sign In", use_container_width=True, type="primary")

            if login_clicked:
                if email and password:
                    with st.spinner("Authenticating via Supabase..."):
                        time.sleep(1)
                    st.session_state["authenticated"] = True
                    st.session_state["user_email"] = email
                    st.rerun()
                else:
                    st.error("Please enter both email and password.")

            st.caption("This is a simulated login for thesis demonstration purposes.")