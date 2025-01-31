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
    st.markdown(
        """
        <div style='display: flex; align-items: center; justify-content: center; width: 100%;'>
            <h1 style='margin: 0; display: inline-flex; align-items: center; white-space: nowrap;'>
                <img src='https://sw01.rogsurvey.de/data/bonsai/Kara_23_19/logo_Bonsa_BONSAI_neu.png' 
                     style='height: 80px; margin-right: 10px;'/>
                Willkommen im bonsAI Übersetzungsbüro 📚
            </h1>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Center the instruction text
    st.markdown(
        """
        <div style='text-align: center; margin-top: 10px; margin-bottom: 0px;'>
            <h2 style='font-size: 16px;'>Bitte wähle die gewünschte Anwendung aus:</h2>
        </div>
        """,
        unsafe_allow_html=True
    )

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
                color: #3c3c3c; /* Corrected color format */
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
                color: #3c3c3c;
                border-radius: 15px;
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
                color: #3c3c3c;
                border-radius: 15px;
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

    # Dritte Zeile mit zwei Buttons für PowerPoint und Word
    col6, col7 = st.columns(2)
    with col6:
        st.markdown(
            f"""
            <style>
            div.stButton > button:first-child {{
                height: 150px;
                width: 100%;
                font-size: 18px;
                color: #3c3c3c;
                border-radius: 15px;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.button(
            "**PowerPoint Übersetzer**\n\n(Überprüft und korrigiert die Sprache in PowerPoint-Präsentationen)",
            on_click=lambda: select_app("powerpoint"),
            key="powerpoint_button",
        )
    
    with col7:
        st.markdown(
            f"""
            <style>
            div.stButton > button:first-child {{
                height: 150px;
                width: 100%;
                font-size: 18px;
                color: #3c3c3c;
                border-radius: 15px;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.button(
            "**Word Übersetzer**\n\n(Überprüft und korrigiert die Sprache in Word-Dokumenten)",
            on_click=lambda: select_app("word"),
            key="word_button",
        )

    # Neue Zeile für die Transkript-Apps (nebeneinander)
    col8, col9 = st.columns(2)
    with col8:
        st.markdown(
            f"""
            <style>
            div.stButton > button:first-child {{
                height: 150px;
                width: 100%;
                font-size: 18px;
                color: #3c3c3c;
                border-radius: 15px;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.button(
            "**Audio-Transkription**\n\n(Konvertiert Audio- und Videodateien in Text. Kann Trankripte in Originalsprache oder auf Englisch erstellen)",
            on_click=lambda: select_app("transkript"),
            key="transkript_button",
        )

    with col9:
        st.markdown(
            f"""
            <style>
            div.stButton > button:first-child {{
                height: 150px;
                width: 100%;
                font-size: 18px;
                color: #3c3c3c;
                border-radius: 15px;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.button(
            "**Word-Dokument-Verarbeitung**\n\n(Word-Dokumente können hier von der KI beliebig bearbeitet werden)",
            on_click=lambda: select_app("transkript_verarbeitung"),
            key="transkript_verarbeitung_button",
        )

def select_app(app_name):
    st.session_state.app_selected = app_name

# Removed the following line to prevent duplicate invocations
# selection_page()
