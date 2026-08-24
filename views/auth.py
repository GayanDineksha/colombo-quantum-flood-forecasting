import streamlit as st
import time
import os
from dotenv import load_dotenv

load_dotenv()
VALID_EMAIL = os.getenv("ADMIN_EMAIL")
VALID_PASSWORD = os.getenv("ADMIN_PASSWORD")

def show():

    left, center, right = st.columns([1, 1.2, 1])

    with center:
        st.markdown("<br><br>", unsafe_allow_html=True)
        
        # Updated Title
        st.markdown(
            "<h1 style='text-align: center;'>🌊 Flood Early Warning Systems</h1>",
            unsafe_allow_html=True,
        )
        
        # Added Authorized Personnel Warning
        st.markdown(
            "<p style='text-align: center; color: #ff4b4b; font-weight: 600;'>"
            "Restricted Access: Authorized Personnel Only</p>",
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
                if not email or not password:
                    st.error("Please enter both email and password.")
                elif email == VALID_EMAIL and password == VALID_PASSWORD:
                    with st.spinner("Authenticating via Supabase..."):
                        time.sleep(1)
                    st.session_state["authenticated"] = True
                    st.session_state["user_email"] = email
                    st.rerun()
                else:
                    st.error("Invalid email or password.")
                    