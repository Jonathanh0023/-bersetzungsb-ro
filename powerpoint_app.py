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
        
        # Modus-Auswahl
        mode = st.selectbox(
            "Modus",
            options=["Editor", "Übersetzer"],
            index=0,
            help=("Editor: Korrigiert Texte in der gewählten Sprache\n"
                  "Übersetzer: Übersetzt Texte in die gewählte Sprache")
        )
        
        # Sprachauswahl
        target_language = st.selectbox(
            "Zielsprache",
            options=["US English", "UK English", "Deutsch", "Französisch", "Italienisch", 
                     "Dänisch", "Bulgarisch", "Holländisch", "Ungarisch", "Polnisch"],
            index=0
        )
        
        # Zusätzlicher Kontext
        additional_context = st.text_area(
            "Zusätzlicher Kontext (optional)",
            help="Hier können zusätzliche Informationen oder Anweisungen für die KI eingeben werden, "
                 "z.B. dass es sich um ein Transkript handelt oder Stil-Richtlinien oder Branchenkontext, etc...",
            placeholder="Beispiel: Dies ist ein Transkript einer Sitzung. Bitte korrigiere die Grammatik und die Rechtschreibung",
            max_chars=1000
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
                    try:
                        # Überprüfe die Position des Shapes (ob es sich um den Haupttextbereich handelt)
                        if hasattr(shape, "top") and hasattr(shape, "height"):
                            slide_height = 7200000  # Standard PowerPoint-Höhe in EMUs
                            shape_top = shape.top
                            shape_bottom = shape.top + shape.height
                            
                            # Ignoriere obere 15% und untere 15% der Folie
                            if (shape_top > slide_height * 0.15 and shape_bottom < slide_height * 0.85):
                                texts.append({
                                    "slide_number": slide_number,
                                    "original_text": shape.text.strip(),
                                    "corrected_text": "",
                                    "status": "ausstehend"
                                })
                    except AttributeError:
                        continue
        
        return pd.DataFrame(texts)

    def check_text_with_gpt(text):
        try:
            # Erstelle ein sprachspezifisches Prompt
            editor_templates = {
                "US English": (
                    "You are a professional editor specializing in US English. Please review and correct the following text, focusing on:\n"
                    "1. Grammar and syntax according to US English rules\n"
                    "2. Spelling using US English conventions\n"
                    "3. Punctuation following US style guides\n"
                    "4. Improving phrasing while maintaining the original meaning\n"
                    "5. Ensuring consistency with US English vocabulary and expressions\n\n"
                    "Important: Preserve all formatting, line breaks, font sizes, and text styling (bold, italic, etc.). Only correct the language aspects mentioned above.\n\n"
                    "If the text is too short or requires no corrections, respond with a single hyphen '-'"
                ),
                "UK English": (
                    "You are a professional editor specializing in British English. Please review and correct the following text, focusing on:\n"
                    "1. Grammar and syntax according to British English rules\n"
                    "2. Spelling using British English conventions\n"
                    "3. Punctuation following UK style guides\n"
                    "4. Improving phrasing while maintaining the original meaning\n"
                    "5. Ensuring consistency with British English vocabulary and expressions\n\n"
                    "Important: Preserve all formatting, line breaks, font sizes, and text styling (bold, italic, etc.). Only correct the language aspects mentioned above.\n\n"
                    "If the text is too short or requires no corrections, respond with a single hyphen '-'"
                ),
                "Deutsch": (
                    "Du bist ein professioneller Lektor für die deutsche Sprache. Bitte überprüfe und korrigiere den folgenden Text mit Fokus auf:\n"
                    "1. Grammatik und Syntax nach den Regeln der deutschen Sprache\n"
                    "2. Rechtschreibung nach aktueller deutscher Rechtschreibreform\n"
                    "3. Zeichensetzung nach deutschen Rechtschreibregeln\n"
                    "4. Verbesserung der Formulierungen unter Beibehaltung der ursprünglichen Bedeutung\n"
                    "5. Sicherstellung einer einheitlichen deutschen Ausdrucksweise\n\n"
                    "Wichtig: Bewahre alle Formatierungen, Zeilenumbrüche, Schriftgrößen und Textauszeichnungen (fett, kursiv, etc.). Korrigiere ausschließlich die oben genannten sprachlichen Aspekte.\n\n"
                    "Falls der Text zu kurz ist oder keine Korrekturen benötigt, antworte mit einem einzelnen Bindestrich '-'"
                ),
                "Französisch": (
                    "Tu es un éditeur professionnel spécialisé en français. Examine et corrige le texte suivant en te concentrant sur:\n"
                    "1. La grammaire et la syntaxe selon les règles du français\n"
                    "2. L'orthographe selon les conventions françaises actuelles\n"
                    "3. La ponctuation selon les règles françaises\n"
                    "4. L'amélioration des formulations tout en conservant le sens original\n"
                    "5. L'assurance d'une expression française cohérente et élégante\n\n"
                    "Important: Conserve tous les formatages, sauts de ligne, tailles de police et styles de texte (gras, italique, etc.). Corrige uniquement les aspects linguistiques mentionnés ci-dessus.\n\n"
                    "Si le texte est trop court ou ne nécessite aucune correction, réponds avec un simple tiret '-'"
                ),
                "Italienisch": (
                    "Sei un editor professionale specializzato in italiano. Esamina e correggi il seguente testo, concentrandoti su:\n"
                    "1. Grammatica e sintassi secondo le regole dell'italiano\n"
                    "2. Ortografia secondo le convenzioni italiane attuali\n"
                    "3. Punteggiatura secondo le regole italiane\n"
                    "4. Miglioramento delle formulazioni mantenendo il significato originale\n"
                    "5. Garanzia di un'espressione italiana coerente ed elegante\n\n"
                    "Importante: Mantieni tutta la formattazione, le interruzioni di riga e lo stile del testo. Corrigi solo gli aspetti linguistici menzionati sopra.\n\n"
                    "Se il testo è troppo breve o non necessita correzioni, rispondi con un singolo trattino '-'"
                ),
                "Dänisch": (
                    "Du er en professionel redaktør specialiseret i dansk. Gennemgå og ret følgende tekst med fokus på:\n"
                    "1. Grammatik og syntaks efter danske regler\n"
                    "2. Stavning efter danske konventioner\n"
                    "3. Tegnsætning efter danske regler\n"
                    "4. Forbedring af formuleringer med bibeholdelse af den oprindelige betydning\n"
                    "5. Sikring af et konsistent dansk sprog\n\n"
                    "Vigtigt: Bevar al formatering, linjeskift og tekststil. Ret kun de sproglige aspekter nævnt ovenfor.\n\n"
                    "Hvis teksten er for kort eller ikke kræver rettelser, svar med en enkelt bindestreg '-'"
                ),
                "Bulgarisch": (
                    "Вие сте професионален редактор, специализиран в български език. Прегледайте и коригирайте следния текст, фокусирайки се върху:\n"
                    "1. Граматика и синтаксис според правилата на българския език\n"
                    "2. Правопис според българските конвенции\n"
                    "3. Пунктуация според българските правила\n"
                    "4. Подобряване на формулировките при запазване на оригиналния смисъл\n"
                    "5. Осигуряване на последователен български изказ\n\n"
                    "Важно: Запазете цялото форматиране, преходи между редовете и стил на текста. Коригирайте само езиковите аспекти, посочени по-горе.\n\n"
                    "Ако текстът е твърде кратък или не се нуждае от корекции, отговорете с единично тире '-'"
                ),
                "Holländisch": (
                    "Je bent een professionele redacteur gespecialiseerd in het Nederlands. Controleer en corrigeer de volgende tekst, met focus op:\n"
                    "1. Grammatica en syntaxis volgens Nederlandse regels\n"
                    "2. Spelling volgens Nederlandse conventies\n"
                    "3. Interpunctie volgens Nederlandse regels\n"
                    "4. Verbetering van formuleringen met behoud van de oorspronkelijke betekenis\n"
                    "5. Zorgen voor consistent Nederlands taalgebruik\n\n"
                    "Belangrijk: Behoud alle opmaak, regeleinden en tekststijl. Corrigeer alleen de hierboven genoemde taalaspecten.\n\n"
                    "Als de tekst te kort is of geen correcties nodig heeft, antwoord dan met een enkel streepje '-'"
                ),
                "Ungarisch": (
                    "Ön egy magyar nyelvre szakosodott professzionális szerkesztő. Kérjük, ellenőrizze és javítsa a következő szöveget, koncentrálva:\n"
                    "1. Nyelvtan és mondattan a magyar szabályok szerint\n"
                    "2. Helyesírás a magyar konvenciók szerint\n"
                    "3. Központozás a magyar szabályok szerint\n"
                    "4. Megfogalmazások javítása az eredeti jelentés megtartásával\n"
                    "5. Következetes magyar nyelvhasználat biztosítása\n\n"
                    "Fontos: Őrizze meg az összes formázást, sortörést és szövegstílust. Csak a fent említett nyelvi szempontokat javítsa.\n\n"
                    "Ha a szöveg túl rövid vagy nem igényel javítást, válaszoljon egyetlen kötőjellel '-'"
                ),
                "Polnisch": (
                    "Jesteś profesjonalnym redaktorem specjalizującym się w języku polskim. Przejrzyj i popraw następujący tekst, skupiając się na:\n"
                    "1. Gramatyce i składni według zasad języka polskiego\n"
                    "2. Pisowni zgodnej z polskimi konwencjami\n"
                    "3. Interpunkcji według polskich zasad\n"
                    "4. Poprawie sformułowań przy zachowaniu oryginalnego znaczenia\n"
                    "5. Zapewnieniu spójnego języka polskiego\n\n"
                    "Ważne: Zachowaj całe formatowanie, podziały wierszy i styl tekstu. Poprawiaj tylko wymienione wyżej aspekty językowe.\n\n"
                    "Jeśli tekst jest zbyt krótki lub jest już po polsku, odpowiedz pojedynczym myślnikiem '-'"
                )
            }
            translator_templates = {
                "US English": (
                    "You are a professional translator. Translate the following text into US English.\n\n"
                    "Important guidelines:\n"
                    "1. Maintain the original meaning and tone\n"
                    "2. Use US English spelling and expressions\n"
                    "3. Preserve all formatting, line breaks, and text styling (bold, italic, etc.)\n"
                    "4. Ensure natural, fluent language appropriate for the context\n"
                    "5. Keep any technical terms or proper names as they are unless there's a standard English equivalent\n\n"
                    "If the text is too short or is already in English, respond with a single hyphen '-'"
                ),
                "UK English": (
                    "You are a professional translator. Translate the following text into British English.\n\n"
                    "Important guidelines:\n"
                    "1. Maintain the original meaning and tone\n"
                    "2. Use British English spelling and expressions\n"
                    "3. Preserve all formatting, line breaks, and text styling (bold, italic, etc.)\n"
                    "4. Ensure natural, fluent language appropriate for the context\n"
                    "5. Keep any technical terms or proper names as they are unless there's a standard English equivalent\n\n"
                    "If the text is too short or is already in English, respond with a single hyphen '-'"
                ),
                "Deutsch": (
                    "Du bist ein professioneller Übersetzer. Übersetze den folgenden Text ins Deutsche.\n\n"
                    "Wichtige Richtlinien:\n"
                    "1. Bewahre die ursprüngliche Bedeutung und den Ton\n"
                    "2. Verwende natürliches, zeitgemäßes Deutsch\n"
                    "3. Behalte alle Formatierungen, Zeilenumbrüche und Textauszeichnungen (fett, kursiv, etc.) bei\n"
                    "4. Stelle eine flüssige, dem Kontext angemessene Sprache sicher\n"
                    "5. Behalte Fachbegriffe oder Eigennamen bei, außer es gibt eine standardisierte deutsche Entsprechung\n\n"
                    "Falls der Text zu kurz ist oder bereits auf Deutsch ist, antworte mit einem einzelnen Bindestrich '-'"
                ),
                "Französisch": (
                    "Tu es un traducteur professionnel. Traduis le texte suivant en français.\n\n"
                    "Directives importantes:\n"
                    "1. Conserve le sens et le ton d'origine\n"
                    "2. Utilise un français naturel et contemporain\n"
                    "3. Préserve tous les formatages, sauts de ligne et styles de texte (gras, italique, etc.)\n"
                    "4. Assure un langage fluide et approprié au contexte\n"
                    "5. Conserve les termes techniques ou noms propres sauf s'il existe un équivalent français standard\n\n"
                    "Si le texte est trop court ou déjà en français, réponds avec un simple tiret '-'"
                ),
                "Italienisch": (
                    "Sei un traduttore professionista. Traduci il seguente testo in italiano.\n\n"
                    "Linee guida importanti:\n"
                    "1. Mantieni il significato e il tono originale\n"
                    "2. Usa un italiano naturale e contemporaneo\n"
                    "3. Preserva tutta la formattazione, le interruzioni di riga e lo stile del testo\n"
                    "4. Assicura un linguaggio fluido e appropriato al contesto\n"
                    "5. Mantieni i termini tecnici o i nomi propri a meno che non esista un equivalente italiano standard\n\n"
                    "Se il testo è troppo breve o è già in italiano, rispondi con un singolo trattino '-'"
                ),
                "Dänisch": (
                    "Du er en professionel oversætter. Oversæt følgende tekst til dansk.\n\n"
                    "Vigtige retningslinjer:\n"
                    "1. Bevar den oprindelige betydning og tone\n"
                    "2. Brug naturligt, moderne dansk\n"
                    "3. Bevar al formatering, linjeskift og tekststil\n"
                    "4. Sikr et flydende sprog, der passer til konteksten\n"
                    "5. Behold tekniske termer eller egennavne, medmindre der findes en standard dansk ækvivalent\n\n"
                    "Hvis teksten er for kort eller allerede er på dansk, svar med en enkelt bindestreg '-'"
                ),
                "Bulgarisch": (
                    "Вие сте професионален преводач. Преведете следния текст на български.\n\n"
                    "Важни насоки:\n"
                    "1. Запазете оригиналното значение и тон\n"
                    "2. Използвайте естествен, съвременен български език\n"
                    "3. Запазете цялото форматиране, преходи между редовете и стил на текста\n"
                    "4. Осигурете плавен език, подходящ за контекста\n"
                    "5. Запазете техническите термини или собствените имена, освен ако няма стандартен български еквивалент\n\n"
                    "Ако текстът е твърде кратък или вече е на български, отговорете с единично тире '-'"
                ),
                "Holländisch": (
                    "Je bent een professionele vertaler. Vertaal de volgende tekst naar het Nederlands.\n\n"
                    "Belangrijke richtlijnen:\n"
                    "1. Behoud de originele betekenis en toon\n"
                    "2. Gebruik natuurlijk, hedendaags Nederlands\n"
                    "3. Behoud alle opmaak, regeleinden en tekststijl\n"
                    "4. Zorg voor vloeiende taal die past bij de context\n"
                    "5. Behoud technische termen of eigennamen tenzij er een standaard Nederlands equivalent bestaat\n\n"
                    "Als de tekst te kort is of al in het Nederlands is, antwoord dan met een enkel streepje '-'"
                ),
                "Ungarisch": (
                    "Ön professzionális fordító. Fordítsa le a következő szöveget magyar nyelvre.\n\n"
                    "Fontos irányelvek:\n"
                    "1. Őrizze meg az eredeti jelentést és hangnemet\n"
                    "2. Használjon természetes, modern magyar nyelvet\n"
                    "3. Őrizze meg az összes formázást, sortörést és szövegstílust\n"
                    "4. Biztosítson folyékony, a kontextushoz illő nyelvezetet\n"
                    "5. Tartsa meg a műszaki kifejezéseket vagy tulajdonneveket, hacsak nincs szabványos magyar megfelelőjük\n\n"
                    "Ha a szöveg túl rövid vagy már magyar nyelvű, válaszoljon egyetlen kötőjellel '-'"
                ),
                "Polnisch": (
                    "Jesteś profesjonalnym tłumaczem. Przetłumacz następujący tekst na język polski.\n\n"
                    "Ważne wytyczne:\n"
                    "1. Zachowaj oryginalne znaczenie i ton\n"
                    "2. Używaj naturalnego, współczesnego języka polskiego\n"
                    "3. Zachowaj całe formatowanie, podziały wierszy i styl tekstu\n"
                    "4. Zapewnij płynny język odpowiedni do kontekstu\n"
                    "5. Zachowaj terminy techniczne lub nazwy własne, chyba że istnieje standardowy polski odpowiednik\n\n"
                    "Jeśli tekst jest zbyt krótki lub jest już po polsku, odpowiedz pojedynczym myślnikiem '-'"
                )
            }
            # Wähle das entsprechende Template basierend auf Modus und Sprache
            templates = editor_templates if mode == "Editor" else translator_templates
            system_prompt = templates[target_language]
            
            # Füge zusätzlichen Kontext hinzu, wenn vorhanden
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
            return response.choices[0].message.content
        except Exception as e:
            st.error(f"Fehler bei der GPT-Anfrage: {str(e)}")
            return text

    def create_diff_html(original, corrected):
        if corrected == '-' or original == corrected:
            return "Keine Änderungen"
        
        def split_into_words(text):
            return text.replace('\n', ' \n ').split()
        
        original_words = split_into_words(original)
        corrected_words = split_into_words(corrected)
        
        matcher = difflib.SequenceMatcher(None, original_words, corrected_words)
        
        html = ['''
            <div style="font-family: arial; 
                        white-space: pre-wrap; 
                        line-height: 1.5; 
                        font-size: 1.1em;">
        ''']
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                html.append(f'<span style="background-color: #ffcdd2; color: #c62828; text-decoration: line-through; padding: 2px 4px; border-radius: 3px; margin: 0 2px;">{" ".join(original_words[i1:i2])}</span>')
                html.append(f'<span style="background-color: #c8e6c9; color: #2e7d32; padding: 2px 4px; border-radius: 3px; margin: 0 2px;">{" ".join(corrected_words[j1:j2])}</span>')
            elif tag == 'delete':
                html.append(f'<span style="background-color: #ffcdd2; color: #c62828; text-decoration: line-through; padding: 2px 4px; border-radius: 3px; margin: 0 2px;">{" ".join(original_words[i1:i2])}</span>')
            elif tag == 'insert':
                html.append(f'<span style="background-color: #c8e6c9; color: #2e7d32; padding: 2px 4px; border-radius: 3px; margin: 0 2px;">{" ".join(corrected_words[j1:j2])}</span>')
            elif tag == 'equal':
                html.append(f'<span style="color: #37474f;">{" ".join(original_words[i1:i2])}</span>')
        
        html.append('</div>')
        return "".join(html)

    # Hauptlogik: Verarbeite die Präsentation erst nach Klick auf den Button "Prozess starten"
    if uploaded_file is not None:
        if st.button("Prozess starten"):
            st.session_state.corrections_df = extract_text_from_pptx(uploaded_file)
            
            # Zeige Gesamtanzahl der Folien
            total_slides = st.session_state.corrections_df['slide_number'].max()
            st.info(f"Präsentation enthält {total_slides} Folien")
            
            # Progress Bar für den Gesamtfortschritt
            progress_bar = st.progress(0)
            status_text = st.empty()
            total_items = len(st.session_state.corrections_df)
            
            # GPT-Korrektur für jeden Textelement durchführen
            for idx, row in st.session_state.corrections_df.iterrows():
                current_slide = row['slide_number']
                status_text.text(f"Überprüfe Folie {current_slide} von {total_slides} ({idx + 1}/{total_items} Textelemente)")
                progress_bar.progress((idx + 1) / total_items)
                
                corrected = check_text_with_gpt(row['original_text'])
                st.session_state.corrections_df.at[idx, 'corrected_text'] = corrected
            
            progress_bar.empty()
            status_text.empty()
            st.success(f"Überprüfung abgeschlossen! {total_items} Textelemente in {total_slides} Folien wurden verarbeitet.")
        
        # Anzeige der Korrekturen (falls bereits verarbeitet)
        if 'corrections_df' in st.session_state:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.header("Originaltext")
            with col2:
                st.header("Korrigierter Text")
            with col3:
                st.header("Änderungen")
            
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
                    st.session_state.corrections_df.at[idx, 'corrected_text'] = corrected
                
                with col3:
                    diff_html = create_diff_html(row['original_text'], corrected)
                    st.markdown(diff_html, unsafe_allow_html=True)
        
        # Word-Dokument Erstellen Button
        if st.button("Word-Dokument erstellen"):
            def create_word_document():
                def clean_text_for_word(text):
                    if not isinstance(text, str):
                        return ""
                    # Entferne Steuerzeichen, behalte Zeilenumbrüche
                    text = ''.join(char for char in text if char == '\n' or (ord(char) >= 32 and ord(char) != 127))
                    text = re.sub(r'\n{3,}', '\n\n', text)
                    return text

                def create_word_diff(original, corrected):
                    if corrected == '-' or original == corrected:
                        return "Keine Änderungen"
                    
                    def split_into_words(text):
                        lines = text.split('\n')
                        result = []
                        for line in lines:
                            result.extend(line.split())
                            result.append('\n')
                        return result[:-1]
                    
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
                    doc = Document()
                    doc.add_heading('Korrekturübersicht PowerPoint-Präsentation', 0)
                    
                    header_style = doc.styles.add_style('HeaderStyle', 1)
                    header_style.font.bold = True
                    header_style.font.size = Pt(11)
                    
                    table = doc.add_table(rows=1, cols=3)
                    table.style = 'Table Grid'
                    table.autofit = False
                    for i, width in enumerate([1667, 1667, 1666]):
                        table.columns[i].width = width
                    
                    header_cells = table.rows[0].cells
                    header_cells[0].text = "Originaltext"
                    header_cells[1].text = "Korrigierter Text"
                    header_cells[2].text = "Änderungen"
                    
                    for cell in header_cells:
                        cell.paragraphs[0].style = header_style
                        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                    
                    for _, row in st.session_state.corrections_df.iterrows():
                        title_row = table.add_row()
                        title_cell = title_row.cells[0]
                        title_cell.merge(title_row.cells[-1])
                        title_cell.text = f"Folie {row['slide_number']}"
                        title_cell.paragraphs[0].style = header_style
                        
                        content_row = table.add_row()
                        cells = content_row.cells
                        
                        cells[0].text = clean_text_for_word(row['original_text'])
                        cells[1].text = clean_text_for_word(row['corrected_text'])
                        
                        diff_paragraph = cells[2].paragraphs[0]
                        diff_results = create_word_diff(
                            clean_text_for_word(row['original_text']),
                            clean_text_for_word(row['corrected_text'])
                        )
                        
                        if isinstance(diff_results, str):
                            diff_paragraph.add_run(diff_results)
                        else:
                            for diff_type, text in diff_results:
                                text_parts = text.split('\n')
                                for i, part in enumerate(text_parts):
                                    if part.strip():
                                        run = diff_paragraph.add_run(part)
                                        if diff_type == 'delete':
                                            run.font.color.rgb = RGBColor(198, 40, 40)
                                            run.font.strike = True
                                        elif diff_type == 'insert':
                                            run.font.color.rgb = RGBColor(46, 125, 50)
                                    if i < len(text_parts) - 1:
                                        diff_paragraph.add_run('\n')
                    
                    doc_buffer = BytesIO()
                    doc.save(doc_buffer)
                    doc_buffer.seek(0)
                    return doc_buffer
                except Exception as e:
                    st.error(f"Fehler beim Erstellen des Word-Dokuments: {str(e)}")
                    return None
            
            doc_buffer = create_word_document()
            if doc_buffer is not None:
                st.download_button(
                    label="Word-Dokument herunterladen",
                    data=doc_buffer,
                    file_name="powerpoint_korrekturen.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="word_download"
                )

if __name__ == "__main__":
    powerpoint_app()
