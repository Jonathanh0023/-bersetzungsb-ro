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
        st.markdown(f"<h1>Allgemeines Übersetzungsbüro 📖</h1>", unsafe_allow_html=True)
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
        api_key = st.text_input("Gib deinen OpenAI API-Schlüssel ein", type="password", key="api_key_input")

        # Modellauswahl mit Infobutton
        col_model, col_info = st.columns([10, 1])
        with col_model:
            st.subheader("Modellauswahl")
        with col_info:
            if st.button("ℹ️", key="info_model_selection"):
                toggle_info("show_model_selection_info")
        if st.session_state.get("show_model_selection_info", False):
            st.info(info_texts["model_selection"])
        model_options = ["gpt-4o", "gpt-4o-mini", "gpt-o1-mini", "o3-mini"]
        selected_model = st.selectbox("Wähle ein Modell", model_options, index=1)

        # Batchgröße mit Infobutton
        col_batch, col_info = st.columns([10, 1])
        with col_batch:
            st.subheader("Batchgröße")
        with col_info:
            if st.button("ℹ️", key="info_batch_size"):
                toggle_info("show_batch_size_info")
        if st.session_state.get("show_batch_size_info", False):
            st.info(info_texts["batch_size"])
        batch_size = st.slider("Batchgröße", min_value=2, max_value=50, value=10, step=2)

        # Ausgangs- und Zielsprache mit Infobutton
        col_lang, col_info = st.columns([10, 1])
        with col_lang:
            st.subheader("Sprachen")
        with col_info:
            if st.button("ℹ️", key="info_language_selection"):
                toggle_info("show_language_selection_info")
        if st.session_state.get("show_language_selection_info", False):
            st.info(info_texts["language_selection"])

        col1, col2 = st.columns(2)
        with col1:
            source_language = st.selectbox(
                "Ausgangssprache", 
                ["English", "German", "French", "Spanish", "Italian", "Polish", "Dutch", "Portuguese", "Russian", "Turkish", "Arabic", "Chinese", "Japanese", "Korean", "Vietnamese", "Other"]
            )
        with col2:
            target_language = st.selectbox(
                "Zielsprache", 
                ["German", "English", "French", "Spanish", "Italian", "Polish", "Dutch", "Portuguese", "Russian", "Turkish", "Arabic", "Chinese", "Japanese", "Korean", "Vietnamese", "Other"]
            )

        # Zielland mit Infobutton
        col_country, col_info = st.columns([10, 1])
        with col_country:
            st.subheader("Zielland")
        with col_info:
            if st.button("ℹ️", key="info_country"):
                toggle_info("show_country_info")
        if st.session_state.get("show_country_info", False):
            st.info(info_texts["country"])
        country = st.text_input("Land, in dem die Befragung durchgeführt wird, z.B. 'Germany'")

        # Befragtengruppe und Thema mit Infobutton
        col_resp, col_info = st.columns([10, 1])
        with col_resp:
            st.subheader("Befragtengruppe und Thema")
        with col_info:
            if st.button("ℹ️", key="info_respondent_group"):
                toggle_info("show_respondent_group_info")
        if st.session_state.get("show_respondent_group_info", False):
            st.info(info_texts["respondent_group"])

        col1, col2 = st.columns(2)
        with col1:
            respondent_group = st.text_input("Befragtengruppe auf Englisch eingeben, z.B. 'Dentists'")
        with col2:
            survey_topic = st.text_input("Thema der Befragung auf Englisch eingeben, z.B. 'dental hygiene'")

        # Fragebogeninformationen mit Infobutton
        col_survey, col_info = st.columns([10, 1])
        with col_survey:
            st.subheader("Fragebogeninformationen")
        with col_info:
            if st.button("ℹ️", key="info_survey_content"):
                toggle_info("show_survey_content_info")
        if st.session_state.get("show_survey_content_info", False):
            st.info(info_texts["survey_content"])
        survey_content = st.text_area("Beschreibe hier in 1-2 Sätzen das Ziel und das Thema des Fragebogens auf Englisch.", height=100)

        # E-Mail-Adresse mit Infobutton
        col_email, col_info = st.columns([10, 1])
        with col_email:
            st.subheader("E-Mail-Adresse für Benachrichtigung")
        with col_info:
            if st.button("ℹ️", key="info_email"):
                toggle_info("show_email_info")
        if st.session_state.get("show_email_info", False):
            st.info(info_texts["email"])
        email = st.text_input("E-Mail-Adresse eingeben")

        # Datei hochladen mit Infobutton
        col_file, col_info = st.columns([10, 1])
        with col_file:
            st.subheader("Datei hochladen")
        with col_info:
            if st.button("ℹ️", key="info_file_upload"):
                toggle_info("show_file_upload_info")
        if st.session_state.get("show_file_upload_info", False):
            st.info(info_texts["file_upload"])

        uploaded_file = st.file_uploader("Wähle eine Datei", type=["xlsx"])

        if uploaded_file is not None:
            try:
                df = pd.read_excel(uploaded_file, engine="openpyxl")
                # Überprüfen, ob die erforderlichen Spalten vorhanden sind
                if "Vergleichstext Ursprungsversion" not in df.columns or "Text zur Übersetzung / Versionsanpassung" not in df.columns:
                    st.error("Die Datei muss die Spalten 'Vergleichstext Ursprungsversion' und 'Text zur Übersetzung / Versionsanpassung' enthalten.")
                else:
                    st.markdown("### Vorschau der Datei")
                    st.dataframe(df.head(5))

                    # Generiere eine Systemanweisung für die Übersetzung
                    system_message = generate_system_message(
                        source_language,
                        respondent_group,
                        survey_topic,
                        target_language,
                        survey_content,
                        country
                    )

                    # Übersetzungsbutton
                    if st.button("Übersetzen"):
                        # Validiere API-Schlüssel
                        is_valid, message = validate_openai_key(api_key)
                        if not is_valid:
                            st.error(message)
                        elif not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                            st.error("Bitte gib eine gültige E-Mail-Adresse ein.")
                        else:
                            # Eingaben validieren
                            if not country:
                                st.error("Bitte gib das Land ein, in dem die Befragung durchgeführt wird.")
                                return
                            if not respondent_group:
                                st.error("Bitte gib die Befragtengruppe ein.")
                                return
                            if not survey_topic:
                                st.error("Bitte gib das Thema der Befragung ein.")
                                return
                            if not survey_content:
                                st.error("Bitte beschreibe das Ziel und das Thema des Fragebogens.")
                                return

                            # Konvertiere DataFrame in Base64-String
                            excel_buffer = BytesIO()
                            df.to_excel(excel_buffer, index=False, engine="openpyxl")
                            excel_buffer.seek(0)
                            file_data = base64.b64encode(excel_buffer.read()).decode("utf-8")

                            # Schritt 1: Datei zu Supabase hochladen und Job starten
                            with st.spinner("Übersetzungsjob wird gestartet..."):
                                try:
                                    # Format des Dateinamens extrahieren
                                    original_filename = uploaded_file.name

                                    # Daten für die Supabase Edge Function vorbereiten
                                    supabase_url = "https://tyggaqynkmujggfszrvc.supabase.co/functions/v1/start-translation"
                                    
                                    # Die Anfrage an die Supabase-Funktion senden
                                    response = requests.post(
                                        supabase_url,
                                        headers={"Content-Type": "application/json"},
                                        json={
                                            "source_language": source_language,
                                            "target_language": target_language,
                                            "fileData": file_data,  # Base64-String der Excel-Datei
                                            "email": email,
                                            "api_key": api_key,
                                            "model": selected_model,
                                            "batch_size": batch_size,
                                            "country": country,
                                            "respondent_group": respondent_group,
                                            "survey_topic": survey_topic,
                                            "survey_content": survey_content,
                                            "system_message": system_message,
                                            "original_filename": original_filename
                                        }
                                    )
                                    
                                    if response.status_code == 200:
                                        result = response.json()
                                        job_id = result.get("jobId")
                                        st.success(f"Übersetzungsjob erfolgreich gestartet! Du erhältst eine E-Mail, sobald die Übersetzung abgeschlossen ist.")
                                        st.info(f"Job-ID: {job_id}")
                                        st.write("Du kannst den Status deines Jobs in der 'Alle Jobs' App überprüfen.")
                                    else:
                                        st.error(f"Fehler beim Starten des Übersetzungsjobs: {response.text}")
                                except Exception as e:
                                    st.error(f"Ein Fehler ist aufgetreten: {str(e)}")
                                    
            except Exception as e:
                st.error(f"Fehler beim Lesen der Excel-Datei: {e}")

        # Zeige einen Link zur Jobs-App
        st.markdown("---")
        st.write("Du möchtest den Fortschritt deiner Übersetzungen verfolgen? Schau dir die [Alle Jobs App](#) an.")
        if st.button("Zur Jobs-App"):
            select_app("jobs")
            st.rerun()

    # Textbereinigung für die Übersetzung
    def clean_text(text):
        if pd.isna(text):
            return ''
        return str(text).strip()

    # Entscheidungsfindung, ob Tutorial oder Hauptapp gezeigt werden sollte
    if not st.session_state.tutorial_done:
        show_tutorial()
    else:
        main_app()
