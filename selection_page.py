# selection_page.py
import streamlit as st
from utils import select_app

def set_bg_hack_url():
    '''
    A function to unpack an image from url and set as bg.
    Returns
    -------
    The background.
    '''
        
    st.markdown(
         f"""
         <style>
         .stApp {{
             background: linear-gradient(180deg, rgba(228, 218, 218, 1) 5%, rgb(11 213 237 / 41%) 60%, rgba(229, 0, 127, 0.5) 100%);
             background-size: cover
         }}
         </style>
         """,
         unsafe_allow_html=True
     )
    
def selection_page():
    set_bg_hack_url()  # Call the function to set the background
    st.markdown("<h1>Willkommen im bonsAI Übersetzungsbüro 📚</h1>", unsafe_allow_html=True)
    st.write("Bitte wähle die gewünschte Anwendung aus:")

    # Größere Buttons erstellen - Erste Zeile mit einem Button
    col1, col2, col3 = st.columns([1, 10, 1])  # Make the middle column wider to match the width of two columns below
    with col2:
        st.markdown(
            f"""
            <style>
            div.stButton > button:first-child {{
                height: 150px;
                width: 100%;
                font-size: 18px;
                color: 3c3c3c; /* 3c3c3c text */
                border-radius: 15px; /* Rounded corners */
            }}
            </style>
            """,    
            unsafe_allow_html=True,
        )
        st.button(
            "**Allgemeines KI-Übersetzungsbüro**",
            on_click=lambda: select_app("allgemein"),
            key="allgemein_button",
        )

    # Zweite Zeile mit zwei Buttons in zwei Spalten
    col4, col5 = st.columns(2)
    with col4:
        st.markdown(
            f"""
            <style>
            div.stButton > button:first-child {{
                height: 150px;
                width: 100%;
                font-size: 18px;
                color: 3c3c3c; /* 3c3c3c text */
                border-radius: 15px; /* Rounded corners */
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.button(
            "**Key Account Übersetzungsbüro**\n\n (inaktiv)",
            on_click=lambda: select_app("key_account"),
            key="key_account_button",
        )
    with col5:
        st.markdown(
            f"""
            <style>
            div.stButton > button:first-child {{
                height: 150px;
                width: 100%;
                font-size: 18px;
                color: 3c3c3c; /* 3c3c3c text */
                border-radius: 15px; /* Rounded corners */
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.button(
            "**KI-Matching App**\n\n (Hilft dir dabei, Texte zwischen einer Rogator-Umfrageexport-Datei und einer Übersetzungsdatei abzugleichen und die passenden Übersetzungen zu finden)",
            on_click=lambda: select_app("matching"),
            key="matching_button",
        )
def select_app(app_name):
    st.session_state.app_selected = app_name
# Call the function to display the page
selection_page()
