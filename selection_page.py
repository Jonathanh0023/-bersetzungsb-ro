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
             background: url("https://img.freepik.com/free-vector/gradient-blur-pink-blue-abstract-background_53876-117324.jpg?t=st=1728376415~exp=1728380015~hmac=9ce399175fb8d773a91b45f397ed63826fd2b973ac842a42fa3f94a09efb52c0&w=1380");
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
            "Allgemeines Übersetzungsbüro",
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
            "Key Account Übersetzungsbüro\n\n (Nur für fortgeschrittene Anwender)",
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
            "Matching-App\n\n (Für vorgegebene Übersetzungen und ergänzender KI-Übersetzung)",
            on_click=lambda: select_app("matching"),
            key="matching_button",
        )

# Call the function to display the page
selection_page()
