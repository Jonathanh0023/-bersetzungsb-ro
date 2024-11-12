# key_account_app.py
import streamlit as st
import pandas as pd
from openai import OpenAI
from io import BytesIO
import re
from time import sleep
import tenacity
from utils import select_app, toggle_info
from config import set_page_config, apply_global_css

def generate_system_message(source_language, target_language, survey_topic, survey_content):
    return (
        f"You are assisting an English-speaking programmer in translating a questionnaire from {source_language} into {target_language}. "
        f"The topic of the survey is '{survey_topic}'. Your primary goal is to ensure that the translation sounds natural and fluent for native speakers while preserving all technical and programming elements accurately.\n\n"
        "Programming Instructions: All programming instructions, including codes and strings (e.g., 'Screenout', 'Quote'), must remain exactly as they are in the translation. "
        "Rogator-specific syntax, which always begins with !% and ends with %!, represents dynamic placeholders and must be retained unchanged, as these will later be populated by the software.\n\n"
        "Curly Brace Elements: Retain all elements within curly braces and any country codes without translating them.\n\n"
        "Form of Address: Use the polite form ('Sie') for direct addresses. For job titles or personal forms of address, ensure gender inclusivity by using both masculine and feminine forms or a gender-neutral term if appropriate.\n\n"
        "Content Translation: Translate the meaning rather than word-for-word. Ensure the translation is fluent and natural for native speakers, without changing the original intent.\n\n"
        "Consistency in Style: Ensure a consistent and natural style throughout the translation, adapting the language to suit {target_language} linguistic nuances. Your response should include only the translated text. "
        "If the input is a code or a placeholder, reproduce it exactly without translation.\n\n"
        "Attention to Detail: Take the necessary time to carefully consider each term. It is critical to maintain both accuracy and cultural appropriateness for the {target_language} audience.\n\n"
        f"For reference, here is background information on the questionnaire's purpose and target audience:\n{survey_content}"
    )

