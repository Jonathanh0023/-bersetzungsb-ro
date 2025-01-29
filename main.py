import streamlit as st
from config import set_page_config, apply_global_css
from utils import initialize_session_state
from selection_page import selection_page
from allgemeine_app import allgemeine_app
from key_account_app import key_account_app
from matching_app import matching_app
from powerpoint_app import powerpoint_app
from word_app import word_app  # Neuer Import für die Word-App
from transkript import main as transkript_app  # Neuer Import für die Transkript-App

def main():
    # Setze die Seitenkonfiguration als ersten Streamlit-Befehl
    set_page_config()
    apply_global_css()

    # Session-State initialisieren
    initialize_session_state()

    if "app_selected" not in st.session_state:
        st.session_state.app_selected = None

    if st.session_state.app_selected is None:
        selection_page()
    else:
        # Zurück-Button
        if st.button("← Zurück zur Startseite"):
            st.session_state.app_selected = None
            st.rerun()
            
        # App-Auswahl
        if st.session_state.app_selected == "allgemein":
            allgemeine_app()
        elif st.session_state.app_selected == "matching":
            matching_app()
        elif st.session_state.app_selected == "powerpoint":
            powerpoint_app()
        elif st.session_state.app_selected == "word":
            word_app()
        elif st.session_state.app_selected == "transkript":  # Neue Bedingung
            transkript_app()
        else:
            st.error("Unbekannte Anwendung ausgewählt")

if __name__ == "__main__":
    main()
