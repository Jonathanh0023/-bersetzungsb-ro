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
                    "3. Bevar al formatering, linjeskift og tekststil (fed, kursiv osv.)\n"
                    "4. Sikre et flydende sprog passende til konteksten\n"
                    "5. Behold fagudtryk eller egennavne, medmindre der findes en standard dansk ækvivalent\n\n"
                    "Hvis teksten er for kort eller allerede er på dansk, svar med en enkelt bindestreg '-'"
                ),
                "Bulgarisch": (
                    "Вие сте професионален преводач. Преведете следния текст на български.\n\n"
                    "Важни насоки:\n"
                    "1. Запазете оригиналното значение и тон\n"
                    "2. Използвайте естествен, съвременен български език\n"
                    "3. Запазете цялото форматиране, преходите между редовете и стила на текста\n"
                    "4. Осигурете плавен език, подходящ за контекста\n"
                    "5. Запазете технически термини или собствени имена, освен ако няма стандартен български еквивалент\n\n"
                    "Ако текстът е твърде кратък или вече е на български, отговорете с единично тире '-'"
                ),
                "Holländisch": (
                    "Je bent een professionele vertaler. Vertaal de volgende tekst naar het Nederlands.\n\n"
                    "Belangrijke richtlijnen:\n"
                    "1. Behoud de oorspronkelijke betekenis en toon\n"
                    "2. Gebruik natuurlijk, hedendaags Nederlands\n"
                    "3. Behoud alle opmaak, regeleinden en tekststijl (vet, cursief, enz.)\n"
                    "4. Zorg voor vloeiende taal die past bij de context\n"
                    "5. Behoud technische termen of eigennamen, tenzij er een standaard Nederlands equivalent bestaat\n\n"
                    "Als de tekst te kort is of al in het Nederlands is, antwoord dan met een enkel streepje '-'"
                ),
                "Ungarisch": (
                    "Ön professzionális fordító. Fordítsa le a következő szöveget magyarra.\n\n"
                    "Fontos irányelvek:\n"
                    "1. Tartsa meg az eredeti jelentést és hangnemet\n"
                    "2. Használjon természetes, modern magyar nyelvet\n"
                    "3. Őrizze meg az összes formázást, sortörést és szövegstílust (félkövér, dőlt, stb.)\n"
                    "4. Biztosítson folyékony, a kontextushoz illő nyelvet\n"
                    "5. Tartsa meg a szakkifejezéseket vagy tulajdonneveket, hacsak nincs standard magyar megfelelő\n\n"
                    "Ha a szöveg túl rövid vagy már magyar nyelvű, válaszoljon egyetlen kötőjellel '-'"
                ),
                "Polnisch": (
                    "Jesteś profesjonalnym tłumaczem. Przetłumacz poniższy tekst na język polski.\n\n"
                    "Ważne wytyczne:\n"
                    "1. Zachowaj oryginalne znaczenie i ton\n"
                    "2. Używaj naturalnego, współczesnego języka polskiego\n"
                    "3. Zachowaj całe formatowanie, podziały wierszy i styl tekstu (pogrubienie, kursywa, itp.)\n"
                    "4. Zapewnij płynny język odpowiedni do kontekstu\n"
                    "5. Zachowaj terminy techniczne lub nazwy własne, chyba że istnieje standardowy polski odpowiednik\n\n"
                    "Jeśli tekst jest zbyt krótki lub jest już w języku polskim, odpowiedz pojedynczym myślnikiem '-'"
                )
            }

            # Wähle den richtigen Systemprompt basierend auf dem Modus
            templates = editor_templates if mode == "Editor" else translator_templates
            system_prompt = templates.get(target_language, templates["US English"])
            
            # Füge den zusätzlichen Kontext zum Systemprompt hinzu, wenn vorhanden
            if additional_context and len(additional_context.strip()) > 0:
                system_prompt += f"\n\nAdditional context: {additional_context}"

            # Führe API-Anfrage durch
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.7,
                max_tokens=4000,
                presence_penalty=0
            )

            # Extrahiere den korrigierten Text
            corrected_text = response.choices[0].message.content.strip()
            
            # Entferne '-' wenn das die einzige Antwort ist
            if corrected_text == '-':
                corrected_text = text  # Behalte den Originaltext bei
                
            return corrected_text
        except Exception as e:
            st.error(f"Fehler bei der GPT-Anfrage: {str(e)}")
            return text  # Bei Fehlern Originaltext zurückgeben
    
    def generate_diff_html(original, corrected):
        """Generate HTML that shows the difference between original and corrected text"""
        if original == corrected:
            return f"<div style='background-color: #f0f0f0; padding: 10px; border-radius: 5px;'>{escape(original)}</div>"
        
        diff = difflib.ndiff(original.splitlines(), corrected.splitlines())
        
        html_parts = []
        for line in diff:
            if line.startswith('+ '):
                html_parts.append(f"<div style='background-color: #e6ffed; color: #22863a; padding: 2px 5px;'>{escape(line[2:])}</div>")
            elif line.startswith('- '):
                html_parts.append(f"<div style='background-color: #ffeef0; color: #cb2431; padding: 2px 5px; text-decoration: line-through;'>{escape(line[2:])}</div>")
            elif line.startswith('  '):
                html_parts.append(f"<div style='padding: 2px 5px;'>{escape(line[2:])}</div>")
        
        return "".join(html_parts)

    def create_summary_document(data_df):
        """Erstellt ein Word-Dokument mit Original- und korrigiertem Text"""
        doc = Document()
        
        # Titel hinzufügen
        doc.add_heading('PowerPoint-Korrektur-Zusammenfassung', level=1)
        
        # Füge Informationen zum Modus und zur Zielsprache hinzu
        doc.add_paragraph(f"Modus: {mode}")
        doc.add_paragraph(f"Zielsprache: {target_language}")
        
        # Zusätzlicher Kontext, falls vorhanden
        if additional_context:
            doc.add_paragraph(f"Zusätzlicher Kontext: {additional_context}")
        
        # Überschrift für die Korrekturen
        doc.add_heading('Korrekturen nach Folien', level=2)
        
        # Für jede korrigierte Folie
        for _, row in data_df.iterrows():
            slide_num = row['slide_number']
            original = row['original_text']
            corrected = row['corrected_text']
            
            # Nur Änderungen anzeigen
            if original != corrected:
                # Überschrift für die Folie
                doc.add_heading(f'Folie {slide_num}', level=3)
                
                # Original Text mit roter Markierung
                doc.add_paragraph("Original:")
                p = doc.add_paragraph(original)
                for run in p.runs:
                    run.font.color.rgb = RGBColor(200, 0, 0)
                
                # Korrigierter Text mit grüner Markierung
                doc.add_paragraph("Korrigiert:")
                p = doc.add_paragraph(corrected)
                for run in p.runs:
                    run.font.color.rgb = RGBColor(0, 150, 0)
                
                # Trennlinie
                doc.add_paragraph("-----------------------------")
        
        return doc

    def create_output_document(data_df, uploaded_file):
        """Kopiere die originale Präsentation und ersetze die Texte"""
        output_prs = Presentation(uploaded_file)

        # Wir erstellen ein Dictionary, um die Zuordnung von Folien und Texten zu speichern
        slide_texts = {}
        for _, row in data_df.iterrows():
            slide_num = row['slide_number']
            original_text = row['original_text']
            corrected_text = row['corrected_text']
            
            if slide_num not in slide_texts:
                slide_texts[slide_num] = []
            
            slide_texts[slide_num].append((original_text, corrected_text))
        
        # Für jede Folie in der Präsentation
        for slide_idx, slide in enumerate(output_prs.slides, 1):
            if slide_idx in slide_texts:
                for original_text, corrected_text in slide_texts[slide_idx]:
                    # Suche alle TextFrames in dieser Folie
                    for shape in slide.shapes:
                        if hasattr(shape, "text") and shape.text.strip() == original_text:
                            # Wenn der Text übereinstimmt, ersetze ihn
                            shape.text = corrected_text
        
        return output_prs

    # Hauptprogrammlogik
    if uploaded_file is not None:
        # Prüfe, ob bereits ein DataFrame mit Texten existiert oder erstelle ein neues
        if "powerpoint_texts" not in st.session_state:
            with st.spinner("Extrahiere Texte aus der PowerPoint-Datei..."):
                st.session_state.powerpoint_texts = extract_text_from_pptx(uploaded_file)
        
        df = st.session_state.powerpoint_texts
        
        # Zeige die Anzahl der gefundenen Texte an
        st.info(f"{len(df)} Textelemente in {df['slide_number'].nunique()} Folien gefunden.")
        
        # Selektiere nur ausstehende Texte zur Korrektur
        pending_df = df[df['status'] == 'ausstehend']
        
        if not pending_df.empty:
            col1, col2 = st.columns([1, 5])
            
            with col1:
                if st.button("Alle korrigieren"):
                    for idx, row in pending_df.iterrows():
                        with st.spinner(f"Korrigiere Text {idx+1} von {len(pending_df)}..."):
                            original_text = row['original_text']
                            corrected_text = check_text_with_gpt(original_text)
                            df.at[idx, 'corrected_text'] = corrected_text
                            df.at[idx, 'status'] = 'korrigiert'
                    
                    st.session_state.powerpoint_texts = df
                    st.success("Alle Texte wurden korrigiert!")
                    st.rerun()
            
            with col2:
                # Zeige den Fortschritt an
                progress = (len(df) - len(pending_df)) / len(df) if len(df) > 0 else 0
                st.progress(progress)
                st.caption(f"{len(df) - len(pending_df)} von {len(df)} Texten korrigiert ({progress:.0%})")
        
        # Zeige die Texte und ihre Korrekturen an
        if not df.empty:
            # Nur zeigen, wenn mindestens ein Text korrigiert wurde
            corrected_df = df[df['status'] == 'korrigiert']
            if not corrected_df.empty:
                st.subheader("Korrigierte Texte:")
                
                # Gruppiere nach Foliennummer für bessere Übersicht
                for slide_num in sorted(corrected_df['slide_number'].unique()):
                    slide_df = corrected_df[corrected_df['slide_number'] == slide_num]
                    
                    with st.expander(f"Folie {slide_num} ({len(slide_df)} Texte)"):
                        for idx, row in slide_df.iterrows():
                            st.markdown(f"**Text {idx+1}:**")
                            
                            # Zeige die Texte nur an, wenn sie unterschiedlich sind
                            original = row['original_text']
                            corrected = row['corrected_text']
                            
                            if original != corrected:
                                st.markdown("**Original:**")
                                st.text(original)
                                st.markdown("**Korrigiert:**")
                                st.text(corrected)
                                # HTML-Diff anzeigen
                                st.markdown(generate_diff_html(original, corrected), unsafe_allow_html=True)
                            else:
                                st.info("Keine Änderungen notwendig.")
                            
                            st.markdown("---")
                
                # Herunterladen der korrigierten Dokumente
                col1, col2 = st.columns(2)
                
                with col1:
                    # Word-Bericht herunterladen
                    summary_doc = create_summary_document(corrected_df)
                    
                    # Word-Dokument in BytesIO-Objekt speichern
                    doc_bytes = BytesIO()
                    summary_doc.save(doc_bytes)
                    doc_bytes.seek(0)
                    
                    st.download_button(
                        label="Korrekturbericht herunterladen (DOCX)",
                        data=doc_bytes,
                        file_name="powerpoint-korrekturbericht.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                
                with col2:
                    # Korrigierte PowerPoint herunterladen
                    output_prs = create_output_document(df, uploaded_file)
                    
                    # PowerPoint in BytesIO-Objekt speichern
                    pptx_bytes = BytesIO()
                    output_prs.save(pptx_bytes)
                    pptx_bytes.seek(0)
                    
                    st.download_button(
                        label="Korrigierte Präsentation herunterladen (PPTX)",
                        data=pptx_bytes,
                        file_name="korrigierte-praesentation.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )
    else:
        # Zeige Beispieltext und Anweisungen
        st.info("Bitte lade eine PowerPoint-Datei hoch, um zu beginnen.")
        
        # Beispiel für den Benutzer
        st.markdown("""
        ### So funktioniert es:
        
        1. Lade deine PowerPoint-Datei im Seitenmenü hoch
        2. Wähle den gewünschten Modus (Editor oder Übersetzer)
        3. Wähle die Zielsprache
        4. Klicke auf "Alle korrigieren", um die KI die Texte bearbeiten zu lassen
        5. Überprüfe die Änderungen 
        6. Lade die korrigierte Präsentation oder den Korrekturbericht herunter
        
        Die App erkennt automatisch Texte in deiner Präsentation und ignoriert dabei Kopf- und Fußzeilen sowie Foliennummern.
        """)
        
if __name__ == "__main__":
    powerpoint_app()