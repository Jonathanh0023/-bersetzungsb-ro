import streamlit as st
from config import set_page_config, apply_global_css
from utils import initialize_session_state
from selection_page import selection_page
from allgemeine_app import allgemeine_app
from key_account_app import key_account_app
from matching_app import matching_app  # Importiere die Matching-App

def main():
    # Setze die Seitenkonfiguration als ersten Streamlit-Befehl
    apply_global_css()

    # Session-State initialisieren
    initialize_session_state()

    # Steuerung, welche Seite angezeigt wird
    if st.session_state.app_selected is None:
        selection_page()
    elif st.session_state.app_selected == "allgemein":
        allgemeine_app()
    elif st.session_state.app_selected == "key_account":
        key_account_app()
    elif st.session_state.app_selected == "matching":
        matching_app()  # Füge die Matching-App hinzu
    else:
        st.error("Unbekannte Anwendung ausgewählt.")

if __name__ == "__main__":
    main()
