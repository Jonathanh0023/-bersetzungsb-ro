# config.py
import streamlit as st

def set_page_config():
    st.set_page_config(
        page_title="bonsAI Übersetzungsbüro",
        page_icon="https://sw01.rogsurvey.de/data/bonsai/Kara_23_19/logo_Bonsa_BONSAI_neu.png",
    )

def apply_global_css():
    heading_font_size_h1 = 30  # Schriftgröße für h1-Überschriften
    heading_font_size_h2 = 24  # Schriftgröße für h2-Überschriften
    button_font_size = 14      # Schriftgröße für Buttons

    st.markdown(
        f"""
        <style>
        h1 {{
            font-size: {heading_font_size_h1}px !important;
        }}
        h2 {{
            font-size: {heading_font_size_h2}px !important;
        }}
        div.stButton > button {{
            font-size: {button_font_size}px !important;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

# Example definition of info_texts
info_texts = {
    "welcome": "Willkommen im bonsAI Übersetzungsbüro!",
    "instructions": "Bitte folgen Sie den Anweisungen auf dem Bildschirm."
}
