# allgemeine_app.py
import streamlit as st
import pandas as pd
import requests
import base64
import time
import uuid
from io import BytesIO
from utils import select_app, toggle_info  # Stelle sicher, dass diese Module vorhanden sind
from config import set_page_config, apply_global_css  # Passe diese Funktionen ggf. an

# Seitenkonfiguration & globale CSS-Einstellungen laden (optional, falls definiert)
set_page_config()
apply_global_css()

# Funktion zur Erzeugung einer eindeutigen Job-ID
def generate_job_id():
    return str(uuid.uuid4())

def allgemeine_app():
    # Überschrift der App
    st.markdown("<h1>Allgemeines Übersetzungsbüro 📚</h1>", unsafe_allow_html=True)
    
    # Abfrage der E-Mail-Adresse (wird benötigt, um das fertige Übersetzungsergebnis zu senden)
    email = st.text_input("Bitte gib deine E-Mail-Adresse ein, um das fertige Übersetzungsergebnis zu erhalten:")
    
    # Session-States für das Tutorial initialisieren
    if "tutorial_done" not in st.session_state:
        st.session_state.tutorial_done = False
    if "tutorial_step" not in st.session_state:
        st.session_state.tutorial_step = 0

    # Tutorial-Schritte definieren
    tutorial_steps = [
        {
            "title": "Willkommen im Übersetzungsbüro",
            "content": "Schön, dass du hier bist! Dieses Tutorial zeigt dir, wie du deine Übersetzung startest. Klicke auf 'Weiter', um fortzufahren.",
        },
        {
            "title": "E-Mail-Adresse",
            "content": "Gib bitte deine E-Mail-Adresse ein, damit wir dir das fertige Übersetzungsergebnis zusenden können.",
        },
        {
            "title": "API-Schlüssel & Modellauswahl",
            "content": "Trage deinen OpenAI API-Schlüssel ein und wähle das gewünschte Modell aus.",
        },
        {
            "title": "Weitere Einstellungen",
            "content": "Lege die Batchgröße, die Spracheinstellungen, das Zielland, die Befragtengruppe und das Thema der Befragung fest.",
        },
        {
            "title": "Dateiupload",
            "content": "Lade eine Excel-Datei hoch, die die erforderlichen Spalten 'Vergleichstext Ursprungsversion' und 'Text zur Übersetzung / Versionsanpassung' enthält.",
        },
        {
            "title": "Start der Übersetzung",
            "content": "Klicke auf 'Übersetzen', um den Übersetzungsvorgang zu starten. Du erhältst anschließend eine Bestätigung und die fertige Übersetzung per E-Mail.",
        }
    ]
    
    # Funktion zur Anzeige des Tutorials
    def show_tutorial():
        step = st.session_state.tutorial_step
        st.subheader(tutorial_steps[step]["title"])
        st.write(tutorial_steps[step]["content"])
        col1, col2 = st.columns(2)
        if step > 0:
            if col1.button("Zurück"):
                st.session_state.tutorial_step = max(0, step - 1)
        if st.session_state.tutorial_step < len(tutorial_steps) - 1:
            if col2.button("Weiter"):
                st.session_state.tutorial_step += 1
        else:
            if col2.button("Tutorial abschließen"):
                st.session_state.tutorial_done = True

    # Hauptanwendung mit allen Eingabefeldern
    def main_app():
        st.subheader("API-Schlüssel")
        api_key = st.text_input("Gib deinen OpenAI API-Schlüssel ein", type="password")
        
        st.subheader("Modellauswahl")
        model_options = ["o3-mini", "gpt-4o-mini", "gpt-4o"]
        selected_model = st.selectbox("Wähle das Modell", model_options, index=0)
        
        st.subheader("Batchgröße")
        batch_size = st.slider("Batchgröße", min_value=2, max_value=50, value=10, step=2)
        
        st.subheader("Spracheinstellungen")
        language_options = ["English", "German", "French", "Spanish", "Italian", "Polish", "Arabic", "Swedish"]
        source_language = st.selectbox("Ausgangssprache", language_options, index=0)
        target_language = st.selectbox("Zielsprache", language_options, index=1)
        
        st.subheader("Zielland")
        country = st.text_input("Land, in dem die Befragung durchgeführt wird (z.B. 'Germany'):")
        
        st.subheader("Befragtengruppe und Thema")
        respondent_group = st.text_input("Befragtengruppe (z.B. 'Dentists'):")
        survey_topic = st.text_input("Thema der Befragung (z.B. 'dental hygiene'):")
        
        st.subheader("Fragebogen")
        survey_content = st.text_area("Beschreibe in 1-2 Sätzen das Ziel und das Thema des Fragebogens auf Englisch.", height=100)
        
        # Dynamisch generierte Systemanweisung (vereinfacht)
        system_message = (
            f"You are assisting an English-speaking programmer in translating a questionnaire. "
            f"Source language: {source_language}, Target language: {target_language}. "
            f"Survey topic: {survey_topic}. Additional info: {survey_content}."
        )
        
        st.subheader("Dateiupload")
        uploaded_file = st.file_uploader("Wähle eine Excel-Datei", type=["xlsx"])
        
        if uploaded_file is not None:
            try:
                df = pd.read_excel(uploaded_file)
            except Exception as e:
                st.error(f"Fehler beim Einlesen der Datei: {e}")
                return
            
            # Überprüfe, ob die erforderlichen Spalten vorhanden sind
            required_columns = ["Vergleichstext Ursprungsversion", "Text zur Übersetzung / Versionsanpassung"]
            if not all(col in df.columns for col in required_columns):
                st.error("Die Excel-Datei enthält nicht die erforderlichen Spalten.")
                return
            
            st.write("Originaltext:")
            st.dataframe(df)
            
            # Generiere eine eindeutige Job-ID
            job_id = generate_job_id()
            st.info(f"Deine Job-ID: {job_id}")
            
            # Dateiinhalt in Base64 kodieren
            file_bytes = uploaded_file.read()
            file_base64 = base64.b64encode(file_bytes).decode("utf-8")
            
            # Payload zusammenstellen
            payload = {
                "job_id": job_id,
                "email": email,
                "api_key": api_key,
                "selected_model": selected_model,
                "batch_size": batch_size,
                "source_language": source_language,
                "target_language": target_language,
                "country": country,
                "respondent_group": respondent_group,
                "survey_topic": survey_topic,
                "survey_content": survey_content,
                "system_message": system_message,
                "file_base64": file_base64,
            }
            
            # Zapier Webhook URL (wie eingerichtet)
            zapier_webhook_url = "https://hooks.zapier.com/hooks/catch/22221288/2c8vwqv/"
            
            if st.button("Übersetzen"):
                try:
                    response = requests.post(zapier_webhook_url, json=payload, timeout=10)
                    if response.status_code == 200:
                        st.success("Der Übersetzungsvorgang wurde gestartet. Du erhältst das Ergebnis per E-Mail.")
                    else:
                        st.error("Fehler beim Starten des Übersetzungsvorgangs.")
                except Exception as ex:
                    st.error(f"Ein Fehler ist aufgetreten: {ex}")
                
                # Simulierte Fortschrittsanzeige (in der Produktion über Supabase oder deinen API-Endpunkt abfragen)
                progress_placeholder = st.empty()
                for i in range(0, 101, 10):
                    progress_placeholder.progress(i)
                    time.sleep(0.5)
                st.info("Übersetzung gestartet – der Fortschritt wird aktualisiert.")
        else:
            st.info("Bitte lade eine Excel-Datei hoch.")
    
    # Anzeige entweder des Tutorials oder der Hauptanwendung
    if st.session_state.tutorial_done:
        main_app()
    else:
        show_tutorial()

if __name__ == "__main__":
    allgemeine_app()


if __name__ == "__main__":
    allgemeine_app()

