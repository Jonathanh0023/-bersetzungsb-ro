# allgemeine_app.py 
import streamlit as st
import pandas as pd
from openai import OpenAI
from io import BytesIO
import re
from time import sleep
import tenacity
from utils import select_app, toggle_info
from config import set_page_config, apply_global_css
import requests
import json
import base64

def allgemeine_app():
    # Einstellungen für die allgemeine App
    col1, col2 = st.columns([8, 2])
    with col1:
        st.markdown(f"<h1>Allgemeines Übersetzungsbüro 📚</h1>", unsafe_allow_html=True)
    with col2:
        st.markdown(
            "<div style='display: flex; justify-content: flex-end;'>",
            unsafe_allow_html=True
        )
        st.button("Home", on_click=lambda: select_app(None), key="home_button_allgemein")
        st.markdown("</div>", unsafe_allow_html=True)

    # Funktion zum Validieren des OpenAI API-Keys
    def validate_openai_key(api_key):
        if not api_key:
            return False, "API-Schlüssel darf nicht leer sein."
        
        try:
            # Teste, ob der Key gültig ist, indem wir einen kurzen API-Call machen
            client = OpenAI(api_key=api_key)
            # Wir verwenden einen einfachen, kleinen API-Call um den Key zu validieren
            response = client.models.list()
            return True, "API-Schlüssel ist gültig."
        except Exception as e:
            error_message = str(e)
            if "401" in error_message:
                return False, "Ungültiger API-Schlüssel. Bitte überprüfe dein API-Key."
            elif "429" in error_message:
                return False, "API-Rate-Limit überschritten. Bitte warte einen Moment und versuche es erneut."
            else:
                return False, f"Fehler bei der API-Verbindung: {error_message}"

    # Session-States initialisieren
    if "tutorial_done" not in st.session_state:
        st.session_state.tutorial_done = False  # Tutorial zu Beginn anzeigen
    if "tutorial_step" not in st.session_state:
        st.session_state.tutorial_step = 0

    def reset_tutorial():
        st.session_state.tutorial_done = False
        st.session_state.tutorial_step = 0

    def next_step():
        st.session_state.tutorial_step += 1

    def skip_tutorial():
        st.session_state.tutorial_done = True
        st.session_state.tutorial_step = 0

    def finish_tutorial():
        st.session_state.tutorial_done = True
        st.session_state.tutorial_step = 0

    # Erklärungstexte für die Info-Icons
    info_texts = {
        "api_key": "Hier trägst du deinen OpenAI API-Schlüssel ein. Ohne diesen können wir leider nicht loslegen. Den aktuellen API-Schlüssel erhältst du von Jonathan Heeckt oder Tobias Bucher.",
        "model_selection": "Wähle das GPT-Modell aus, das du verwenden möchtest. Für die beste Leistung empfehlen wir dir GPT-4o.",
        "batch_size": "Hier bestimmst du, wie viele Zeilen auf einmal übersetzt werden. Wir empfehlen dir eine Batchgröße von 10. Achtung: Umso größer die Batchsize umso schneller und günstiger, aber auch umso fehleranfälliger ist die Übersetzung.",
        "language_selection": "Wähle die Ausgangs- und Zielsprache deiner Übersetzung. Sollte deine gewünschte Ausgangs-/ Zielsprache nicht verfügbar sein, melde dich gerne bei Jonathan Heeckt oder Tobias Bucher.",
        "respondent_group": "Diese Felder helfen der KI, den Kontext deiner Übersetzung besser zu verstehen. Gebe die Befragtengruppe und das Thema am besten auf Englisch ein.",
        "survey_content": "Beschreibe hier kurz in 1-2 Sätzen auf Englisch, worum es in deinem Fragebogen geht und was das Ziel deiner Befragung ist, damit die KI bestimmte Begriffe besser übersetzen kann.\n\nz.B. 'The purpose of the questionnaire is to determine whether dentists recommend Listerine as a mouthwash and to understand their reasons for doing so or not.'",
        "file_upload": "Lade die Datei hoch, die übersetzt werden soll. Aktuell werden Dateien ausschließlich im Excel-Format akzeptiert.\nAchtung: Es wird immer die Spalte mit der Überschrift 'Text zur Übersetzung / Versionsanpassung' übersetzt, Spalten mit anderen Überschriften werden nicht übersetzt. Sobald deine Excel-Datei erfolgreich hochgeladen wurde, erscheint deine Excel-Datei als Tabelle im bonsAI Übersetzungsbüro.\n\nDurch das Anklicken des Buttons 'Übersetzen' startet das Tool mit der Übersetzung. Die Übersetzung wird im Hintergrund durchgeführt und du erhältst eine E-Mail, sobald diese abgeschlossen ist.",
        "country": "Hier wählst du das Land aus, in dem die Befragung durchgeführt wird. Die Übersetzung wird an die kulturellen Besonderheiten dieses Ziellandes angepasst.",
        "email": "Gib hier deine E-Mail-Adresse ein, an die wir die fertige Übersetzung senden sollen. Du erhältst eine Benachrichtigung, sobald deine Übersetzung abgeschlossen ist."
    }

    # Tutorial anzeigen
    def show_tutorial():
        tutorial_steps = [
            {
                "title": "Willkommen im Allgemeinen bonsAI Übersetzungsbüro!",
                "content": "Schön, dass du da bist! Lass uns zusammen herausfinden, wie alles funktioniert. Klicke auf 'Weiter', um mit dem Tutorial zu starten.\n\nFalls du der Meinung bist, dass du dich schon bestens auskennst, dann klicke auf 'Tutorial überspringen'.\n",
                "widget": lambda: None,
            },
            {
                "title": "Schritt 1: API-Schlüssel",
                "content": "Hier trägst du deinen OpenAI API-Schlüssel ein. Ohne diesen können wir leider nicht loslegen. Den aktuellen API-Schlüssel erhältst du von Jonathan Heeckt oder Tobias Bucher.\n",
                "widget": lambda: st.text_input(
                    "Gib deinen OpenAI API-Schlüssel ein",
                    type="password",
                    disabled=True,
                ),
            },
            {
                "title": "Schritt 2: Modellauswahl",
                "content": "Wähle das GPT-Modell aus, das du verwenden möchtest. Für die beste Leistung empfehlen wir dir GPT-4o.\n",
                "widget": lambda: st.selectbox(
                    "Wähle das Modell",
                    ["gpt-4o", "gpt-4o-mini", "gpt-o1-mini", "o3-mini"],
                    disabled=True,
                ),
            },
            {
                "title": "Schritt 3: Batchgröße festlegen",
                "content": "Hier bestimmst du, wie viele Zeilen auf einmal übersetzt werden. Wir empfehlen dir eine Batchgröße von 10.\n\nAchtung: Umso größer die Batchgröße, umso schneller und günstiger, aber auch umso fehleranfälliger ist die Übersetzung.\n",
                "widget": lambda: st.slider(
                    "Batchgröße",
                    min_value=2,
                    max_value=50,
                    value=10,
                    step=2,
                    disabled=True,
                ),
            },
            {
                "title": "Schritt 4: Spracheinstellungen",
                "content": "Wähle die Ausgangs- und Zielsprache deiner Übersetzung.\n",
                "widget": lambda: (
                    st.selectbox(
                        "Ausgangssprache",
                        ["English", "German", "French", "Spanish", "Italian", "Polish", "Arabic"],
                        disabled=True,
                    ),
                    st.selectbox(
                        "Zielsprache",
                        ["German", "English", "French", "Spanish", "Italian", "Polish", "Arabic"],
                        disabled=True,
                    ),
                ),
            },
            {
                "title": "Schritt 5: Zielland",
                "content": "Wähle das Land aus, in dem die Befragung durchgeführt wird. Die Übersetzung wird an die kulturellen Gegebenheiten dieses Ziellandes angepasst.\n",
                "widget": lambda: st.text_input(
                    "Land, in dem die Befragung durchgeführt wird, z.B. 'Germany'",
                    disabled=True,
                ),
            },
            {
                "title": "Schritt 6: Befragtengruppe und Thema angeben",
                "content": "Diese Felder helfen der KI, den Kontext deiner Übersetzung besser zu verstehen. Gib die Befragtengruppe und das Thema am besten auf Englisch ein.\n",
                "widget": lambda: (
                    st.text_input(
                        "Befragtengruppe auf Englisch eingeben, z.B. 'Dentists'",
                        disabled=True,
                    ),
                    st.text_input(
                        "Thema der Befragung auf Englisch eingeben, z.B. 'dental hygiene'",
                        disabled=True,
                    ),
                ),
            },
            {
                "title": "Schritt 7: Fragebogen",
                "content": "Beschreibe hier kurz in 1-2 Sätzen auf Englisch, worum es in deinem Fragebogen geht und was das Ziel deiner Befragung ist, damit die KI bestimmte Begriffe besser übersetzen kann.\n\nz.B. 'The purpose of the questionnaire is to determine whether dentists recommend Listerine as a mouthwash and to understand their reasons for doing so or not.'\n",
                "widget": lambda: st.text_area(
                    "Beschreibe hier in 1-2 Sätzen das Ziel und das Thema des Fragebogens auf Englisch.",
                    height=100,
                    disabled=True,
                ),
            },
            {
                "title": "Schritt 8: E-Mail-Adresse",
                "content": "Gib hier deine E-Mail-Adresse ein, an die wir die fertige Übersetzung senden sollen. Du erhältst eine Benachrichtigung, sobald deine Übersetzung abgeschlossen ist.\n",
                "widget": lambda: st.text_input(
                    "E-Mail-Adresse eingeben",
                    disabled=True,
                ),
            },
            {
                "title": "Schritt 9: Dateiupload",
                "content": "Lade die Datei hoch, die übersetzt werden soll. Aktuell werden Dateien ausschließlich im Excel-Format akzeptiert.\nAchtung: Es wird immer die Spalte mit der Überschrift 'Text zur Übersetzung / Versionsanpassung' übersetzt, Spalten mit anderen Überschriften werden nicht übersetzt.\n\n",
                "widget": lambda: st.file_uploader(
                    "Wähle eine Datei", type=["xlsx"], disabled=True
                ),
            },
            {
                "title": "Schritt 10: Übersetzung starten",
                "content": "Sobald deine Excel-Datei erfolgreich hochgeladen wurde, erscheint deine Excel-Datei als Tabelle im bonsAI Übersetzungsbüro.\n\nDurch das Anklicken des Buttons 'Übersetzen' startet das Tool mit der Übersetzung. Die Übersetzung erfolgt im Hintergrund und du erhältst eine E-Mail mit einem Link zur fertigen Übersetzung, sobald diese abgeschlossen ist.",
                "widget": lambda: None,
            },
            {
                "title": "Let's Go 🚀",
                "content": "Du hast das Tutorial erfolgreich abgeschlossen. Nun viel Spaß beim Verwenden des bonsAI Übersetzungsbüros!\n",
                "widget": lambda: None,
            },
        ]

        step = st.session_state.tutorial_step
        if step < len(tutorial_steps):
            st.subheader(tutorial_steps[step]["title"])
            st.write(tutorial_steps[step]["content"])
            tutorial_steps[step]["widget"]()
            if step < len(tutorial_steps) - 1:
                col1, col2 = st.columns([1, 1])
                col1.button("Weiter", on_click=next_step)
                col2.button("Tutorial überspringen", on_click=skip_tutorial)
            else:
                col1, col2 = st.columns([1, 1])
                col1.button("Zur App", on_click=finish_tutorial)
                col2.button("Tutorial überspringen", on_click=skip_tutorial)
        else:
            st.session_state.tutorial_done = True
            st.session_state.tutorial_step = 0

    # Systemanweisung für die Übersetzung
    def generate_system_message(
        source_language,
        respondent_group,
        survey_topic,
        target_language,
        survey_content,
        country
    ):
        return (
            f"You are assisting an English-speaking programmer in translating a questionnaire from {source_language} into {target_language}."
            f"The topic of the survey is '{survey_topic}'. Your primary goal is to ensure that the translation sounds natural and fluent for native speakers while preserving all technical and programming elements accurately.\n\n"
            "Programming Instructions: All programming instructions, including codes and strings (e.g., 'Screenout', 'Quote'), must remain exactly as they are in the translation. "
            "Rogator-specific syntax, which always begins with !% and ends with %!, represents dynamic placeholders and must be retained unchanged, as these will later be populated by the software.\n\n"
            "Curly Brace Elements: Retain all elements within curly braces and any country codes without translating them.\n\n"
            "Form of Address: Use the polite form ('Sie') for direct addresses. For job titles or personal forms of address, ensure gender inclusivity by using both masculine and feminine forms or a gender-neutral term if appropriate.\n\n"
            "Content Translation: Translate the meaning rather than word-for-word. Ensure the translation is fluent and natural for native speakers, without changing the original intent."
            "For example: If the sentence already uses a polite form of address, such as 'Veuillez' or 'Pourriez-vous' in French, it is not necessary to include phrases like 's'il vous plaît' for example."
            "The German phrase 'Würden Sie uns bitte' would be translated into French as 'Veuillez nous' and the 's'il vous plaît' can be omitted.\n\n"
            "Language-Specific Conventions: Pay special attention to conventional sentence structures and placement of polite expressions in the target language. For French, for example, the phrase 's'il vous plaît' is typically placed at the beginning or end of the sentence, not in the middle."
            f"Consistency in Style: Ensure a consistent and natural style throughout the translation, adapting the language to suit {target_language} linguistic nuances. Your response should include only the translated text. "
            "If the input is a code or a placeholder, reproduce it exactly without translation.\n\n"
            f"For reference, here is background information on the questionnaire's purpose and target audience:\n{survey_content}\n\n"
            f"Also, be sure to consider cultural nuances and conventions relevant to {country}. If any cultural adjustments need to be made to improve clarity, precision and appropriateness for respondents in {country}, please integrate them. When translating, base your translation on how the wording, sentence structure and linguistic expression is usually formulated in {country}.\n\n"
            f"Attention to detail and take your time: Take the necessary time to carefully consider each term. It is critical to maintain accuracy, modified sentence structure, and cultural appropriateness in {country} in the translated text."
        )

    def main_app():
        def toggle_info(key):
            # Toggle the visibility of the info popup
            if key not in st.session_state:
                st.session_state[key] = False
            st.session_state[key] = not st.session_state[key]

        # API-Schlüssel Eingabefeld mit Infobutton
        col_api, col_info = st.columns([10, 1])
        with col_api:
            st.subheader("API-Schlüssel")
        with col_info:
            if st.button("ℹ️", key="info_api_key"):
                toggle_info("show_api_key_info")
        if st.session_state.get("show_api_key_info", False):
            st.info(info_texts["api_key"])
        api_key = st.text_input("Gib deinen OpenAI API-Schlüssel ein", type="password")
        
        # Sofort API-Schlüssel validieren, wenn ein Wert eingegeben wurde
        if api_key:
            validate_button = st.button("API-Schlüssel validieren")
            if validate_button:
                with st.spinner("API-Schlüssel wird validiert..."):
                    is_valid, message = validate_openai_key(api_key)
                    if is_valid:
                        st.success(message)
                    else:
                        st.error(message)

        # Auswahl des GPT-Modells
        col1, col2 = st.columns([10, 1])
        with col1:
            st.subheader("Modellauswahl")
        with col2:
            if st.button("ℹ️", key="info_model_selection"):
                toggle_info("show_model_selection_info")
        if st.session_state.get("show_model_selection_info", False):
            st.info(info_texts["model_selection"])
        model_options = ["o3-mini", "gpt-4o-mini", "gpt-4o"]
        selected_model = st.selectbox("Wähle das Modell", model_options, index=0)

        # Eingabefeld für die Batchgröße
        col1, col2 = st.columns([10, 1])
        with col1:
            st.subheader("Batchgröße")
        with col2:
            if st.button("ℹ️", key="info_batch_size"):
                toggle_info("show_batch_size_info")
        if st.session_state.get("show_batch_size_info", False):
            st.info(info_texts["batch_size"])
        batch_size = st.slider(
            "Batchgröße", min_value=2, max_value=50, value=10, step=2
        )

        # Dropdowns für Sprachen
        col1, col2 = st.columns([10, 1])
        with col1:
            st.subheader("Spracheinstellungen")
        with col2:
            if st.button("ℹ️", key="info_language_selection"):
                toggle_info("show_language_selection_info")
        if st.session_state.get("show_language_selection_info", False):
            st.info(info_texts["language_selection"])
        language_options = [
            "English",
            "German",
            "French",
            "Spanish",
            "Italian",
            "Polish",
            "Arabic",
            "Swedish"
        ]
        source_language = st.selectbox("Ausgangssprache", language_options, index=0)
        target_language = st.selectbox("Zielsprache", language_options, index=1)

        # Zielland-Eingabefeld mit Info-Icon
        col1, col2 = st.columns([10, 1])
        with col1:
            st.subheader("Zielland")
        with col2:
            if st.button("ℹ️", key="info_country"):
                toggle_info("show_country_info")
        if st.session_state.get("show_country_info", False):
            st.info(info_texts["country"])
        country = st.text_input("Land, in dem die Befragung durchgeführt wird (z.B. 'Germany'): ")

        # Neue Eingabefelder für Befragtengruppe und Thema der Befragung
        col1, col2 = st.columns([10, 1])
        with col1:
            st.subheader("Befragtengruppe und Thema")
        with col2:
            if st.button("ℹ️", key="info_respondent_group"):
                toggle_info("show_respondent_group_info")
        if st.session_state.get("show_respondent_group_info", False):
            st.info(info_texts["respondent_group"])
        respondent_group = st.text_input(
            "Befragtengruppe auf Englisch eingeben, z.B. 'Dentists'"
        )
        survey_topic = st.text_input(
            "Thema der Befragung auf Englisch eingeben, z.B. 'dental hygiene'"
        )

        # Fragebogen
        col1, col2 = st.columns([10, 1])
        with col1:
            st.subheader("Fragebogen")
        with col2:
            if st.button("ℹ️", key="info_survey_content"):
                toggle_info("show_survey_content_info")
        if st.session_state.get("show_survey_content_info", False):
            st.info(info_texts["survey_content"])
        survey_content = st.text_area(
            "Beschreibe hier in 1-2 Sätzen das Ziel und das Thema des Fragebogens auf Englisch.",
            height=100,
        )

        # E-Mail-Adresse für den Erhalt der Übersetzung
        col1, col2 = st.columns([10, 1])
        with col1:
            st.subheader("E-Mail-Adresse")
        with col2:
            if st.button("ℹ️", key="info_email"):
                toggle_info("show_email_info")
        if st.session_state.get("show_email_info", False):
            st.info(info_texts["email"])
        email = st.text_input("E-Mail-Adresse eingeben")

        # Dynamisch generierte Systemanweisung
        system_message = generate_system_message(
            source_language,
            respondent_group,
            survey_topic,
            target_language,
            survey_content,
            country
        )

        # Zusammenklappbare Systemanweisung mit Warnhinweis
        with st.expander(
            "Systemanweisung (Achtung: Nur für fortgeschrittene Anwender)"
        ):
            custom_system_message = st.text_area(
                "Gib die Systemanweisung ein", value=system_message, height=200
            )

        # Funktion zur Bereinigung des Textes
        def clean_text(text):
            if pd.isna(text):
                return text
            # Normalisiere Whitespace (entfernt überflüssige Leerzeichen, Umbrüche)
            text = ' '.join(text.split())
            return text

        # Dateiupload
        col1, col2 = st.columns([10, 1])
        with col1:
            st.subheader("Dateiupload")
        with col2:
            if st.button("ℹ️", key="info_file_upload"):
                toggle_info("show_file_upload_info")
        if st.session_state.get("show_file_upload_info", False):
            st.info(info_texts["file_upload"])
        uploaded_file = st.file_uploader("Wähle eine Datei", type=["xlsx"])

        if uploaded_file is not None:
            df = pd.read_excel(uploaded_file)
            if "Vergleichstext Ursprungsversion" not in df.columns or "Text zur Übersetzung / Versionsanpassung" not in df.columns:
                st.error("Die hochgeladene Excel-Datei enthält nicht die erforderlichen Spalten 'Vergleichstext Ursprungsversion' und/oder 'Text zur Übersetzung / Versionsanpassung'. Bitte laden Sie eine gültige Datei hoch.")
                return

            # Vorverarbeitung der Texte
            df["Vergleichstext Ursprungsversion"] = df["Vergleichstext Ursprungsversion"].apply(clean_text)

            st.write("Originaltext")
            st.dataframe(df)

            # Button "Übersetzen" hier platzieren
            translate_button = st.button("Übersetzen")
            if translate_button:
                # Erstelle eine Liste für die Validierungsmeldungen
                validation_errors = []
                
                # Validiere alle Eingaben bevor der Job gestartet wird
                if not api_key:
                    validation_errors.append("- Bitte gib einen API-Schlüssel ein.")
                
                if not email:
                    validation_errors.append("- Bitte gib eine E-Mail-Adresse ein.")
                
                if not country:
                    validation_errors.append("- Bitte gib das Zielland ein.")
                
                if not respondent_group:
                    validation_errors.append("- Bitte gib die Befragtengruppe ein.")
                
                if not survey_topic:
                    validation_errors.append("- Bitte gib das Thema der Befragung ein.")
                
                if not survey_content:
                    validation_errors.append("- Bitte beschreibe das Ziel und Thema des Fragebogens.")
                
                if not uploaded_file:
                    validation_errors.append("- Bitte lade eine Excel-Datei hoch.")
                
                # Wenn Validierungsfehler vorhanden sind, zeige sie an und beende die Funktion
                if validation_errors:
                    st.error("Bitte fülle alle erforderlichen Felder aus:\n" + "\n".join(validation_errors))
                    return
                
                # Validiere den OpenAI API-Key
                with st.spinner("API-Schlüssel wird validiert..."):
                    is_valid, message = validate_openai_key(api_key)
                    if not is_valid:
                        st.error(f"Der API-Schlüssel ist ungültig: {message}")
                        return
                
                try:
                    # Fortschrittsanzeige
                    with st.spinner("Übersetzungsjob wird gestartet..."):
                        # Datei als Base64 kodieren
                        output_buffer = BytesIO()
                        with pd.ExcelWriter(output_buffer, engine="xlsxwriter") as writer:
                            df.to_excel(writer, index=False)
                        output_buffer.seek(0)
                        file_data = base64.b64encode(output_buffer.getvalue()).decode("utf-8")
                        
                        # Daten für die Supabase-Edge-Funktion vorbereiten
                        response = requests.post(
                            "https://tyggaqynkmujggfszrvc.supabase.co/functions/v1/start-translation",
                            json={
                                "email": email,
                                "fileData": file_data,
                                "fileName": uploaded_file.name,
                                "original_filename": uploaded_file.name,
                                "source_language": source_language,
                                "target_language": target_language,
                                "country": country,
                                "respondent_group": respondent_group,
                                "survey_topic": survey_topic,
                                "survey_content": survey_content,
                                "api_key": api_key,
                                "model": selected_model,
                                "batch_size": batch_size,
                                "system_message": custom_system_message
                            },
                            headers={
                                "Content-Type": "application/json",
                                "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InR5Z2dhcXlua211amdnZnN6cnZjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDI5OTA4MzAsImV4cCI6MjA1ODU2NjgzMH0.VACjxNLN_0AnN37xfrYcb-8b-5bOQgBfgLdl29I-HoE"
                            }
                        )
                        
                        # Detailliertere Fehlerbehandlung
                        if response.status_code == 200:
                            response_data = response.json()
                            st.success(f"""
                            Übersetzungsjob erfolgreich gestartet!
                            
                            Deine Übersetzung wird im Hintergrund verarbeitet. Sobald sie fertig ist, erhältst du eine E-Mail an {email} mit einem Link zum Herunterladen der übersetzten Datei. Falls du keine E-Mail erhalten hast, bitte überprüfe deinen Spam-Ordner. 
                            
                            Den Fortschritt deines Jobs kannst du jederzeit in der "Alle Jobs" App auf der Startseite verfolgen.

                            Job-ID: {response_data.get('jobId')}
                            """)
                        else:
                            # Versuche, detailliertere Fehlerinformationen zu extrahieren
                            try:
                                error_data = response.json()
                                error_message = error_data.get('error', 'Kein spezifischer Fehler zurückgegeben')
                                st.error(f"Fehler beim Starten des Übersetzungsjobs (Status: {response.status_code}): {error_message}")
                                st.error(f"Vollständige Antwort: {error_data}")
                            except Exception as json_error:
                                st.error(f"Fehler beim Starten des Übersetzungsjobs (Status: {response.status_code})")
                                st.error(f"Antworttext: {response.text}")
                            
                except Exception as e:
                    st.error(f"Ein Fehler ist aufgetreten: {str(e)}")
                    # Zeige den vollständigen Fehler in einem Expander für Entwickler
                    with st.expander("Fehlerdetails (für Entwickler)"):
                        st.exception(e)
                        st.write("Exception Typ:", type(e).__name__)

    # Zeige Hauptanwendung oder Tutorial
    if st.session_state.tutorial_done:
        main_app()
    else:
        show_tutorial()


