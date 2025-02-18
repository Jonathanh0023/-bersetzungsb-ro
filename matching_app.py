import streamlit as st
import pandas as pd
import re
import openai
from io import BytesIO
from config import set_page_config, apply_global_css
from utils import select_app, toggle_info
from github import Github
import base64
import json
import os

def matching_app():
        # Einstellungen für die allgemeine App
    col1, col2 = st.columns([8, 2])
    with col1:
        st.markdown(f"<h1>Matching Übersetzungsbüro 🕵️‍♂️</h1>", unsafe_allow_html=True)
    with col2:
        st.markdown(
            "<div style='display: flex; justify-content: flex-end;'>",
            unsafe_allow_html=True
        )
        st.button("Home", on_click=lambda: select_app(None), key="home_button_allgemein")
        st.markdown("</div>", unsafe_allow_html=True)

    # Funktion zur Bereinigung des Textes für das Matching
    def clean_text_for_matching(text):
        if pd.isna(text):
            return ''
        text = str(text)
        clean_line = re.sub(r'!%.*?%!', '', text)
        clean_line = re.sub(r'{!%.*?%!}', '', clean_line)
        clean_line = clean_line.strip()
        return clean_line

    # Funktion zur Bereinigung des Textes mit Platzhaltern
    def clean_text_with_placeholders(text):
        if pd.isna(text):
            return '', []
        text = str(text)
        placeholders = []
        def replace_with_placeholder(match):
            start_pos = match.start()
            placeholders.append((match.group(0), start_pos))
            return ''
        clean_line = re.sub(r'!%.*?%!', replace_with_placeholder, text)
        clean_line = re.sub(r'{!%.*?%!}', replace_with_placeholder, clean_line)
        clean_line = clean_line.strip()
        return clean_line, placeholders

    # Funktion zur Wiederherstellung des Textes mit Platzhaltern
    def restore_text(cleaned_text, placeholders):
        cleaned_text = str(cleaned_text)
        placeholders.sort(key=lambda x: x[1])
        for placeholder, position in reversed(placeholders):
            cleaned_text = cleaned_text[:position] + placeholder + cleaned_text[position:]
        return cleaned_text

    # Funktion zur Überprüfung, ob der Text immer dupliziert werden soll
    def should_always_duplicate(text):
        special_cases = [
            r'\{!%I-progress.txt%!}',
            r'<div style="display:none;">&nbsp;</div>',
            r'&nbsp;years'
        ]
        for case in special_cases:
            if re.search(case, text):
                return True
        if text.startswith('<') and text.endswith('>'):
            return True
        if text.startswith('!%') and text.endswith('%!'):
            return True
        if text.startswith('!') and text.endswith('!'):
            return True
        if text.startswith('ZC:'):
            return True
        if re.fullmatch(r'\d+(\.\d+)?', text):
            return True
        if text.strip().lower() in {"result:", "kommentar", "general remarks", "allgemeine bemerkungen", "screenout", "quotafull", "&#10148S"}:
            return True
        if re.search(r'Brand\s+\d+', text):
            return True
        if text.startswith('Neue Antwort'):
            return True
        return False

    # Funktion zur Generierung der Systemnachricht für GPT
    def generate_system_message(source_language, respondent_group, survey_topic, target_language, survey_content):
        return (
            f"You are assisting an English-speaking programmer in translating a questionnaire from {source_language} into {target_language}. "
            f"The topic of the survey is '{survey_topic}'. Your primary goal is to ensure that the translation sounds natural and fluent for native speakers while preserving all technical and programming elements accurately.\n\n"
            "Programming Instructions: All programming instructions, including codes and strings (e.g., 'Screenout', 'Quote'), must remain exactly as they are in the translation. "
            "Rogator-specific syntax, which always begins with !% and ends with %!, represents dynamic placeholders and must be retained unchanged, as these will later be populated by the software.\n\n"
            "Curly Brace Elements: Retain all elements within curly braces and any country codes without translating them.\n\n"
            "Form of Address: Use the polite form ('Sie') for direct addresses. For job titles or personal forms of address, ensure gender inclusivity by using both masculine and feminine forms or a gender-neutral term if appropriate.\n\n"
            "Content Translation: Translate the meaning rather than word-for-word. Ensure the translation is fluent and natural for native speakers, without changing the original intent.\n\n"
            f"Consistency in Style: Ensure a consistent and natural style throughout the translation, adapting the language to suit {target_language} linguistic nuances. Your response should include only the translated text. "
            "If the input is a code or a placeholder, reproduce it exactly without translation.\n\n"
            f"Attention to Detail: Take the necessary time to carefully consider each term. It is critical to maintain both accuracy and cultural appropriateness for the {target_language} audience.\n\n"
            f"For reference, here is background information on the questionnaire's purpose and target audience:\n{survey_content}"
        )

    # Tutorial und Info-Texte
    info_texts = {
        "api_key": "Hier trägst du deinen OpenAI API-Schlüssel ein. Ohne diesen können wir leider nicht loslegen. Den aktuellen API-Schlüssel erhältst du von Jonathan Heeckt oder Tobias Bucher.",
        "model_selection": "Wähle das GPT-Modell aus, das du verwenden möchtest. Für die beste Leistung empfehlen wir dir GPT-4o.",
        "batch_size": "Hier bestimmst du, wie viele Zeilen auf einmal übersetzt werden. Wir empfehlen dir eine Batchgröße von 10. Achtung: Umso größer die Batchsize umso schneller und günstiger, aber auch umso fehleranfälliger ist die Übersetzung.",
        "language_selection": "Wähle die Ausgangs- und Zielsprache deiner Übersetzung. Sollte deine gewünschte Ausgangs-/ Zielsprache nicht verfügbar sein, melde dich gerne bei Jonathan Heeckt oder Tobias Bucher.",
        "respondent_group": "Diese Felder helfen der KI, den Kontext deiner Übersetzung besser zu verstehen. Gib die Befragtengruppe und das Thema am besten auf Englisch ein.",
        "survey_content": "Beschreibe hier kurz in 1-2 Sätzen auf Englisch, worum es in deinem Fragebogen geht und was das Ziel deiner Befragung ist, damit die KI bestimmte Begriffe besser übersetzen kann.\n\n z.B. 'The purpose of the questionnaire is to determine whether dentists recommend Listerine as a mouthwash and to understand their reasons for doing so or not.'",
        "file_upload": "Lade die Datei hoch, die übersetzt werden soll. Aktuell werden Dateien ausschließlich im Excelformat akzeptiert.\n Achtung: Es wird immer die Spalte mit der Überschrift „Text zur Übersetzung / Versionsanpassung“ übersetzt, Spalten mit anderen Überschriften werden nicht übersetzt. Sobald deine Exceldatei erfolgreich hochgeladen wurde, erscheint deine Exceldatei als Tabelle im BonsAI Übersetzungsbüro.\n\n Durch das Anklicken des Buttons „Übersetzen“ startet das Tool mit der Übersetzung. Du kannst den Fortschritt live in der angezeigten Tabelle verfolgen. Sobald die Übersetzung abgeschlossen ist, kannst du die Exceldatei über den Button „Übersetzung herunterladen“ herunterladen."
    }

    # Session-States initialisieren
    if 'tutorial_done' not in st.session_state:
        st.session_state.tutorial_done = False  # Tutorial zu Beginn anzeigen
    if 'tutorial_step' not in st.session_state:
        st.session_state.tutorial_step = 0
    if 'template_loaded' not in st.session_state:
        st.session_state.template_loaded = False
    if 'translation_file' not in st.session_state:
        st.session_state.translation_file = None

    def reset_tutorial():
        st.session_state.tutorial_done = False
        st.session_state.tutorial_step = 0

    def next_step():
        st.session_state.tutorial_step += 1
        st.rerun()  # Aktualisiert die Seite sofort

    def skip_tutorial():
        st.session_state.tutorial_done = True
        st.session_state.tutorial_step = 0
        st.rerun()  # Diese Zeile sorgt dafür, dass die Hauptanwendung sofort geladen wird

    # Funktion zum Umschalten der Info-Popups
    def toggle_info(key):
        if key not in st.session_state:
            st.session_state[key] = False
        st.session_state[key] = not st.session_state[key]

    # Funktion zum Highlighten der Zellen
    def highlight_cells(row):
        if row['Quelle'] == 'Match':
            return ['background-color: transparent'] * len(row)  # Hellgrün
        elif row['Quelle'] == 'GPT':
            return ['background-color: transparent'] * len(row)  # Hellorange
        else:
            return [''] * len(row)

    def show_tutorial():
        st.title("Tutorial")
        tutorial_steps = [
            {"title": "Willkommen im bonsAI Matching-Übersetzungsbüro! 📚", 
            "content": "Schön, dass du da bist! Lass uns zusammen herausfinden, wie alles funktioniert. Klicke auf „Weiter“, um mit dem Tutorial zu starten.\n\n Falls du der Meinung bist, dass du dich schon bestens auskennst, dann klicke auf „Tutorial überspringen“.\n", 
            "widget": lambda: None},
            {"title": "Schritt 1: API-Schlüssel", 
            "content": "Hier trägst du deinen OpenAI API-Schlüssel ein. Ohne diesen können wir leider nicht loslegen. Den aktuellen API-Schlüssel erhältst du von Jonathan Heeckt oder Tobias Bucher.\n", 
            "widget": lambda: st.text_input("Gib deinen OpenAI API-Schlüssel ein", type="password", disabled=True)},
            {"title": "Schritt 2: Modellauswahl", 
            "content": "Wähle das GPT-Modell aus, das du verwenden möchtest. Für die beste Leistung empfehlen wir dir GPT-4o.\n", 
            "widget": lambda: st.selectbox("Wähle das Modell", ["gpt-4o", "gpt-4o-mini", "o3-mini"], disabled=True)},
            {"title": "Schritt 3: Batchgröße festlegen", 
            "content": "Hier bestimmst du, wie viele Zeilen auf einmal übersetzt werden. Wir empfehlen dir eine Batchgröße von 10.\n\n Achtung: Umso größer die Batchsize umso schneller und günstiger, aber auch umso fehleranfälliger ist die Übersetzung.\n", 
            "widget": lambda: st.slider("Batchgröße", min_value=2, max_value=50, value=10, step=2, disabled=True)},
            {"title": "Schritt 4: Spracheinstellungen", 
            "content": "Wähle die Ausgangs- und Zielsprache deiner Übersetzung.\n", 
            "widget": lambda: (st.selectbox("Ausgangssprache", ["English", "German", "French", "Spanish", "Italian", "Polish", "Dutch", "Portuguese", "Russian", "Turkish", "Arabic", "Chinese", "Japanese", "Korean", "Vietnamese"], disabled=True), 
                            st.selectbox("Zielsprache", ["German", "English", "French", "Spanish", "Italian", "Polish", "Dutch", "Portuguese", "Russian", "Turkish", "Arabic", "Chinese", "Japanese", "Korean", "Vietnamese"], disabled=True))},
            {"title": "Schritt 5: Befragtengruppe und Thema der Befragung", 
            "content": "Diese Felder helfen der KI, den Kontext deiner Übersetzung besser zu verstehen. Gib die Befragtengruppe und das Thema am besten auf Englisch ein.\n", 
            "widget": lambda: (st.text_input("Befragtengruppe auf Englisch eingeben, z.B. 'Dentists'", disabled=True), 
                            st.text_input("Thema der Befragung auf Englisch eingeben, z.B. 'Dental hygiene'", disabled=True))},
            {"title": "Schritt 6: Fragebogen", 
            "content": "Beschreibe hier kurz in 1-2 Sätzen auf Englisch, worum es in deinem Fragebogen geht und was das Ziel deiner Befragung ist, damit die KI bestimmte Begriffe besser übersetzen kann.\n\n z.B. 'The purpose of the questionnaire is to determine whether dentists recommend Listerine as a mouthwash and to understand their reasons for doing so or not.'\n", 
            "widget": lambda: st.text_area("Beschreibe hier in 1-2 Sätzen das Ziel und das Thema des Fragebogens auf Englisch.", height=100, disabled=True)},
            {"title": "Schritt 7: Dateiupload", 
            "content": "Lade die Datei hoch, die übersetzt werden soll. Aktuell werden Dateien ausschließlich im Excelformat akzeptiert.\n Achtung: Es wird immer die Spalte mit der Überschrift „Text zur Übersetzung / Versionsanpassung“ übersetzt, Spalten mit anderen ������berschriften werden nicht übersetzt.\n\n", 
            "widget": lambda: st.file_uploader("Wähle eine Datei", type=["xlsx"])},
            {"title": "Schritt 8: Matching der Texte", 
            "content": "Sobald deine Rogator-Datei und Übersetzungsdatei hochgeladen sind, wird ein Matching durchgeführt. Dies bedeutet:\n\n- Texte aus der Spalte „Vergleichstext Ursprungsversion“ in der Rogator-Datei werden mit den englischen Texten in der Übersetzungsdatei abgeglichen.\n- Wenn ein übereinstimmender Text gefunden wird, wird die entsprechende Übersetzung automatisch eingefügt.\n- Spezielle Fälle wie Codierungen oder Platzhalter werden nicht übersetzt, sondern direkt übernommen.\n\nKlicke „Weiter���, um mehr über den Übersetzungsprozess zu erfahren.",
            "widget": lambda: None},
            {"title": "Schritt 9: KI-Übersetzung starten", 
            "content": "Texte, die im Matching-Prozess nicht gefunden wurden, können von der KI übersetzt werden. Dafür musst du deinen OpenAI API-Schlüssel eingeben und die Option „Starte KI-Übersetzung“ nutzen.\n\n Die KI verwendet den angegebenen Kontext und die Systemanweisungen, um die Übersetzungen so präzise wie möglich zu gestalten.",
            "widget": lambda: None},
            {"title": "Schritt 10: Übersetzung herunterladen", 
            "content": "Nachdem alle Übersetzungen abgeschlossen sind (durch Matching oder KI), kannst du die vollständig übersetzte Datei im Excelformat herunterladen.\n\n Viel Spaß beim Verwenden des bonsAI Übersetzungsbüros! 🚀",
            "widget": lambda: None},
        ]

        step = st.session_state.tutorial_step
        if step < len(tutorial_steps):
            st.subheader(tutorial_steps[step]["title"])
            st.write(tutorial_steps[step]["content"])
            tutorial_steps[step]["widget"]()
            col1, col2 = st.columns([1, 1])
            if col1.button("Weiter"):
                next_step()
            if col2.button("Tutorial überspringen"):
                skip_tutorial()
        else:
            st.session_state.tutorial_done = True  # Direkt zur Hauptseite nach Abschluss
            st.session_state.tutorial_step = 0
            st.rerun()  # Hauptseite wird sofort angezeigt


    # Hauptanwendung
    def main_app():
        st.title("KI Matching App")

        st.markdown("""
        Willkommen im Matching-Übersetzungsbüro! Diese App hilft dir dabei, Texte zwischen einer Rogator-Umfrageexport-Datei und einer Übersetzungsdatei abzugleichen und die passenden Übersetzungen einzufügen.
        
        **So funktioniert's:**
        1. Lade deine **Rogator-Exportdatei** hoch (im `.xlsx` Format).
        2. Lade deine **Übersetzungsdatei** hoch (im `.xlsx` Format), die die englischen und übersetzten Texte enthält.
        3. Klicke auf den **"Starte KI-Übersetzung"** Button, um den Übersetzungsprozess zu starten.
        4. Die App gleicht die Texte aus Spalte C in der Rogator-Datei mit den Texten in der Übersetzungsdatei ab.
        5. Die App fügt die Übersetzungen in Spalte B der Rogator-Datei ein.
        6. Zusätzlich werden nicht gematchte Zellen von GPT übersetzt.
        7. Verfolge den Fortschritt live in der angezeigten Tabelle.
        8. Lade die modifizierte Rogator-Datei mit eingefügten Übersetzungen herunter.
        """)

        # Eingabefelder für OpenAI API und Übersetzungsparameter
        st.header("⚙️GPT-Übersetzungs-Einstellungen")
        col1, col2 = st.columns([10, 1])
        with col1:
            st.subheader("API-Schlüssel")
        with col2:
            if st.button("ℹ️", key="info_api_key"):
                toggle_info("show_api_key_info")
        if st.session_state.get("show_api_key_info", False):
            st.info(info_texts["api_key"])
        api_key = st.text_input("Gib deinen OpenAI API-Schlüssel ein", type="password")

        col1, col2 = st.columns([10, 1])
        with col1:
            st.subheader("Modellauswahl")
        with col2:
            if st.button("ℹ️", key="info_model_selection"):
                toggle_info("show_model_selection_info")
        if st.session_state.get("show_model_selection_info", False):
            st.info(info_texts["model_selection"])
        model_options = ["gpt-4o-mini", "o3-mini", "gpt-4o"]
        selected_model = st.selectbox("Wähle das Modell", model_options, index=0)

        col1, col2 = st.columns([10, 1])
        with col1:
            st.subheader("Batchgröße")
        with col2:
            if st.button("ℹ️", key="info_batch_size"):
                toggle_info("show_batch_size_info")
        if st.session_state.get("show_batch_size_info", False):
            st.info(info_texts["batch_size"])
        batch_size = st.slider("Batchgröße", min_value=2, max_value=50, value=10, step=2)

        col1, col2 = st.columns([10, 1])
        with col1:
            st.subheader("Spracheinstellungen")
        with col2:
            if st.button("ℹ️", key="info_language_selection"):
                toggle_info("show_language_selection_info")
        if st.session_state.get("show_language_selection_info", False):
            st.info(info_texts["language_selection"])
        language_options = ["English", "German", "French", "Spanish", "Italian", "Polish", "Dutch", "Portuguese", "Russian", "Turkish", "Arabic", "Chinese", "Japanese", "Korean", "Vietnamese"]
        source_language = st.selectbox("Ausgangssprache", language_options, index=0)
        target_language = st.selectbox("Zielsprache", language_options, index=1)

        col1, col2 = st.columns([10, 1])
        with col1:
            st.subheader("Befragtengruppe und Thema")
        with col2:
            if st.button("ℹ️", key="info_respondent_group"):
                toggle_info("show_respondent_group_info")
        if st.session_state.get("show_respondent_group_info", False):
            st.info(info_texts["respondent_group"])
        respondent_group = st.text_input("Befragtengruppe auf Englisch eingeben, z.B. 'Dentists'")
        survey_topic = st.text_input("Thema der Befragung auf Englisch eingeben, z.B. 'Dental hygiene'")

        col1, col2 = st.columns([10, 1])
        with col1:
            st.subheader("Fragebogen")
        with col2:
            if st.button("ℹ️", key="info_survey_content"):
                toggle_info("show_survey_content_info")
        if st.session_state.get("show_survey_content_info", False):
            st.info(info_texts["survey_content"])
        survey_content = st.text_area("Beschreibe hier in 1-2 Sätzen das Ziel und das Thema des Fragebogens auf Englisch.", height=100)

        # Generierung der Systemnachricht für GPT
        system_message = generate_system_message(
            source_language, respondent_group, survey_topic, target_language, survey_content
        )
        
        # Zusammenklappbare Systemanweisung mit Warnhinweis
        with st.expander("Systemanweisung für die KI (Achtung: Nur für fortgeschrittene Anwender)"):
            custom_system_message = st.text_area("Gib die Systemanweisung ein", value=system_message, height=200)

        # Füge das Menü für die festen Regeln direkt darunter ein
        with st.expander("Feste Regeln für das Matching (Achtung: Nur für fortgeschrittene Anwender)"):
            st.markdown("### Bearbeite die Regeln, um festzulegen, wann ein Text immer dupliziert werden soll:")
            
            # Bearbeitung der speziellen Fälle (RegEx-Muster)
            special_cases_input = st.text_area(
                "Spezielle Fälle (RegEx-Muster, ein Muster pro Zeile):",
                value="\n".join([
                    r'\{!%I-progress.txt%!}',
                    r'<div style="display:none;">&nbsp;</div>',
                    r'&nbsp;years'
                ]),
                height=150
            )
            
            # Weitere Bedingungen als Checkboxen oder Eingabefelder
            tag_start_end = st.checkbox("Texte, die mit '<' beginnen und mit '>' enden sollen immer dupliziert werden", value=True)
            exclamation_mark = st.checkbox("Texte, die mit '!%' beginnen und mit '%!' enden sollen immer dupliziert werden", value=True)
            single_exclamation = st.checkbox("Texte, die mit '!' beginnen und mit '!' enden sollen immer dupliziert werden", value=True)
            starts_with_zc = st.checkbox("Texte, die mit 'ZC:' beginnen sollen immer dupliziert werden", value=True)
            numeric_match = st.checkbox("Numerische Texte (Ganzzahlen oder Dezimalzahlen) sollen immer dupliziert werden", value=True)
            additional_terms = st.text_area(
                "Zusätzliche Schlüsselwörter (ein Begriff pro Zeile, case-insensitive):",
                value="\n".join([
                    "result:", "kommentar", "general remarks", 
                    "allgemeine bemerkungen", "screenout", "quotafull"
                ]),
                height=100
            )
            brand_match = st.checkbox("Texte, die mit 'Brand' gefolgt von einer Nummer beginnen, sollen immer dupliziert werden", value=True)
            starts_with_neue = st.checkbox("Texte, die mit 'Neue Antwort' beginnen, sollen immer dupliziert werden", value=True)

        # Aktualisierte Funktion zur Überprüfung, ob der Text immer dupliziert werden soll
        def should_always_duplicate(text):
            # Verarbeite die spezielle Fälle aus dem UI
            special_cases = special_cases_input.splitlines()
            for case in special_cases:
                if re.search(case.strip(), text):
                    return True
            
            # Überprüfung der weiteren Bedingungen
            if tag_start_end and text.startswith('<') and text.endswith('>'):
                return True
            if exclamation_mark and text.startswith('!%') and text.endswith('%!'):
                return True
            if single_exclamation and text.startswith('!') and text.endswith('!'):
                return True
            if starts_with_zc and text.startswith('ZC:'):
                return True
            if numeric_match and re.fullmatch(r'\d+(\.\d+)?', text):
                return True
            
            # Zusätzliche Schlüsselwörter überprüfen
            additional_terms_list = [term.strip().lower() for term in additional_terms.splitlines() if term.strip()]
            if text.strip().lower() in additional_terms_list:
                return True
            
            if brand_match and re.search(r'Brand\s+\d+', text):
                return True
            if starts_with_neue and text.startswith('Neue Antwort'):
                return True
            
            return False
        
        st.markdown("---")

        # Datei-Upload oder Template verwenden
        rogator_file = st.file_uploader("Lade deine Rogator-Exportdatei hoch", type=["xlsx"])
        
        # Übersetzungsdatei-Upload-Bereich
        st.subheader("Übersetzungsdatei")
        upload_method = st.radio(
            "Wähle eine Option:",
            ["Neue Übersetzungsdatei hochladen", "Vorlage verwenden"],
            index=0
        )

        if upload_method == "Neue Übersetzungsdatei hochladen":
            translation_file = st.file_uploader("Lade deine Übersetzungsdatei hoch", type=["xlsx"])
        else:
            # Template-Auswahl
            templates = load_templates_from_github()
            if templates:
                selected_template = st.selectbox(
                    "Verfügbare Übersetzungsvorlagen",
                    options=[t['name'] for t in templates],
                    index=None,
                    placeholder="Wähle eine Vorlage..."
                )
                
                if selected_template:
                    if st.button("🔄 Vorlage laden", key="load_template"):
                        try:
                            g = Github(st.secrets["github"]["token"])
                            repo = g.get_repo(st.secrets["github"]["repo"])
                            template = next(t for t in templates if t['name'] == selected_template)
                            content = repo.get_contents(template['path'])
                            file_content = content.decoded_content  # Korrekte Binärdaten
                            
                            # Behandle die Datei wie einen normalen File-Upload
                            file_like = BytesIO(file_content)
                            file_like.name = template['path']  # Setze einen Dateinamen
                            
                            # Speichere die Datei im Session State
                            st.session_state.translation_file = file_like
                            st.session_state.template_loaded = True
                            st.success(f"✅ Vorlage '{selected_template}' erfolgreich geladen!")
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Fehler beim Laden der Vorlage: {str(e)}")
            else:
                st.info("🔍 Keine Vorlagen verfügbar.")
            
            # Verwende die geladene Template-Datei wenn vorhanden
            if st.session_state.get("template_loaded", False) and st.session_state.get("translation_file") is not None:
                translation_file = st.session_state.translation_file
            else:
                translation_file = None

        if rogator_file and translation_file:
            try:
                # Einlesen der Rogator-Datei
                rogator_df = pd.read_excel(rogator_file, engine='openpyxl')

                required_columns = ['Frage-ID (gesperrt)', 'Text zur Übersetzung / Versionsanpassung', 'Vergleichstext Ursprungsversion']
                if not all(col in rogator_df.columns for col in required_columns):
                    st.error(f"Die Rogator-Datei muss die folgenden Spalten enthalten: {required_columns}")
                    st.stop()

                # Einlesen der Übersetzungsdatei
                translation_df = pd.read_excel(translation_file, engine='openpyxl')
                translation_df.columns = ['Master / English', 'DE']

                translation_df['Master / English'] = translation_df['Master / English'].astype(str)
                translation_df['Clean English'] = translation_df['Master / English'].apply(clean_text_for_matching)
                translation_dict = pd.Series(
                    translation_df['DE'].values, index=translation_df['Clean English']
                ).to_dict()

                rogator_df_processed = rogator_df.copy()
                rogator_df_processed['Quelle'] = 'Match'  # Initialisieren als 'Match'
                unmatched_texts = []
                unmatched_indices = []

                # Process Rogator DataFrame and match texts with the translation file
                unmatched_texts = []
                unmatched_indices = []

                for index, row in rogator_df_processed.iterrows():
                    text_to_translate = str(row['Vergleichstext Ursprungsversion'])
                    
                    # Bereinigung für Platzhalter
                    clean_text_to_translate, placeholders = clean_text_with_placeholders(text_to_translate)

                    # Überprüfung auf spezielle Fälle
                    if should_always_duplicate(text_to_translate):
                        rogator_df_processed.at[index, 'Text zur Übersetzung / Versionsanpassung'] = text_to_translate
                        rogator_df_processed.at[index, 'Quelle'] = 'Match'
                        continue

                    # Bereinigung für Matching
                    cleaned_for_matching = clean_text_for_matching(text_to_translate)

                    # Versuchen, eine bestehende ��bersetzung zu finden
                    if cleaned_for_matching in translation_dict:
                        translation = translation_dict[cleaned_for_matching]
                        # Überprüfen, ob die Übersetzung leer, "nan" oder None ist
                        if pd.isna(translation) or translation is None or translation.strip() == "":
                            # Wenn die Übersetzung leer ist, zur KI-Übersetzungsliste hinzufügen
                            unmatched_texts.append(text_to_translate)
                            unmatched_indices.append(index)
                            print(f"Leere Übersetzung zur KI-Übersetzung hinzugefügt: {text_to_translate}")  # Debug-Ausgabe
                        else:
                            restored_translation = restore_text(translation, placeholders)
                            rogator_df_processed.at[index, 'Text zur Übersetzung / Versionsanpassung'] = restored_translation
                            rogator_df_processed.at[index, 'Quelle'] = 'Match'
                    else:
                        # Statt alle nicht gematchten Texte zu sammeln, prüfen wir, ob die Zelle nach dem Matching leer ist
                        existing_translation = row.get('Text zur Übersetzung / Versionsanpassung', "")
                        # Prüfen, ob die ��bersetzungszelle leer, `None`, oder nur aus Whitespaces besteht
                        if pd.isna(existing_translation) or existing_translation is None or existing_translation.strip() == "":
                            unmatched_texts.append(text_to_translate)
                            unmatched_indices.append(index)
                            print(f"Text zur Übersetzung hinzugefügt: {text_to_translate}")  # Debug-Ausgabe

                # Count matched and unmatched texts
                num_matched_texts = rogator_df_processed[rogator_df_processed['Quelle'] == 'Match'].shape[0]
                num_unmatched_texts = len(unmatched_texts)

                # Display the counts in the Streamlit app
                st.info(f"**{num_matched_texts}** Texte wurden in der Übersetzungsdatei gefunden. ✨")
                st.info(f"**{num_unmatched_texts}** Texte sind noch offen und können von der KI übersetzt werden.\nKlicke hierfür auf den Button unter der Übersicht. 👇")

                # Display DataFrame in Streamlit
                st.header("Übersicht")
                dataframe_placeholder = st.empty()

                # Function for cell highlighting is already defined above (highlight_cells)
                styled_df = rogator_df_processed.style.apply(highlight_cells, axis=1)

                dataframe_placeholder.dataframe(styled_df)

                # Hinzufügen des "Start Translation" Buttons
                if st.button("Starte KI-Übersetzung"):
                    if unmatched_texts and api_key:
                        st.header("Übersetzung der nicht gefundenen Texte mit KI")
                        st.info(f"{len(unmatched_texts)} Texte werden jetzt von der KI übersetzt. ⏳")

                        # Initialize the GPT translations list and placeholder
                        gpt_translations = []
                        gpt_placeholder = st.empty()
                        gpt_placeholder.dataframe(pd.DataFrame(columns=['Index', 'Original Text', 'Translated Text']))

                        # Initialisierung der OpenAI API
                        openai.api_key = api_key

                        # Fortschrittsbalken und Status-Text
                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        translated_texts = []

                        for i, text in enumerate(unmatched_texts):
                            try:
                                response = openai.chat.completions.create(
                                    model=selected_model,
                                    messages=[
                                        {"role": "system", "content": custom_system_message},
                                        {"role": "user", "content": text}
                                    ]
                                )
                                translation = response.choices[0].message.content.strip()
                                restored_translation = restore_text(translation, [])
                                translated_texts.append(restored_translation)
                                rogator_df_processed.at[unmatched_indices[i], 'Text zur Übersetzung / Versionsanpassung'] = restored_translation
                                rogator_df_processed.at[unmatched_indices[i], 'Quelle'] = 'GPT'
                            except Exception as e:
                                restored_translation = f"Fehler: {e}"
                                translated_texts.append(restored_translation)
                                rogator_df_processed.at[unmatched_indices[i], 'Text zur Übersetzung / Versionsanpassung'] = restored_translation
                                rogator_df_processed.at[unmatched_indices[i], 'Quelle'] = 'GPT'
                            
                            # Append the translation to the GPT translations list
                            gpt_translations.append({
                                'Index': unmatched_indices[i],
                                'Original Text': text,
                                'Translated Text': restored_translation
                            })

                            # Convert the GPT translations list to a DataFrame
                            gpt_translations_df = pd.DataFrame(gpt_translations)

                            # Update the GPT translations placeholder with the new DataFrame
                            gpt_placeholder.dataframe(gpt_translations_df)

                            # Fortschritts aktualisieren
                            progress = (i + 1) / len(unmatched_texts)
                            progress_bar.progress(progress)
                            status_text.text(f"Übersetzung {i + 1} von {len(unmatched_texts)} abgeschlossen.")
                            
                            # Update des Haupt-DataFrames im UI mit neuem Styling
                            styled_df = rogator_df_processed.style.apply(highlight_cells, axis=1)
                            dataframe_placeholder.dataframe(styled_df)

                        st.success("Die KI-Übersetzung ist abgeschlossen. Die vollständige Übersetzung kann jetzt heruntergeladen werden. 🏆")
                    elif not api_key and unmatched_texts:
                        st.warning("Es gibt nicht gefundende Texte, aber kein OpenAI API-Schlüssel wurde eingegeben. Bitte gib einen API-Schlüssel ein, um diese Texte zu übersetzen.")
                    else:
                        st.info("Alle Texte sind bereits übersetzt. Keine weiteren Aktionen erforderlich.")

                # Download der verarbeiteten Datei
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    rogator_df_processed.to_excel(writer, index=False)
                output.seek(0)

                st.download_button(
                    label="Übersetzte Rogator-Datei herunterladen",
                    data=output,
                    file_name="übersetzte_rogator_export.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            except Exception as e:
                st.error(f"Es ist ein Fehler aufgetreten: {e}")

        st.markdown("---")
        
        # Template Management (optional)
        with st.expander("📚 Vorlagen verwalten"):
            st.header("Übersetzungsvorlagen")
            st.markdown("""
            Hier können Übersetzungsdateien als Vorlagen gespeichert und wiederverwendet werden.
            """)
            
            new_template = st.file_uploader(
                "Excel-Datei (.xlsx)",
                type=["xlsx"],
                key="template_uploader",
                help="Die Datei sollte zwei Spalten enthalten: 'Master / English' und 'DE'"
            )
            
            template_description = st.text_input(
                "Beschreibung/Name der Vorlage",
                placeholder="z.B. Henkel Waschmaittel Spanisch",
                help="Geben Sie einen beschreibenden Namen für die Vorlage ein"
            )
            
            if new_template and template_description:
                if st.button("💾 Als Vorlage speichern", key="save_template"):
                    with st.spinner("Speichere Vorlage..."):
                        if save_translation_to_github(new_template, template_description):
                            st.success("✅ Vorlage erfolgreich gespeichert!")
                            st.rerun()

    # Zeige Hauptanwendung oder Tutorial
    if st.session_state.tutorial_done:
        main_app()
    else:
        show_tutorial()

    # Add this section in the main_app function where you describe the app functionality
    with st.expander("📄 Beispiel für die Dateistruktur der Übersetzungsdatei"):
        st.markdown("""
        Die hochzuladende Datei muss im Excel-Format (.xlsx) vorliegen und sollte die folgenden Spalten enthalten: Spalte A (Ausgangssprache) und Spalte B (Übersetzung)

        Hier ist ein Beispiel für die Struktur der Übersetzungsdatei:

        | Englisch | Deutsch               |
        |------------------|------------------|
        | Hello            | Hallo            |
        | Thank you        | Danke            |
        """)

        # Add a sample file download button
        sample_file = BytesIO()
        with pd.ExcelWriter(sample_file, engine='openpyxl') as writer:
            sample_df = pd.DataFrame({
                'Master / English': ['Hello', 'Thank you'],
                'DE': ['Hallo', 'Danke']
            })
            sample_df.to_excel(writer, index=False)
        sample_file.seek(0)

        st.download_button(
            label="Beispiel-Übersetzungsdatei herunterladen",
            data=sample_file,
            file_name="sample_translation_file.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

def save_translation_to_github(translation_file, description):
    """
    Speichert eine Übersetzungsdatei auf GitHub als Template
    """
    try:
        # Lese die Excel-Datei als DataFrame
        df = pd.read_excel(translation_file, engine='openpyxl')
        
        # Erstelle eine neue Excel-Datei
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        
        g = Github(st.secrets["github"]["token"])
        repo = g.get_repo(st.secrets["github"]["repo"])
        
        # Dateiname generieren
        file_name = f"templates/{description.lower().replace(' ', '_')}.xlsx"
        
        # Datei als Binärdaten
        content = output.getvalue()  # Entfernt base64 Encoding
        
        try:
            # Versuche existierende Datei zu aktualisieren
            contents = repo.get_contents(file_name)
            repo.update_file(
                file_name,
                f"Update translation template: {description}",
                content,  # Direkte Binärdaten
                contents.sha,
                branch="main"  # Sicherstellen, dass der Branch korrekt ist
            )
        except:
            # Wenn Datei nicht existiert, neue erstellen
            repo.create_file(
                file_name,
                f"Add translation template: {description}",
                content,
                branch="main"  # Sicherstellen, dass der Branch korrekt ist
            )
        return True
    except Exception as e:
        st.error(f"Fehler beim Speichern der Vorlage: {str(e)}")
        return False

def load_templates_from_github():
    """
    Lädt verfügbare Übersetzungsvorlagen von GitHub
    """
    try:
        g = Github(st.secrets["github"]["token"])
        repo = g.get_repo(st.secrets["github"]["repo"])
        templates = []
        
        try:
            # Prüfe ob templates Verzeichnis existiert
            contents = repo.get_contents("templates")
        except Exception as e:
            # Wenn nicht, erstelle es
            repo.create_file(
                "templates/README.md",
                "Initialize templates directory",
                "# Translation Templates\nThis directory contains translation templates."
            )
            contents = repo.get_contents("templates")
            
        for content in contents:
            if content.name.endswith('.xlsx'):
                templates.append({
                    'name': content.name.replace('.xlsx', '').replace('_', ' ').title(),
                    'path': content.path
                })
        return templates
    except Exception as e:
        st.error(f"Fehler beim Laden der Vorlagen: {str(e)}")
        return []
