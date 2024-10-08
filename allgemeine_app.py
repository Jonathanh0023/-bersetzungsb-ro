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
        "model_selection": "Wähle das GPT-Modell aus, das du verwenden möchtest. Für die beste Leistung empfehlen wir dir GPT-4o.",
        "batch_size": "Hier bestimmst du, wie viele Zeilen auf einmal übersetzt werden. Wir empfehlen dir eine Batchgröße von 10. Achtung: Umso größer die Batchsize umso schneller und günstiger, aber auch umso fehleranfälliger ist die Übersetzung.",
        "language_selection": "Wähle die Ausgangs- und Zielsprache deiner Übersetzung. Sollte deine gewünschte Ausgangs-/ Zielsprache nicht verfügbar sein, melde dich gerne bei Jonathan Heeckt oder Tobias Bucher.",
        "respondent_group": "Diese Felder helfen der KI, den Kontext deiner Übersetzung besser zu verstehen. Gebe die Befragtengruppe und das Thema am besten auf Englisch ein.",
        "survey_content": "Beschreibe hier kurz in 1-2 Sätzen auf Englisch, worum es in deinem Fragebogen geht und was das Ziel deiner Befragung ist, damit die KI bestimmte Begriffe besser übersetzen kann.\n\nz.B. 'The purpose of the questionnaire is to determine whether dentists recommend Listerine as a mouthwash and to understand their reasons for doing so or not.'",
        "file_upload": "Lade die Datei hoch, die übersetzt werden soll. Aktuell werden Dateien ausschließlich im Excel-Format akzeptiert.\nAchtung: Es wird immer die Spalte mit der Überschrift 'Text zur Übersetzung / Versionsanpassung' übersetzt, Spalten mit anderen Überschriften werden nicht übersetzt. Sobald deine Excel-Datei erfolgreich hochgeladen wurde, erscheint deine Excel-Datei als Tabelle im bonsAI Übersetzungsbüro.\n\nDurch das Anklicken des Buttons 'Übersetzen' startet das Tool mit der Übersetzung. Du kannst den Fortschritt live in der angezeigten Tabelle verfolgen. Sobald die Übersetzung abgeschlossen ist, kannst du die Excel-Datei über den Button 'Übersetzung herunterladen' herunterladen.",
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
                    ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
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
                        ["English", "German", "French", "Spanish", "Italian", "Polish"],
                        disabled=True,
                    ),
                    st.selectbox(
                        "Zielsprache",
                        ["German", "English", "French", "Spanish", "Italian", "Polish"],
                        disabled=True,
                    ),
                ),
            },
            {
                "title": "Schritt 5: Befragtengruppe und Thema angeben",
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
                "title": "Schritt 6: Fragebogen",
                "content": "Beschreibe hier kurz in 1-2 Sätzen auf Englisch, worum es in deinem Fragebogen geht und was das Ziel deiner Befragung ist, damit die KI bestimmte Begriffe besser übersetzen kann.\n\nz.B. 'The purpose of the questionnaire is to determine whether dentists recommend Listerine as a mouthwash and to understand their reasons for doing so or not.'\n",
                "widget": lambda: st.text_area(
                    "Beschreibe hier in 1-2 Sätzen das Ziel und das Thema des Fragebogens auf Englisch.",
                    height=100,
                    disabled=True,
                ),
            },
            {
                "title": "Schritt 7: Dateiupload",
                "content": "Lade die Datei hoch, die übersetzt werden soll. Aktuell werden Dateien ausschließlich im Excel-Format akzeptiert.\nAchtung: Es wird immer die Spalte mit der Überschrift 'Text zur Übersetzung / Versionsanpassung' übersetzt, Spalten mit anderen Überschriften werden nicht übersetzt.\n\n",
                "widget": lambda: st.file_uploader(
                    "Wähle eine Datei", type=["xlsx"], disabled=True
                ),
            },
            {
                "title": "Schritt 8: Übersetzung starten",
                "content": "Sobald deine Excel-Datei erfolgreich hochgeladen wurde, erscheint deine Excel-Datei als Tabelle im bonsAI Übersetzungsbüro.\n\nDurch das Anklicken des Buttons 'Übersetzen' startet das Tool mit der Übersetzung. Du kannst den Fortschritt live in der angezeigten Tabelle verfolgen. Sobald die Übersetzung abgeschlossen ist, kannst du die Excel-Datei über den Button 'Übersetzung herunterladen' herunterladen.",
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
    ):
        return (
            f"You are helping a {source_language} programmer translate a questionnaire for {respondent_group} about {survey_topic} into {target_language}. "
            "You ensure that all programming instructions like codes and strings remain unchanged in the translation. "
            "When addressing people personally and for job titles, use the polite form and translate the masculine and feminine form or a neutral term. "
            "Only words within curly braces and country codes should not be translated. If you see only a code, you output only the code. "
            "It is crucial that all programming instructions such as 'Screenout' and 'Quote' are reproduced exactly in the translation. Your response is only the translation or the code of the input. "
            "Here are a few examples of an English-French translation: Original - J&J Customer Journey FR | Translated - J&J Customer Journey FR / Original - !%L-S1%! Please indicate your gender: | Translated - !%L-S1%! Veuillez indiquer votre sexe: / Original - {!%I-progress.txt%!} | Translated - {!%I-progress.txt%!} / Original - &#10148 | Translated - &#10148 / Original - Male | Translated - Homme / Original - Female | Translated - Femme / Original - Other | Translated - autre / Original - Yes | Translated - Oui / Original - Quote | Translated - Quote\n\n"
            "Take your time and think carefully about the right translation, it is essential that everything is translated correctly.\n\n"
            f"For your information, this is what the questionnaire is about:\n{survey_content}"
        )

    # Hauptanwendung
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

        # Auswahl des GPT-Modells
        col1, col2 = st.columns([10, 1])
        with col1:
            st.subheader("Modellauswahl")
        with col2:
            if st.button("ℹ️", key="info_model_selection"):
                toggle_info("show_model_selection_info")
        if st.session_state.get("show_model_selection_info", False):
            st.info(info_texts["model_selection"])
        model_options = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]
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
        ]
        source_language = st.selectbox("Ausgangssprache", language_options, index=0)
        target_language = st.selectbox("Zielsprache", language_options, index=1)

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

        # Dynamisch generierte Systemanweisung
        system_message = generate_system_message(
            source_language,
            respondent_group,
            survey_topic,
            target_language,
            survey_content,
        )

        # Zusammenklappbare Systemanweisung mit Warnhinweis
        with st.expander(
            "Systemanweisung (Achtung: Nur für fortgeschrittene Anwender)"
        ):
            custom_system_message = st.text_area(
                "Gib die Systemanweisung ein", value=system_message, height=200
            )

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
            st.write("Originaltext")

            # Platzhalter für die DataFrame-Aktualisierung
            dataframe_placeholder = st.empty()
            dataframe_placeholder.dataframe(df)

            # Fortschrittsbalken
            progress_bar = st.progress(0)

            # Platzhalter für den Statusanzeigetext
            status_text = st.empty()

            # Button "Übersetzen" hier platzieren
            translate_button = st.button("Übersetzen")
            if translate_button:
                try:
                    if api_key:
                        client = OpenAI(api_key=api_key)
                        previous_translations = ""
                        all_texts = df["Vergleichstext Ursprungsversion"].tolist()
                        translated_lines = []

                        total_batches = (
                            len(all_texts) // batch_size
                            + (1 if len(all_texts) % batch_size > 0 else 0)
                        )

                        # Statusanzeige für Übersetzung
                        status_text.text("Übersetzung wird durchgeführt...")

                        @tenacity.retry(
                            wait=tenacity.wait_exponential(multiplier=1, min=2, max=10),
                            stop=tenacity.stop_after_attempt(5),
                            retry=tenacity.retry_if_exception_type(Exception),
                            reraise=True
                        )
                        def ask_assistant_translation(client, model, messages):
                            response = client.chat.completions.create(
                                model=model,
                                messages=messages,
                            )
                            return response.choices[0].message.content

                        @tenacity.retry(
                            wait=tenacity.wait_exponential(multiplier=1, min=2, max=10),
                            stop=tenacity.stop_after_attempt(5),
                            retry=tenacity.retry_if_exception_type(Exception),
                            reraise=True
                        )
                        def ask_assistant_qm_check(client, model, messages):
                            response = client.chat.completions.create(
                                model=model,
                                messages=messages,
                            )
                            return response.choices[0].message.content.strip()

                        for i in range(0, len(all_texts), batch_size):
                            batch_text = "\n".join(all_texts[i : i + batch_size])

                            # Füge bisherigen Kontext in die Systemnachricht ein
                            extended_system_message = (
                                f"{custom_system_message}\n\n"
                                f"Earlier translations to remain consistent in the translation:\n{previous_translations}"
                            )

                            # Übersetzung mit tenacity
                            translated_batch = ask_assistant_translation(
                                client,
                                selected_model,
                                [
                                    {"role": "system", "content": extended_system_message},
                                    {"role": "user", "content": batch_text},
                                ]
                            )
                            translated_lines.extend(translated_batch.split("\n"))

                            # Aktualisiere den Kontext mit den neuen Übersetzungen
                            previous_translations += "\n".join(
                                [
                                    f"Original: {orig} | Übersetzt: {trans}"
                                    for orig, trans in zip(
                                        all_texts[i : i + batch_size],
                                        translated_batch.split("\n"),
                                    )
                                ]
                            )

                            # Aktualisierung des DataFrames mit dem übersetzten Text
                            for j, line in enumerate(translated_batch.split("\n")):
                                df.at[
                                    i + j, "Text zur Übersetzung / Versionsanpassung"
                                ] = line.strip()

                            # Fortschrittsbalken aktualisieren
                            progress = (i + batch_size) / len(all_texts)
                            progress_bar.progress(min(progress, 1.0))

                            # Aktualisierten DataFrame anzeigen
                            dataframe_placeholder.dataframe(df)

                        # QM-Check für jede Zeile der übersetzten Texte
                        df["QMS"] = ""

                        # Statusanzeige für QM-Check
                        status_text.text("QM-Check wird durchgeführt...")

                        for index, row in df.iterrows():
                            original_text = row["Vergleichstext Ursprungsversion"]
                            translated_text = row["Text zur Übersetzung / Versionsanpassung"]

                            # Zielsprachinformation bleibt direkt verfügbar als target_language

                            # Angepasste Systemanweisung für den QM-Check inklusive Zielsprache
                            qm_check_message = (
                                f"The following translation is part of a questionnaire on the topic of '{survey_topic}' for the group '{respondent_group}'. "
                                f"The original text is in '{source_language}' and has been translated into '{target_language}'. "
                                "Ensure that the translation is accurate, retains the context of the survey, and that all programming codes or programming instructions like 'Screenout' and 'Quote', symbols, country ISO codes like DE, CZ, CH, FR, SP, PL, EN, etc., brands, and special characters are correctly handled. "
                                "Do not alter or misinterpret these elements. "
                                "For example, translations like ISO-Codes 'PL' to 'PL' (English to German), 'Elmex' to 'Elmex' (English to Spanish), 'Yes' to 'Tak' (English to Polish) oder 'No' to 'Nein' (English to German) should be marked as 'True'. "
                                "Programming codes like '&#10148' and html codes within curly braces should remain unchanged and should not be marked as 'False' if they are kept as is. "
                                "If the translation is correct according to these guidelines, respond with 'True'. If there is a mistake or if you think it could be translated better, respond with 'False'."
                            )

                            # QM-Check mit tenacity
                            qm_check_result = ask_assistant_qm_check(
                                client,
                                "gpt-4o",
                                [
                                    {"role": "system", "content": qm_check_message},
                                    {
                                        "role": "user",
                                        "content": (
                                            f"Please check the following translation.\n\n"
                                            f"Original Text: '{original_text}'\n"
                                            f"Translated Text: '{translated_text}'\n\n"
                                            "Respond only with 'True' or 'False' based on the accuracy and consistency of the translation."
                                        ),
                                    },
                                ]
                            )

                            df.at[index, "QMS"] = qm_check_result

                            # Aktualisiere den DataFrame
                            dataframe_placeholder.dataframe(df)

                            # Fortschrittsbalken aktualisieren
                            progress_bar.progress((index + 1) / len(df))

                        # Statusanzeige zurücksetzen
                        status_text.text("Übersetzung und QM-Check abgeschlossen.")

                        # DataFrame für den Download vorbereiten
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                            df.to_excel(writer, index=False)
                        output.seek(0)

                        st.download_button(
                            label="Übersetzung herunterladen",
                            data=output,
                            file_name="translated_output.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    else:
                        st.warning("Bitte gib einen gültigen API-Schlüssel ein.")
                except Exception as e:
                    st.error(f"Ein Fehler ist aufgetreten: {e}")
                    status_text.text("Fehler während der Verarbeitung.")

    # Zeige Hauptanwendung oder Tutorial
    if st.session_state.tutorial_done:
        main_app()
    else:
        show_tutorial()