def key_account_app():
    # Einstellungen für die Key Account App
    col1, col2 = st.columns([8, 2])
    with col1:
        st.markdown(f"<h1>Key Account Übersetzungsbüro 🌍</h1>", unsafe_allow_html=True)
    with col2:
        st.markdown(
            "<div style='display: flex; justify-content: flex-end;'>",
            unsafe_allow_html=True
        )
        st.button(
            "Home", on_click=lambda: select_app(None), key="home_button_key_account"
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # Session-State initialisieren
    if "api_key" not in st.session_state:
        st.session_state.api_key = None
    if "translation_running" not in st.session_state:
        st.session_state.translation_running = False
    if "translation_stopped" not in st.session_state:
        st.session_state.translation_stopped = False
    if "uploaded_file_info" not in st.session_state:
        st.session_state.uploaded_file_info = None
    if "df" not in st.session_state:
        st.session_state.df = None

    # Callback-Funktion zum Aktualisieren des API-Schlüssels
    def set_api_key():
        st.session_state.api_key = st.session_state.api_key_input

    # Callback-Funktionen für Übersetzung starten und stoppen
    def start_translation():
        st.session_state.translation_running = True

    def stop_translation():
        st.session_state.translation_running = False
        st.session_state.translation_stopped = True  # Übersetzung wurde gestoppt
        st.info("Übersetzung wurde abgebrochen.")

    def api_key_input():
        st.write("Bitte gib deinen OpenAI API-Schlüssel ein, um fortzufahren.")

        with st.form(key="api_key_form"):
            st.text_input(
                "🔑 OpenAI API-Schlüssel", type="password", key="api_key_input"
            )
            st.form_submit_button(label="Weiter", on_click=set_api_key)

        if st.session_state.api_key:
            main_app_key()  # Wechsle zur Hauptanwendung

    @tenacity.retry(
        wait=tenacity.wait_exponential(multiplier=1, min=2, max=10),
        stop=tenacity.stop_after_attempt(5),
        retry=tenacity.retry_if_exception_type(Exception),
        reraise=True
    )
    def ask_assistant(client, thread, message_text, assistant_id):
        try:
            client.beta.threads.messages.create(
                thread_id=thread.id, role="user", content=message_text
            )
            run = client.beta.threads.runs.create(
                thread_id=thread.id, assistant_id=assistant_id
            )

            while run.status != "completed":
                sleep(2)
                run = client.beta.threads.runs.retrieve(
                    thread_id=thread.id, run_id=run.id
                )

            messages = client.beta.threads.messages.list(thread.id)
            return messages.data[0].content[0].text.value.strip()
        except Exception as e:
            st.error(f"Ein Fehler ist aufgetreten: {e}")
            raise e  # Fehler erneut werfen, um retry auszulösen

    def clean_translation(original_text, translated_text):
        translated_text = re.sub(r"【\d+:\d+†[^】]+】", "", translated_text)
        translated_text = translated_text.replace('"', "")
        if not original_text.endswith(".") and translated_text.endswith("."):
            translated_text = translated_text.rstrip(".")
        return translated_text

    def main_app_key():
        # Seitenleiste für Einstellungen
        with st.sidebar:
            st.subheader("⚙️ Einstellungen")

            # API-Schlüssel bearbeiten
            api_key_value = st.text_input(
                "🔑 OpenAI API-Schlüssel",
                type="password",
                value=st.session_state.api_key,
            )
            if api_key_value != st.session_state.api_key:
                st.session_state.api_key = api_key_value

            # Überprüfen, ob ein API-Schlüssel vorhanden ist
            if not st.session_state.api_key:
                st.warning("Bitte gib einen gültigen API-Schlüssel ein.")
                st.stop()

            # Zielsprache auswählen
            target_language = st.selectbox(
                "🌐 Zielsprache auswählen",
                ["German", "English", "French", "Spanish", "Italian", "Polish"],
            )

            # Assistenten-Auswahl
            assistant_options = {
                "Henkel Übersetzer 2024": "asst_za7m9htCcjl6pjietq1hi0Gd",
                # Weitere Assistenten können hier hinzugefügt werden
                "Other Assistant 1": "asst_example_1",
                "Other Assistant 2": "asst_example_2",
            }
            selected_assistant_name = st.selectbox(
                "🤖 Wähle einen Assistenten", list(assistant_options.keys())
            )
            selected_assistant_id = assistant_options[selected_assistant_name]

        # OpenAI-Client initialisieren
        client = OpenAI(api_key=st.session_state.api_key)

        # Datei hochladen
        uploaded_file = st.file_uploader(
            "📄 Lade deine Excel-Datei hoch", type="xlsx"
        )

        if uploaded_file is not None:
            current_file_info = (uploaded_file.name, uploaded_file.size)
            if st.session_state.uploaded_file_info != current_file_info:
                # Neue Datei hochgeladen oder Datei geändert
                st.session_state.uploaded_file_info = current_file_info
                st.session_state.df = None  # DataFrame zurücksetzen
                st.session_state.translation_stopped = False

            if st.session_state.df is None:
                try:
                    df = pd.read_excel(uploaded_file, engine="openpyxl")
                except Exception as e:
                    st.error(f"Fehler beim Lesen der Excel-Datei: {e}")
                    st.stop()

                # Überprüfen, ob die erforderlichen Spalten vorhanden sind
                required_columns = [
                    "Vergleichstext Ursprungsversion",
                    "Text zur Übersetzung / Versionsanpassung",
                ]
                if not all(col in df.columns for col in required_columns):
                    st.error(
                        f"Die hochgeladene Datei muss die folgenden Spalten enthalten: {', '.join(required_columns)}"
                    )
                    st.stop()

                # Sicherstellen, dass die zu übersetzende Spalte als Text behandelt wird
                df["Text zur Übersetzung / Versionsanpassung"] = df[
                    "Text zur Übersetzung / Versionsanpassung"
                ].astype(str)

                # Speichern des DataFrames im Session-State
                st.session_state.df = df
            else:
                df = st.session_state.df

            # Zeige den DataFrame an
            st.write("### 📝 Datenvorschau:")
            dataframe_placeholder = st.empty()
            dataframe_placeholder.dataframe(df)

            # Platzhalter für Meldungen und Fortschrittsbalken
            message_placeholder = st.empty()
            progress_bar = st.empty()

            # Platzhalter für die Buttons
            button_placeholder = st.empty()

            with button_placeholder.container():
                # Buttons zum Starten und Stoppen der Übersetzung
                col1, col2 = st.columns(2)
                with col1:
                    st.button(
                        "🚀 Übersetzung starten",
                        disabled=st.session_state.translation_running,
                        on_click=start_translation,
                    )
                # Den "Übersetzung abbrechen" Button nur anzeigen, wenn die Übersetzung läuft
                if st.session_state.translation_running:
                    with col2:
                        st.button("🛑 Übersetzung abbrechen", on_click=stop_translation)

            if st.session_state.translation_running:
                # Übersetzung durchführen
                progress_bar.progress(0)
                total_rows = len(df)

                # Thread für die Übersetzungen erstellen
                thread = client.beta.threads.create()

                try:
                    for index, row in df.iterrows():
                        if not st.session_state.translation_running:
                            message_placeholder.info("Übersetzung wurde abgebrochen.")
                            break
                        original_text = row["Vergleichstext Ursprungsversion"]

                        # Nur übersetzen, wenn "Text zur Übersetzung / Versionsanpassung" leer ist
                        translation_text = row["Text zur Übersetzung / Versionsanpassung"]
                        if translation_text.strip().lower() == "nan" or translation_text.strip() == "":
                            if pd.notna(original_text):
                                # Übersetzung durchführen mit tenacity
                                prompt = f"Translate the following Text into {target_language} and make sure that you consider the programming code or HTML string in the translated version. Your answer is only the correct translated version in {target_language} from your knowledge database with the programming code or HTML string: {original_text}"
                                translated_text = ask_assistant(
                                    client, thread, prompt, selected_assistant_id
                                )
                                clean_line = clean_translation(
                                    original_text, translated_text
                                )
                                df.at[
                                    index, "Text zur Übersetzung / Versionsanpassung"
                                ] = clean_line.strip()

                                # Aktualisierung des DataFrames
                                st.session_state.df = df
                                dataframe_placeholder.dataframe(df)

                        # Fortschritt aktualisieren
                        progress_bar.progress((index + 1) / total_rows)

                    if st.session_state.translation_running:
                        message_placeholder.success("Übersetzung abgeschlossen.")
                    st.session_state.translation_running = False
                except Exception as e:
                    message_placeholder.error(f"Ein Fehler ist aufgetreten: {e}")
                    st.session_state.translation_running = False
                finally:
                    progress_bar.empty()
                    st.session_state.translation_stopped = True
                    # Button-Placeholder leeren
                    button_placeholder.empty()

            # Excel-Datei für den Download vorbereiten
            if st.session_state.translation_stopped:
                output = BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    st.session_state.df.to_excel(writer, index=False)
                output.seek(0)

                st.download_button(
                    label="💾 Übersetzung herunterladen",
                    data=output,
                    file_name="translated_output.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                st.session_state.translation_stopped = False  # Zurücksetzen

        else:
            st.info("Bitte lade eine Excel-Datei hoch, um fortzufahren.")
            # Entferne DataFrame aus Session-State, wenn keine Datei hochgeladen ist
            if "df" in st.session_state:
                del st.session_state.df

    # Steuerung, welche Seite angezeigt wird
    if st.session_state.api_key:
        main_app_key()  # Zeigt die Hauptanwendung an
    else:
        api_key_input()  # Zeigt die Eingabeaufforderung für den API-Schlüssel an
