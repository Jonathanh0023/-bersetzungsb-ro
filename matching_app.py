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
        if text.strip().lower() in {"result:", "kommentar", "general remarks", "allgemeine bemerkungen", "screenout", "quotafull", "&#10148"}:
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