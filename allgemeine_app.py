# allgemeine_app.py

import streamlit as st
import pandas as pd
import uuid
import base64
import requests
from io import BytesIO, StringIO
import re
from time import sleep
from utils import select_app, toggle_info
from config import set_page_config, apply_global_css

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
        "email": "Bitte gib deine E-Mail-Adresse ein. Du erhältst das fertige Übersetzungsergebnis dann direkt per E-Mail zugesendet.",
        "model_selection": "Wähle das GPT-Modell aus, das du verwenden möchtest. Für die beste Leistung empfehlen wir dir GPT-4o.",
        "batch_size": "Hier bestimmst du, wie viele Zeilen auf einmal übersetzt werden. Wir empfehlen dir eine Batchgröße von 10. Achtung: Umso größer die Batchsize umso schneller und günstiger, aber auch umso fehleranfälliger ist die Übersetzung.",
        "language_selection": "Wähle die Ausgangs- und Zielsprache deiner Übersetzung. Sollte deine gewünschte Ausgangs-/ Zielsprache nicht verfügbar sein, melde dich gerne bei Jonathan Heeckt oder Tobias Bucher.",
        "respondent_group": "Diese Felder helfen der KI, den Kontext deiner Übersetzung besser zu verstehen. Gebe die Befragtengruppe und das Thema am besten auf Englisch ein.",
        "survey_content": "Beschreibe hier kurz in 1-2 Sätzen auf Englisch, worum es in deinem Fragebogen geht und was das Ziel deiner Befragung ist, damit die KI bestimmte Begriffe besser übersetzen kann.\n\nz.B. 'The purpose of the questionnaire is to determine whether dentists recommend Listerine as a mouthwash and to understand their reasons for doing so or not.'",
        "file_upload": "Lade die Datei hoch, die übersetzt werden soll. Aktuell werden Dateien ausschließlich im Excel-Format akzeptiert.\nAchtung: Es wird immer die Spalte mit der Überschrift 'Text zur Übersetzung / Versionsanpassung' übersetzt, Spalten mit anderen Überschriften werden nicht übersetzt. Sobald deine Excel-Datei erfolgreich hochgeladen wurde, erscheint deine Excel-Datei als Tabelle im bonsAI Übersetzungsbüro.\n\nDurch das Anklicken des Buttons 'Übersetzen' startet das Tool mit der Übersetzung. Du kannst den Fortschritt live in der angezeigten Tabelle verfolgen. Sobald die Übersetzung abgeschlossen ist, kannst du die Excel-Datei über den Button 'Übersetzung herunterladen' herunterladen.",
        "country": "Hier wählst du das Land aus, in dem die Befragung durchgeführt wird. Die Übersetzung wird an die kulturellen Besonderheiten dieses Ziellandes angepasst."
    }

    # Tutorial anzeigen
    def show_tutorial():
        tutorial_steps = [
            {
                "title": "Willkommen im Allgemeinen bonsAI Übersetzungsbüro!",
                "content": (
                    "Schön, dass du da bist! Lass uns zusammen herausfinden, wie alles funktioniert. "
                    "Klicke auf 'Weiter', um mit dem Tutorial zu starten.\n\n"
                    "Falls du der Meinung bist, dass du dich schon bestens auskennst, dann klicke auf "
                    "'Tutorial überspringen'.\n"
                ),
                "widget": lambda: None,
            },
            {
                "title": "Schritt 1: E-Mail-Adresse",
                "content": (
                    "Gib bitte eine gültige E-Mail-Adresse an, damit du das fertige Übersetzungsergebnis "
                    "zugeschickt bekommst.\n"
                ),
                "widget": lambda: st.text_input(
                    "Deine E-Mail-Adresse",
                    disabled=True,
                ),
            },
            {
                "title": "Schritt 2: API-Schlüssel",
                "content": (
                    "Hier trägst du deinen OpenAI API-Schlüssel ein. Ohne diesen können wir leider "
                    "nicht loslegen. Den aktuellen API-Schlüssel erhältst du von Jonathan Heeckt oder "
                    "Tobias Bucher.\n"
                ),
                "widget": lambda: st.text_input(
                    "Gib deinen OpenAI API-Schlüssel ein",
                    type="password",
                    disabled=True,
                ),
            },
            {
                "title": "Schritt 3: Modellauswahl",
                "content": (
                    "Wähle das GPT-Modell aus, das du verwenden möchtest. Für die beste Leistung "
                    "empfehlen wir dir GPT-4o.\n"
                ),
                "widget": lambda: st.selectbox(
                    "Wähle das Modell",
                    ["gpt-4o", "gpt-4o-mini", "gpt-o1-mini", "o3-mini"],
                    disabled=True,
                ),
            },
            {
                "title": "Schritt 4: Batchgröße festlegen",
                "content": (
                    "Hier bestimmst du, wie viele Zeilen auf einmal übersetzt werden. Wir empfehlen "
                    "dir eine Batchgröße von 10.\n\nAchtung: Umso größer die Batchgröße, umso schneller "
                    "und günstiger, aber auch umso fehleranfälliger ist die Übersetzung.\n"
                ),
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
                "title": "Schritt 5: Spracheinstellungen",
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
                "title": "Schritt 6: Zielland",
                "content": (
                    "Wähle das Land aus, in dem die Befragung durchgeführt wird. "
                    "Die Übersetzung wird an die kulturellen Gegebenheiten dieses Ziellandes angepasst.\n"
                ),
                "widget": lambda: st.text_input(
                    "Land, in dem die Befragung durchgeführt wird, z.B. 'Germany'",
                    disabled=True,
                ),
            },
            {
                "title": "Schritt 7: Befragtengruppe und Thema angeben",
                "content": (
                    "Diese Felder helfen der KI, den Kontext deiner Übersetzung besser zu verstehen. "
                    "Gib die Befragtengruppe und das Thema am besten auf Englisch ein.\n"
                ),
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
                "title": "Schritt 8: Fragebogen",
                "content": (
                    "Beschreibe hier kurz in 1-2 Sätzen auf Englisch, worum es in deinem Fragebogen "
                    "geht und was das Ziel deiner Befragung ist, damit die KI bestimmte Begriffe "
                    "besser übersetzen kann.\n\n"
                    "z.B. 'The purpose of the questionnaire is to determine whether dentists recommend "
                    "Listerine as a mouthwash and to understand their reasons for doing so or not.'\n"
                ),
                "widget": lambda: st.text_area(
                    "Beschreibe hier in 1-2 Sätzen das Ziel und das Thema des Fragebogens auf Englisch.",
                    height=100,
                    disabled=True,
                ),
            },
            {
                "title": "Schritt 9: Dateiupload",
                "content": (
                    "Lade die Datei hoch, die übersetzt werden soll. Aktuell werden Dateien "
                    "ausschließlich im Excel-Format akzeptiert.\nAchtung: Es wird immer die Spalte "
                    "mit der Überschrift 'Text zur Übersetzung / Versionsanpassung' übersetzt, "
                    "Spalten mit anderen Überschriften werden nicht übersetzt.\n\n"
                ),
                "widget": lambda: st.file_uploader(
                    "Wähle eine Datei", type=["xlsx"], disabled=True
                ),
            },
            {
                "title": "Schritt 10: Übersetzung starten",
                "content": (
                    "Sobald deine Excel-Datei erfolgreich hochgeladen wurde, erscheint deine Excel-Datei "
                    "als Tabelle im bonsAI Übersetzungsbüro.\n\nDurch das Anklicken des Buttons "
                    "'Übersetzen' startet das Tool mit der Übersetzung. Du kannst den Fortschritt "
                    "live in der angezeigten Tabelle verfolgen. Sobald die Übersetzung abgeschlossen ist, "
                    "kannst du die Excel-Datei über den Button 'Übersetzung herunterladen' "
                    "herunterladen."
                ),
                "widget": lambda: None,
            },
            {
                "title": "Let's Go 🚀",
                "content": (
                    "Du hast das Tutorial erfolgreich abgeschlossen. "
                    "Nun viel Spaß beim Verwenden des bonsAI Übersetzungsbüros!\n"
                ),
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

    def main_app():
        def toggle_info(key):
            if key not in st.session_state:
                st.session_state[key] = False
            st.session_state[key] = not st.session_state[key]

        # Eingabe für E-Mail-Adresse (verpflichtend)
        col_email, col_info_email = st.columns([10, 1])
        with col_email:
            st.subheader("E-Mail-Adresse (Pflichtfeld)")
        with col_info_email:
            if st.button("ℹ️", key="info_email"):
                toggle_info("show_email_info")
        if st.session_state.get("show_email_info", False):
            st.info(info_texts["email"])
        email = st.text_input("Bitte gib deine E-Mail-Adresse ein, um das Ergebnis zu erhalten.")

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
        batch_size = st.slider("Batchgröße", min_value=2, max_value=50, value=10, step=2)

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

        # Zielland
        col1, col2 = st.columns([10, 1])
        with col1:
            st.subheader("Zielland")
        with col2:
            if st.button("ℹ️", key="info_country"):
                toggle_info("show_country_info")
        if st.session_state.get("show_country_info", False):
            st.info(info_texts["country"])
        country = st.text_input("Land, in dem die Befragung durchgeführt wird (z.B. 'Germany'): ")

        # Befragtengruppe und Thema
        col1, col2 = st.columns([10, 1])
        with col1:
            st.subheader("Befragtengruppe und Thema")
        with col2:
            if st.button("ℹ️", key="info_respondent_group"):
                toggle_info("show_respondent_group_info")
        if st.session_state.get("show_respondent_group_info", False):
            st.info(info_texts["respondent_group"])
        respondent_group = st.text_input("Befragtengruppe auf Englisch, z.B. 'Dentists'")
        survey_topic = st.text_input("Thema der Befragung auf Englisch, z.B. 'dental hygiene'")

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

        # Systemanweisung (wird später in Zapier gebraucht)
        def generate_system_message(
            source_language,
            respondent_group,
            survey_topic,
            target_language,
            survey_content,
            country
        ):
            return (
                f"You are assisting an English-speaking programmer in translating a questionnaire "
                f"from {source_language} into {target_language}. "
                f"The topic of the survey is '{survey_topic}'. Your primary goal is to ensure that "
                "the translation sounds natural and fluent for native speakers while preserving "
                "all technical and programming elements accurately.\n\n"
                "Programming Instructions: All programming instructions, including codes and strings "
                "(e.g., 'Screenout', 'Quote'), must remain exactly as they are in the translation. "
                "Rogator-specific syntax, which always begins with !% and ends with %!, represents "
                "dynamic placeholders and must be retained unchanged.\n\n"
                "Curly Brace Elements: Retain all elements within curly braces and any country codes "
                "without translating them.\n\n"
                "Form of Address: Use the polite form ('Sie') for direct addresses. For job titles "
                "or personal forms of address, ensure gender inclusivity by using both masculine "
                "and feminine forms or a gender-neutral term if appropriate.\n\n"
                "Content Translation: Translate the meaning rather than word-for-word. Ensure the "
                "translation is fluent and natural for native speakers, without changing the original intent. "
                "For example: If the sentence already uses a polite form of address, such as "
                "'Veuillez' or 'Pourriez-vous' in French, it is not necessary to include phrases like "
                "'s'il vous plaît'. The German phrase ‘Würden Sie uns bitte’ would be "
                "translated into French as ‘Veuillez nous’ and the ‘s'il vous plaît’ can be omitted.\n\n"
                "Language-Specific Conventions: Pay special attention to conventional sentence "
                "structures and placement of polite expressions in the target language. "
                f"Ensure a consistent style for respondents in {country}.\n\n"
                "Attention to detail: Take the necessary time to carefully consider each term. "
                "It is critical to maintain accuracy, modified sentence structure, and cultural "
                f"appropriateness in {country} in the translated text."
            )

        system_message = generate_system_message(
            source_language,
            respondent_group,
            survey_topic,
            target_language,
            survey_content,
            country
        )

        with st.expander("Systemanweisung (Achtung: Nur für fortgeschrittene Anwender)"):
            custom_system_message = st.text_area("Gib die Systemanweisung ein", value=system_message, height=200)

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

        st.write("---")

        # Button "Übersetzen" – hier: Umwandlung in CSV + Versand an Zapier
        if uploaded_file is not None:
            df = pd.read_excel(uploaded_file)
            if "Vergleichstext Ursprungsversion" not in df.columns or "Text zur Übersetzung / Versionsanpassung" not in df.columns:
                st.error(
                    "Die hochgeladene Excel-Datei enthält nicht die erforderlichen "
                    "Spalten 'Vergleichstext Ursprungsversion' und/oder "
                    "'Text zur Übersetzung / Versionsanpassung'. "
                    "Bitte lade eine gültige Datei hoch."
                )
                return

            st.write("Vorschau der hochgeladenen Excel-Datei:")
            st.dataframe(df)

            # Hier könntest du noch lokal etwas bearbeiten, wenn gewünscht
            # z. B. df["Neue Spalte"] = ...

            translate_button = st.button("Übersetzen (CSV an Zapier)")
            if translate_button:
                # Prüfen, ob E-Mail ausgefüllt wurde
                if not email.strip():
                    st.error("Bitte gib eine gültige E-Mail-Adresse ein, bevor du fortfährst.")
                    return

                # Erzeuge Job-ID
                job_id = str(uuid.uuid4())

                # DataFrame -> CSV
                csv_buffer = StringIO()
                df.to_csv(csv_buffer, index=False, encoding="utf-8")
                csv_data = csv_buffer.getvalue()

                # CSV Base64-kodieren
                csv_base64 = base64.b64encode(csv_data.encode("utf-8")).decode("utf-8")

                # Payload für Zapier
                payload = {
                    "job_id": job_id,
                    "email": email,
                    "api_key": api_key,
                    "selected_model": selected_model,
                    "system_message": custom_system_message,
                    "file_base64": csv_base64,
                    "batch_size": batch_size,
                    "source_language": source_language,
                    "target_language": target_language,
                    "country": country,
                    "respondent_group": respondent_group,
                    "survey_topic": survey_topic,
                    "survey_content": survey_content
                }

                zapier_webhook_url = "https://hooks.zapier.com/hooks/catch/22221288/2c8vwqv/"

                try:
                    response = requests.post(zapier_webhook_url, json=payload, timeout=15)
                    if response.status_code == 200:
                        st.success(
                            f"Anfrage an Zapier gesendet. "
                            f"Job-ID: {job_id}.\n\n"
                            f"Du erhältst das Ergebnis als CSV an die angegebene E-Mail-Adresse, "
                            f"sobald die Übersetzung (in Zapier) abgeschlossen ist."
                        )
                    else:
                        st.error(f"Fehler beim Senden an Zapier (Status {response.status_code}):\n{response.text}")
                except Exception as e:
                    st.error(f"Fehler bei der Kommunikation mit Zapier: {e}")

        else:
            st.info("Bitte lade eine Excel-Datei hoch, um fortzufahren.")

    # Zeige Hauptanwendung oder Tutorial
    if st.session_state.tutorial_done:
        main_app()
    else:
        show_tutorial()


