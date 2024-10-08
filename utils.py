# utils.py
import streamlit as st

def initialize_session_state():
    if "app_selected" not in st.session_state:
        st.session_state.app_selected = None

def select_app(app_name):
    st.session_state.app_selected = app_name

def toggle_info(key):
    if key not in st.session_state:
        st.session_state[key] = False
    st.session_state[key] = not st.session_state[key]
