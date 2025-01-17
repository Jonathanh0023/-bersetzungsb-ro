import streamlit as st
import pandas as pd
from pptx import Presentation
from openai import OpenAI
import os
from pathlib import Path
import difflib
from html import escape

def powerpoint_app():
    # Seitenkonfiguration
    # Titel der App
    st.title("BonsAI PowerPoint Sprachprüfung und Korrektur")

    # Sidebar erstellen
    with st.sidebar:
        st.header("Einstellungen")
        
        # API Key Eingabe
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            help="Gib deinen OpenAI API Key ein. Der Key wird nicht gespeichert.",
            placeholder="sk-..."
        )
        
        # File Uploader
        uploaded_file = st.file_uploader("PowerPoint-Datei hochladen", type=["pptx"])
        
        if uploaded_file is not None:
            # Speichere die Datei im Session State
            st.session_state.uploaded_file = uploaded_file
        
        # Sprachauswahl
        target_language = st.selectbox(
            "Zielsprache",
            options=["US English", "UK English", "Deutsch"],
            index=0
        )

    # Prüfe ob API Key eingegeben wurde
    if not api_key:
        st.warning("Bitte gib einen OpenAI API Key ein, um fortzufahren.")
        st.stop()

    # OpenAI Client initialisieren
    client = OpenAI(api_key=api_key)

    def extract_text_from_pptx(uploaded_file):
        prs = Presentation(uploaded_file)
        texts = []
        
        for slide_number, slide in enumerate(prs.slides, 1):
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    texts.append({
                        "slide_number": slide_number,
                        "original_text": shape.text.strip(),
                        "corrected_text": "",
                        "status": "ausstehend"
                    })
        
        return pd.DataFrame(texts)

    def check_text_with_gpt(text):
        try:
            # Erstelle ein sprachspezifisches Prompt
            prompt_templates = {
                "US English": ("You are a professional editor specializing in US English. Please review and correct the following text, focusing on:\n"
                            "1. Grammar and syntax according to US English rules\n"
                            "2. Spelling using US English conventions\n"
                            "3. Punctuation following US style guides\n"
                            "4. Improving phrasing while maintaining the original meaning\n"
                            "5. Ensuring consistency with US English vocabulary and expressions\n\n"
                            "Important: Preserve all formatting, line breaks, font sizes, and text styling (bold, italic, etc.). Only correct the language aspects mentioned above.\n\n"
                            "If the text is too short or requires no corrections, respond with a single hyphen '-'"),
                
                "UK English": ("You are a professional editor specializing in British English. Please review and correct the following text, focusing on:\n"
                            "1. Grammar and syntax according to British English rules\n"
                            "2. Spelling using British English conventions\n"
                            "3. Punctuation following UK style guides\n"
                            "4. Improving phrasing while maintaining the original meaning\n"
                            "5. Ensuring consistency with British English vocabulary and expressions\n\n"
                            "Important: Preserve all formatting, line breaks, font sizes, and text styling (bold, italic, etc.). Only correct the language aspects mentioned above.\n\n"
                            "If the text is too short or requires no corrections, respond with a single hyphen '-'"),
                
                "Deutsch": ("Du bist ein professioneller Lektor für die deutsche Sprache. Bitte überprüfe und korrigiere den folgenden Text mit Fokus auf:\n"
                        "1. Grammatik und Syntax nach den Regeln der deutschen Sprache\n"
                        "2. Rechtschreibung nach aktueller deutscher Rechtschreibreform\n"
                        "3. Zeichensetzung nach deutschen Rechtschreibregeln\n"
                        "4. Verbesserung der Formulierungen unter Beibehaltung der ursprünglichen Bedeutung\n"
                        "5. Sicherstellung einer einheitlichen deutschen Ausdrucksweise\n\n"
                        "Wichtig: Bewahre alle Formatierungen, Zeilenumbrüche, Schriftgrößen und Textauszeichnungen (fett, kursiv, etc.). Korrigiere ausschließlich die oben genannten sprachlichen Aspekte.\n\n"
                        "Falls der Text zu kurz ist oder keine Korrekturen benötigt, antworte mit einem einzelnen Bindestrich '-'")
            }
            
            system_prompt = prompt_templates[target_language]
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            st.error(f"Fehler bei der GPT-Anfrage: {str(e)}")
            return text

    def create_diff_html(original, corrected):
        if corrected == '-' or original == corrected:
            return "Keine Änderungen"
        
        # Wörter statt Zeilen vergleichen
        def split_into_words(text):
            return text.replace('\n', ' \n ').split()
        
        original_words = split_into_words(original)
        corrected_words = split_into_words(corrected)
        
        # Matcher für die Unterschiede
        matcher = difflib.SequenceMatcher(None, original_words, corrected_words)
        
        # HTML aufbauen mit verbessertem CSS für bessere Lesbarkeit
        html = ['''
            <div style="font-family: arial; 
                        white-space: pre-wrap; 
                        line-height: 1.5; 
                        font-size: 1.1em;">
        ''']
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                # Dunkleres Rot für gelöschten Text, dunkleres Grün für neuen Text
                html.append(f'<span style="background-color: #ffcdd2; color: #c62828; text-decoration: line-through; padding: 2px 4px; border-radius: 3px; margin: 0 2px;">{" ".join(original_words[i1:i2])}</span>')
                html.append(f'<span style="background-color: #c8e6c9; color: #2e7d32; padding: 2px 4px; border-radius: 3px; margin: 0 2px;">{" ".join(corrected_words[j1:j2])}</span>')
            elif tag == 'delete':
                # Dunkleres Rot für gelöschten Text
                html.append(f'<span style="background-color: #ffcdd2; color: #c62828; text-decoration: line-through; padding: 2px 4px; border-radius: 3px; margin: 0 2px;">{" ".join(original_words[i1:i2])}</span>')
            elif tag == 'insert':
                # Dunkleres Grün für neuen Text
                html.append(f'<span style="background-color: #c8e6c9; color: #2e7d32; padding: 2px 4px; border-radius: 3px; margin: 0 2px;">{" ".join(corrected_words[j1:j2])}</span>')
            elif tag == 'equal':
                # Unveränderter Text mit verbesserter Lesbarkeit
                html.append(f'<span style="color: #37474f;">{" ".join(original_words[i1:i2])}</span>')
        
        html.append('</div>')
        return "".join(html)

    # Hauptlogik
    if uploaded_file is not None:
        if 'corrections_df' not in st.session_state:
            # Texte aus der PPT extrahieren
            st.session_state.corrections_df = extract_text_from_pptx(uploaded_file)
            
            # Zeige Gesamtanzahl der Slides
            total_slides = st.session_state.corrections_df['slide_number'].max()
            st.info(f"Präsentation enthält {total_slides} Folien")
            
            # Progress Bar für den Gesamtfortschritt
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # GPT-Korrektur für jeden Text durchführen
            total_items = len(st.session_state.corrections_df)
            for idx, row in st.session_state.corrections_df.iterrows():
                # Update Status
                current_slide = row['slide_number']
                status_text.text(f"Überprüfe Folie {current_slide} von {total_slides} ({idx + 1}/{total_items} Textelemente)")
                
                # Update Progress Bar
                progress_bar.progress((idx + 1) / total_items)
                
                corrected = check_text_with_gpt(row['original_text'])
                st.session_state.corrections_df.at[idx, 'corrected_text'] = corrected
            
            # Entferne Progress Bar und Status nach Abschluss
            progress_bar.empty()
            status_text.empty()
            
            # Zeige Zusammenfassung
            st.success(f"Überprüfung abgeschlossen! {total_items} Textelemente in {total_slides} Folien wurden verarbeitet.")

        # Anzeige der Korrekturen in drei Spalten
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.header("Originaltext")
        with col2:
            st.header("Korrigierter Text")
        with col3:
            st.header("Änderungen")

        # Für jede Korrektur
        for idx, row in st.session_state.corrections_df.iterrows():
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.text_area(
                    f"Folie {row['slide_number']} - Original",
                    row['original_text'],
                    key=f"original_{idx}",
                    disabled=True
                )
            
            with col2:
                corrected = st.text_area(
                    f"Folie {row['slide_number']} - Korrigiert",
                    row['corrected_text'],
                    key=f"corrected_{idx}"
                )
                
                # Aktualisiere den korrigierten Text im DataFrame
                st.session_state.corrections_df.at[idx, 'corrected_text'] = corrected
            
            with col3:
                diff_html = create_diff_html(row['original_text'], corrected)
                st.markdown(diff_html, unsafe_allow_html=True)
