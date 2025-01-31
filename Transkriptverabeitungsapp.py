import streamlit as st
import pandas as pd
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

def word_app():
    # Seitenkonfiguration
    st.title("BonsAI Word Universalwerkzeug")

    # --------------------------------------
    # 1) Texte aus dem hochgeladenen Word-Dokument extrahieren
    # --------------------------------------
    def extract_text_from_docx(file) -> pd.DataFrame:
        doc = Document(file)
        data = []
        current_page_text = []
        page_number = 1
        estimated_chars_per_page = 1500  # Ungefähre Anzahl von Zeichen pro Seite
        current_chars = 0

        def process_paragraph(paragraph):
            """Verarbeitet einen einzelnen Paragraphen und gibt den formatierten Text zurück."""
            text = paragraph.text.strip()
            if text:
                # Füge Leerzeilen um Überschriften ein
                if paragraph.style.name.startswith('Heading'):
                    return f"\n{text}\n"
                return text
            return ""

        def process_table(table):
            """Verarbeitet eine Tabelle und gibt den formatierten Text zurück."""
            # Prüfe ob die Tabelle leer ist
            if not table.rows:
                return ""
            
            table_text = []
            table_text.append("")  # Leerzeile vor der Tabelle
            
            # Verarbeite jede Zeile nur einmal
            seen_rows = set()  # Speichert bereits gesehene Zeileninhalte
            
            for row in table.rows:
                # Extrahiere den Text aus jeder Zelle
                row_cells = []
                for cell in row.cells:
                    # Nehme nur den ersten Paragraphen jeder Zelle
                    cell_text = cell.paragraphs[0].text.strip() if cell.paragraphs else ""
                    row_cells.append(cell_text)
                
                # Erstelle einen eindeutigen Schlüssel für diese Zeile
                row_key = "||".join(row_cells)
                
                # Füge die Zeile nur hinzu, wenn wir sie noch nicht gesehen haben
                if row_key not in seen_rows and any(cell.strip() for cell in row_cells):
                    seen_rows.add(row_key)
                    row_text = " | ".join(row_cells)
                    table_text.append(row_text)
            
            table_text.append("")  # Leerzeile nach der Tabelle
            return "\n".join(table_text)

        def add_to_current_page(text):
            """Fügt Text zur aktuellen Seite hinzu und erstellt bei Bedarf eine neue Seite."""
            nonlocal current_chars, page_number, current_page_text
            
            if text.strip():
                current_chars += len(text)
                current_page_text.append(text)
                
                # Wenn die geschätzte Seitenlänge erreicht ist
                if current_chars >= estimated_chars_per_page:
                    # Füge die aktuelle Seite zum DataFrame hinzu
                    combined_text = "\n".join(current_page_text).strip()
                    if combined_text:
                        data.append({
                            "page_number": page_number,
                            "original_text": combined_text,
                            "corrected_text": "",
                            "status": "ausstehend"
                        })
                    # Setze Variablen für die nächste Seite zurück
                    current_page_text = []
                    current_chars = 0
                    page_number += 1

        # Verarbeite alle Elemente im Dokument
        for element in doc.element.body:
            if element.tag.endswith('p'):  # Paragraph
                try:
                    # Finde den entsprechenden Paragraph im Dokument
                    para_index = list(doc.element.body).index(element)
                    paragraph = doc.paragraphs[para_index]
                    text = process_paragraph(paragraph)
                    if text:
                        add_to_current_page(text)
                except IndexError:
                    continue
            
            elif element.tag.endswith('tbl'):  # Table
                try:
                    # Finde den Index der Tabelle
                    table_index = sum(1 for e in doc.element.body[:doc.element.body.index(element)]
                                    if e.tag.endswith('tbl'))
                    table = doc.tables[table_index]
                    table_text = process_table(table)
                    if table_text:
                        add_to_current_page(table_text)
                except IndexError:
                    continue

        # Füge die letzte Seite hinzu, falls noch Text übrig ist
        if current_page_text:
            combined_text = "\n".join(current_page_text).strip()
            if combined_text:
                data.append({
                    "page_number": page_number,
                    "original_text": combined_text,
                    "corrected_text": "",
                    "status": "ausstehend"
                })

        # Wenn keine Daten gefunden wurden
        if not data:
            st.warning("Keine Texte im Dokument gefunden.")
            return pd.DataFrame(columns=["page_number", "original_text", "corrected_text", "status"])

        df = pd.DataFrame(data)
        
        # Entferne doppelte Leerzeilen
        df['original_text'] = df['original_text'].apply(lambda x: re.sub(r'\n{3,}', '\n\n', x))
        
        # Logging
        st.info(f"Extrahierte Seiten: {len(df)}\n"
                f"Gesamtzeichen: {sum(len(text) for text in df['original_text'])}")
        
        return df

    # --------------------------------------
    # 2) GPT-Korrektur für einen Text durchführen
    # --------------------------------------
    def check_text_with_gpt(text):
        try:
            if mode == "Freier Modus":
                system_prompt = additional_context if additional_context else "Bitte bearbeite den folgenden Text."
            else:
                # Ursprüngliche Logik für Editor/Übersetzer Modi
                templates = editor_templates if mode == "Editor" else translator_templates
                system_prompt = templates[target_language]
                if additional_context:
                    system_prompt += f"\n\nZusätzlicher Kontext:\n{additional_context}"
            
            # Debug: Zeige System Prompt
            with st.expander("Debug: System Prompt"):
                st.code(system_prompt, language="text")

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ]
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            st.error(f"Fehler bei der GPT-Anfrage: {str(e)}")
            return text

    # --------------------------------------
    # 3) HTML-Diff erstellen für die Anzeige in Streamlit
    # --------------------------------------
    def create_diff_html(original, corrected):
        if corrected == '-' or original == corrected:
            return "Keine Änderungen"
        
        def split_into_words(txt):
            return txt.replace('\n', ' \n ').split()
        
        original_words = split_into_words(original)
        corrected_words = split_into_words(corrected)
        
        matcher = difflib.SequenceMatcher(None, original_words, corrected_words)
        
        html = ["""
        <div style="
            font-family: arial; 
            white-space: pre-wrap; 
            line-height: 1.5; 
            font-size: 1.1em;">
        """]
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                # Rot für gelöschten Text, Grün für neuen Text
                html.append(f'<span style="background-color: #ffcdd2; color: #c62828; text-decoration: line-through; padding: 2px 4px; border-radius: 3px; margin: 0 2px;">{" ".join(original_words[i1:i2])}</span>')
                html.append(f'<span style="background-color: #c8e6c9; color: #2e7d32; padding: 2px 4px; border-radius: 3px; margin: 0 2px;">{" ".join(corrected_words[j1:j2])}</span>')
            elif tag == 'delete':
                html.append(f'<span style="background-color: #ffcdd2; color: #c62828; text-decoration: line-through; padding: 2px 4px; border-radius: 3px; margin: 0 2px;">{" ".join(original_words[i1:i2])}</span>')
            elif tag == 'insert':
                html.append(f'<span style="background-color: #c8e6c9; color: #2e7d32; padding: 2px 4px; border-radius: 3px; margin: 0 2px;">{" ".join(corrected_words[j1:j2])}</span>')
            else:  # 'equal'
                html.append(f'<span style="color: #37474f;">{" ".join(original_words[i1:i2])}</span>')
        
        html.append('</div>')
        return "".join(html)

    # --------------------------------------
    # 4) Funktion zum Erstellen eines Word-Dokuments
    # --------------------------------------
    def create_word_document(corrections_df):
        def clean_text_for_word(text):
            if not isinstance(text, str):
                return ""
            text = "".join(ch for ch in text if ch == "\n" or (ord(ch) >= 32 and ord(ch) != 127))
            text = re.sub(r'\n{3,}', '\n\n', text)
            return text

        try:
            doc = Document()
            
            # Nur verarbeitete Texte in das Dokument einfügen
            for _, row in corrections_df.iterrows():
                # Verarbeiteter Text ohne Seitenüberschrift
                doc.add_paragraph(clean_text_for_word(row['corrected_text']))

            # BytesIO für den Download
            doc_buffer = BytesIO()
            doc.save(doc_buffer)
            doc_buffer.seek(0)
            return doc_buffer
            
        except Exception as e:
            st.error(f"Fehler beim Erstellen des Word-Dokuments: {str(e)}")
            return None

    # Templates für Editor und Übersetzer definieren
    editor_templates = {
        "US English": (
            "You are a professional editor specializing in US English. "
            "Please review and correct the following text, focusing on grammar, "
            "spelling, and style according to US English conventions."
        ),
        "UK English": (
            "You are a professional editor specializing in UK English. "
            "Please review and correct the following text, focusing on grammar, "
            "spelling, and style according to UK English conventions."
        ),
        "Deutsch": (
            "Du bist ein professioneller Lektor für die deutsche Sprache. "
            "Bitte überprüfe und korrigiere den folgenden Text mit Fokus auf "
            "Grammatik, Rechtschreibung und Stil nach deutschen Konventionen."
        ),
        "Französisch": (
            "Tu es un éditeur professionnel spécialisé en français. "
            "Examine et corrige le texte suivant en te concentrant sur la "
            "grammaire, l'orthographe et le style selon les conventions françaises."
        ),
        "Italienisch": (
            "Sei un editor professionale specializzato in italiano. "
            "Esamina e correggi il seguente testo, concentrandoti su "
            "grammatica, ortografia e stile secondo le convenzioni italiane."
        ),
        "Dänisch": (
            "Du er en professionel redaktør specialiseret i dansk. "
            "Gennemgå og ret følgende tekst med fokus på "
            "grammatik, stavning og stil efter danske konventioner."
        ),
        "Bulgarisch": (
            "Вие сте професионален редактор за български език. "
            "Прегледайте и коригирайте следния текст, като се съсредоточите върху "
            "граматика, правопис и стил според българските конвенции."
        ),
        "Holländisch": (
            "Je bent een professionele redacteur gespecialiseerd in het Nederlands. "
            "Controleer en corrigeer de volgende tekst, met focus op "
            "grammatica, spelling en stijl volgens Nederlandse conventies."
        ),
        "Ungarisch": (
            "Ön egy magyar nyelvre szakosodott professzionális szerkesztő. "
            "Kérjük, ellenőrizze és javítsa a következő szöveget, koncentrálva a "
            "nyelvtanra, helyesírásra és stílusra a magyar konvenciók szerint."
        ),
        "Polnisch": (
            "Jesteś profesjonalnym redaktorem specjalizującym się w języku polskim. "
            "Przejrzyj i popraw następujący tekst, skupiając się na "
            "gramatyce, pisowni i stylu według polskich konwencji."
        )
    }

    translator_templates = {
        "US English": (
            "You are a professional translator. Translate the following text into "
            "US English, maintaining the original meaning and style."
        ),
        "UK English": (
            "You are a professional translator. Translate the following text into "
            "UK English, maintaining the original meaning and style."
        ),
        "Deutsch": (
            "Du bist ein professioneller Übersetzer. Übersetze den folgenden Text "
            "ins Deutsche und bewahre dabei die ursprüngliche Bedeutung und den Stil."
        ),
        "Französisch": (
            "Tu es un traducteur professionnel. Traduis le texte suivant en "
            "français en conservant le sens et le style d'origine."
        ),
        "Italienisch": (
            "Sei un traduttore professionista. Traduci il seguente testo in "
            "italiano mantenendo il significato e lo stile originali."
        ),
        "Dänisch": (
            "Du er en professionel oversætter. Oversæt følgende tekst til "
            "dansk og bevar den oprindelige betydning og stil."
        ),
        "Bulgarisch": (
            "Вие сте професионален преводач. Преведете следния текст на "
            "български, като запазите оригиналното значение и стил."
        ),
        "Holländisch": (
            "Je bent een professionele vertaler. Vertaal de volgende tekst naar "
            "het Nederlands en behoud de originele betekenis en stijl."
        ),
        "Ungarisch": (
            "Ön professzionális fordító. Fordítsa le a következő szöveget "
            "magyar nyelvre, megőrizve az eredeti jelentést és stílust."
        ),
        "Polnisch": (
            "Jesteś profesjonalnym tłumaczem. Przetłumacz następujący tekst na "
            "język polski, zachowując oryginalne znaczenie i styl."
        )
    }

    # -- SIDEBAR --
    with st.sidebar:
        st.header("Einstellungen")
        
        # API Key
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            help="Gib deinen OpenAI API Key ein. Der Key wird nicht gespeichert.",
            placeholder="sk-..."
        )
        
        # File Uploader für mehrere DOCX
        uploaded_files = st.file_uploader(
            "Word-Dateien hochladen", 
            type=["docx"],
            accept_multiple_files=True
        )
        
        if uploaded_files:
            st.session_state.uploaded_files = uploaded_files
        
        # Modus-Auswahl
        mode = st.selectbox(
            "Modus",
            options=["Freier Modus", "Editor", "Übersetzer"],
            index=0,
            help=("Freier Modus: Beliebige Anweisungen über das Prompt-Feld\n"
                  "Editor: Korrigiert und verbessert Texte in der gewählten Sprache\n"
                  "Übersetzer: Übersetzt Texte in die gewählte Sprache")
        )
        
        # Sprachauswahl nur anzeigen, wenn nicht im freien Modus
        target_language = None
        if mode != "Freier Modus":
            target_language = st.selectbox(
                "Zielsprache",
                options=["US English", "UK English", "Deutsch", "Französisch", "Italienisch", 
                        "Dänisch", "Bulgarisch", "Holländisch", "Ungarisch", "Polnisch"],
                index=0
            )
        
        # Zusätzlicher Kontext/Prompt
        context_label = "KI-Anweisungen" if mode == "Freier Modus" else "Zusätzliche Anweisungen (optional)"
        context_help = ("Gib hier deine Anweisungen für die KI ein" if mode == "Freier Modus" else 
                       "Hier können zusätzliche Anweisungen für die KI eingegeben werden")
        
        additional_context = st.text_area(
            context_label,
            help=context_help,
            placeholder=("Beispiel: Fasse den Text zusammen und erstelle eine Gliederung..." 
                        if mode == "Freier Modus" else 
                        "Beispiel: Verwende einen formellen Schreibstil..."),
            max_chars=1000
        )

    # Prüfe, ob ein API-Key vorliegt
    if not api_key:
        st.warning("Bitte gib einen OpenAI API Key ein, um fortzufahren.")
        st.stop()

    # OpenAI Client initialisieren
    client = OpenAI(api_key=api_key)

    # Initialisiere session state für Dateiverarbeitung
    if 'processed_files' not in st.session_state:
        st.session_state.processed_files = {}

    if uploaded_files:
        # Zeige Übersicht der hochgeladenen Dateien
        st.header("Hochgeladene Dateien")
        for file in uploaded_files:
            if file.name not in st.session_state.processed_files:
                st.session_state.processed_files[file.name] = {
                    'status': 'ausstehend',
                    'corrections_df': None
                }
            
            # Status-Anzeige und Verarbeitungs-Button für jede Datei
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"📄 {file.name}")
                status = st.session_state.processed_files[file.name]['status']
                if status == 'ausstehend':
                    st.info("Status: Ausstehend")
                elif status == 'verarbeitung':
                    st.warning("Status: Wird verarbeitet...")
                elif status == 'abgeschlossen':
                    st.success("Status: Abgeschlossen")
            
            with col2:
                if status == 'ausstehend':
                    if st.button("Verarbeiten", key=f"process_{file.name}"):
                        # Verarbeite die Datei
                        st.session_state.processed_files[file.name]['status'] = 'verarbeitung'
                        corrections_df = extract_text_from_docx(file)
                        
                        total_pages = len(corrections_df)
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # GPT-Korrektur für jede Seite
                        for idx, row in corrections_df.iterrows():
                            status_text.text(f"Korrigiere Seite {idx+1} von {total_pages} ...")
                            progress_bar.progress((idx + 1) / total_pages)
                            
                            corrected = check_text_with_gpt(row['original_text'])
                            corrections_df.at[idx, 'corrected_text'] = corrected
                        
                        # Speichere die Ergebnisse
                        st.session_state.processed_files[file.name]['corrections_df'] = corrections_df
                        st.session_state.processed_files[file.name]['status'] = 'abgeschlossen'
                        
                        # UI aufräumen
                        progress_bar.empty()
                        status_text.empty()
                        st.success(f"Verarbeitung von {file.name} abgeschlossen!")
                        st.rerun()

        # Zeige verarbeitete Dateien und deren Ergebnisse
        if any(file_data['status'] == 'abgeschlossen' for file_data in st.session_state.processed_files.values()):
            st.header("Verarbeitete Dateien")
            for file_name, file_data in st.session_state.processed_files.items():
                if file_data['status'] == 'abgeschlossen':
                    with st.expander(f"📄 {file_name}"):
                        corrections_df = file_data['corrections_df']
                        
                        # Zeige korrigierte Texte
                        for idx, row in corrections_df.iterrows():
                            st.subheader(f"Seite {row['page_number']}")
                            corrected_text = st.text_area(
                                "Korrigierter Text",
                                row['corrected_text'],
                                key=f"corrected_{file_name}_{idx}",
                                height=400
                            )
                            corrections_df.at[idx, 'corrected_text'] = corrected_text
                        
                        # Download-Button für jede Datei
                        if st.button("Word-Dokument erstellen", key=f"create_doc_{file_name}"):
                            doc_buffer = create_word_document(corrections_df)
                            if doc_buffer is not None:
                                st.download_button(
                                    label="Word-Dokument herunterladen",
                                    data=doc_buffer,
                                    file_name=f"verarbeitet_{file_name}",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"download_{file_name}"
                                )

            # Reset-Button für alle Verarbeitungen (nur einmal anzeigen)
            if st.button("Alle Verarbeitungen zurücksetzen", key="reset_all"):
                st.session_state.processed_files = {}
                st.rerun()

# Die auskommentierten Zeilen am Ende müssen aktiv sein:
if __name__ == "__main__":
    word_app()
