import streamlit as st
import pandas as pd
from pptx import Presentation
from openai import OpenAI
import os
from pathlib import Path
import difflib
from html import escape
from docx import Document
from io import BytesIO
import re
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

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
                # Überprüfe die Position des Shapes
                if hasattr(shape, "text") and shape.text.strip():
                    try:
                        # Ignoriere Shapes am oberen und unteren Rand
                        if hasattr(shape, "top") and hasattr(shape, "height"):
                            # Typische PowerPoint-Folie ist 7200000 EMUs hoch
                            slide_height = 7200000  # Standard PowerPoint Höhe
                            shape_top = shape.top
                            shape_bottom = shape.top + shape.height
                            
                            # Ignoriere obere 15% und untere 15% der Folie
                            if (shape_top > slide_height * 0.15 and 
                                shape_bottom < slide_height * 0.85):
                                texts.append({
                                    "slide_number": slide_number,
                                    "original_text": shape.text.strip(),
                                    "corrected_text": "",
                                    "status": "ausstehend"
                                })
                    except AttributeError:
                        # Falls die Position nicht ausgelesen werden kann, 
                        # ignoriere dieses Shape
                        continue
        
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

        def create_word_document():
            def clean_text_for_word(text):
                if not isinstance(text, str):
                    return ""
                # Entferne Steuerzeichen, aber behalte Zeilenumbrüche
                text = ''.join(char for char in text if char == '\n' or (ord(char) >= 32 and ord(char) != 127))
                # Ersetze mehrfache Zeilenumbrüche durch maximal zwei
                text = re.sub(r'\n{3,}', '\n\n', text)
                return text

            def create_word_diff(original, corrected):
                if corrected == '-' or original == corrected:
                    return "Keine Änderungen"
                
                def split_into_words(text):
                    # Ersetze Zeilenumbrüche mit speziellen Markierungen
                    lines = text.split('\n')
                    result = []
                    for line in lines:
                        # Füge die Wörter der Zeile hinzu
                        result.extend(line.split())
                        # Füge einen speziellen Marker für Zeilenumbrüche hinzu
                        result.append('\n')
                    return result[:-1]  # Entferne den letzten Zeilenumbruch
                
                original_words = split_into_words(original)
                corrected_words = split_into_words(corrected)
                matcher = difflib.SequenceMatcher(None, original_words, corrected_words)
                
                result = []
                for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                    if tag == 'replace':
                        result.append(('delete', ' '.join(original_words[i1:i2]).replace(' \n ', '\n')))
                        result.append(('insert', ' '.join(corrected_words[j1:j2]).replace(' \n ', '\n')))
                    elif tag == 'delete':
                        result.append(('delete', ' '.join(original_words[i1:i2]).replace(' \n ', '\n')))
                    elif tag == 'insert':
                        result.append(('insert', ' '.join(corrected_words[j1:j2]).replace(' \n ', '\n')))
                    elif tag == 'equal':
                        result.append(('equal', ' '.join(original_words[i1:i2]).replace(' \n ', '\n')))
                return result

            try:
                # Erstelle Word-Dokument
                doc = Document()
                doc.add_heading('Korrekturübersicht PowerPoint-Präsentation', 0)
                
                # Erstelle Tabellenstil für den Header
                header_style = doc.styles.add_style('HeaderStyle', 1)
                header_style.font.bold = True
                header_style.font.size = Pt(11)
                
                # Füge Spaltenüberschriften hinzu
                table = doc.add_table(rows=1, cols=3)
                table.style = 'Table Grid'
                table.autofit = False
                # Setze Spaltenbreiten (insgesamt 5000 Twips = 100%)
                for i, width in enumerate([1667, 1667, 1666]):  # ca. 33% pro Spalte
                    table.columns[i].width = width
                
                # Füge Header hinzu
                header_cells = table.rows[0].cells
                header_cells[0].text = "Originaltext"
                header_cells[1].text = "Korrigierter Text"
                header_cells[2].text = "Änderungen"
                
                # Style Header
                for cell in header_cells:
                    cell.paragraphs[0].style = header_style
                    cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Für jede Folie
                for _, row in st.session_state.corrections_df.iterrows():
                    # Füge neue Zeile für Folientitel hinzu
                    title_row = table.add_row()
                    title_cell = title_row.cells[0]
                    title_cell.merge(title_row.cells[-1])
                    title_cell.text = f"Folie {row['slide_number']}"
                    title_cell.paragraphs[0].style = header_style
                    
                    # Füge Inhaltszeile hinzu
                    content_row = table.add_row()
                    cells = content_row.cells
                    
                    # Originaltext
                    cells[0].text = clean_text_for_word(row['original_text'])
                    
                    # Korrigierter Text
                    cells[1].text = clean_text_for_word(row['corrected_text'])
                    
                    # Änderungen mit Farbmarkierung
                    diff_paragraph = cells[2].paragraphs[0]
                    diff_results = create_word_diff(
                        clean_text_for_word(row['original_text']),
                        clean_text_for_word(row['corrected_text'])
                    )
                    
                    if isinstance(diff_results, str):
                        diff_paragraph.add_run(diff_results)
                    else:
                        for diff_type, text in diff_results:
                            # Teile den Text an Zeilenumbrüchen
                            text_parts = text.split('\n')
                            for i, part in enumerate(text_parts):
                                if part.strip():  # Wenn der Teil nicht leer ist
                                    run = diff_paragraph.add_run(part)
                                    if diff_type == 'delete':
                                        run.font.color.rgb = RGBColor(198, 40, 40)  # Rot
                                        run.font.strike = True
                                    elif diff_type == 'insert':
                                        run.font.color.rgb = RGBColor(46, 125, 50)  # Grün
                                # Füge Zeilenumbruch hinzu, außer beim letzten Teil
                                if i < len(text_parts) - 1:
                                    diff_paragraph.add_run('\n')
                
                # Speichere das Dokument in einem BytesIO-Objekt
                doc_buffer = BytesIO()
                doc.save(doc_buffer)
                doc_buffer.seek(0)
                return doc_buffer
                
            except Exception as e:
                st.error(f"Fehler beim Erstellen des Word-Dokuments: {str(e)}")
                return None

        # Word-Export Button
        if st.button("Word-Dokument erstellen"):
            doc_buffer = create_word_document()
            if doc_buffer is not None:
                st.download_button(
                    label="Word-Dokument herunterladen",
                    data=doc_buffer,
                    file_name="powerpoint_korrekturen.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="word_download"  # Eindeutiger Key für den Download-Button
                )
