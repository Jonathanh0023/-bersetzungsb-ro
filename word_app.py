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
    st.title("BonsAI Word Sprachprüfung und Korrektur")

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
        
        # File Uploader für DOCX
        uploaded_file = st.file_uploader("Word-Datei hochladen", type=["docx"])
        
        if uploaded_file is not None:
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
                    "Dänisch", "Bulgarisch", "Holländisch", "Ungarisch", "Polnisch", "Schwedisch"],
            index=0
        )
        
        # Zusätzlicher Kontext
        additional_context = st.text_area(
            "Zusätzlicher Kontext (optional)",
            help="Hier können zusätzliche Informationen oder Anweisungen für die KI eingeben werden, "
                 "z.B. dass es sich um ein Transkript handelt oder Stil-Richtlinien oder Branchenkontext, etc...",
            placeholder="Beispiel: Dies ist ein Transkript einer Sitzung. "
                      "Bitte korrigiere die Grammatik und die Rechtschreibung",
            max_chars=1000
        )

    # Prüfe, ob ein API-Key vorliegt
    if not api_key:
        st.warning("Bitte gib einen OpenAI API Key ein, um fortzufahren.")
        st.stop()

    # OpenAI Client initialisieren
    client = OpenAI(api_key=api_key)

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
    def check_text_with_gpt(text: str) -> str:
        try:
            # Füge diese Zeile zu allen Templates hinzu (sowohl editor als auch translator)
            table_handling = ("\nSpecial formatting:\n"
                             "- Table cells are separated by ' | '\n"
                             "- Each table row is on a new line\n"
                             "- Keep the table structure intact (do not remove or add separators)\n"
                             "- Preserve empty lines before and after tables\n"
                             "- Only correct/translate the content within cells\n")
            
            # Prompt-Templates je nach Zielsprache
            editor_templates = {
                "US English": (
                    "You are a professional editor specializing in US English. "
                    "Please review and correct the following text, focusing on:\n"
                    "1. Grammar and syntax according to US English rules\n"
                    "2. Spelling using US English conventions\n"
                    "3. Punctuation following US style guides\n"
                    "4. Improving phrasing while maintaining the original meaning\n"
                    "5. Ensuring consistency with US English vocabulary and expressions\n\n"
                    "Important: Preserve all formatting and line breaks. "
                    "Only correct the language aspects mentioned above.\n\n"
                    "If no correction is needed, respond with a single hyphen '-'."
                    + table_handling
                ),
                "UK English": (
                    "You are a professional editor specializing in British English. "
                    "Please review and correct the following text, focusing on:\n"
                    "1. Grammar and syntax according to British English rules\n"
                    "2. Spelling using British English conventions\n"
                    "3. Punctuation following UK style guides\n"
                    "4. Improving phrasing while maintaining the original meaning\n"
                    "5. Ensuring consistency with British English vocabulary and expressions\n\n"
                    "Important: Preserve all formatting and line breaks. "
                    "Only correct the language aspects mentioned above.\n\n"
                    "If no correction is needed, respond with a single hyphen '-'."
                    + table_handling
                ),
                "Deutsch": (
                    "Du bist ein professioneller Lektor für die deutsche Sprache. "
                    "Bitte überprüfe und korrigiere den folgenden Text mit Fokus auf:\n"
                    "1. Grammatik und Syntax\n"
                    "2. Rechtschreibung nach aktueller deutscher Rechtschreibreform\n"
                    "3. Zeichensetzung nach deutschen Rechtschreibregeln\n"
                    "4. Verbesserung der Formulierungen unter Beibehaltung der ursprünglichen Bedeutung\n"
                    "5. Einheitliche deutsche Ausdrucksweise\n\n"
                    "Wichtig: Bewahre alle Formatierungen und Zeilenumbrüche. "
                    "Korrigiere ausschließlich die oben genannten sprachlichen Aspekte.\n\n"
                    "Falls der Text keine Korrektur benötigt, antworte mit '-'."
                    + table_handling
                ),
                "Französisch": (
                    "Tu es un éditeur professionnel spécialisé en français. "
                    "Examine et corrige le texte suivant en te concentrant sur:\n"
                    "1. La grammaire et la syntaxe selon les règles du français\n"
                    "2. L'orthographe selon les conventions françaises actuelles\n"
                    "3. La ponctuation selon les règles françaises\n"
                    "4. L'amélioration des formulations tout en conservant le sens original\n"
                    "5. L'assurance d'une expression française cohérente et élégante\n\n"
                    "Important: Conserve tous les formatages et sauts de ligne. "
                    "Corrige uniquement les aspects linguistiques mentionnés ci-dessus.\n\n"
                    "Si le texte est trop court ou ne nécessite aucune correction, réponds avec un simple tiret '-'."
                    + table_handling
                ),
                "Italienisch": (
                    "Sei un editor professionale specializzato in italiano. Esamina e correggi il seguente testo, concentrandoti su:\n"
                    "1. Grammatica e sintassi secondo le regole dell'italiano\n"
                    "2. Ortografia secondo le convenzioni italiane attuali\n"
                    "3. Punteggiatura secondo le regole italiane\n"
                    "4. Miglioramento delle formulazioni mantenendo il significato originale\n"
                    "5. Garanzia di un'espressione italiana coerente ed elegante\n\n"
                    "Importante: Mantieni tutta la formattazione, le interruzioni di riga e lo stile del testo. "
                    "Correggi solo gli aspetti linguistici menzionati sopra.\n\n"
                    "Se il testo è troppo breve o non necessita correzioni, rispondi con un singolo trattino '-'"
                    + table_handling
                ),
                "Dänisch": (
                    "Du er en professionel redaktør specialiseret i dansk. Gennemgå og ret følgende tekst med fokus på:\n"
                    "1. Grammatik og syntaks efter danske regler\n"
                    "2. Stavning efter danske konventioner\n"
                    "3. Tegnsætning efter danske regler\n"
                    "4. Forbedring af formuleringer med bibeholdelse af den oprindelige betydning\n"
                    "5. Sikring af et konsistent dansk sprog\n\n"
                    "Vigtigt: Bevar al formatering, linjeskift og tekststil. "
                    "Ret kun de sproglige aspekter nævnt ovenfor.\n\n"
                    "Hvis teksten er for kort eller ikke kræver rettelser, svar med en enkelt bindestreg '-'"
                    + table_handling
                ),
                "Bulgarisch": (
                    "Вие сте професионален редактор, специализиран в български език. Прегледайте и коригирайте следния текст, фокусирайки се върху:\n"
                    "1. Граматика и синтаксис според правилата на българския език\n"
                    "2. Правопис според българските конвенции\n"
                    "3. Пунктуация според българските правила\n"
                    "4. Подобряване на формулировките при запазване на оригиналния смисъл\n"
                    "5. Осигуряване на последователен български изказ\n\n"
                    "Важно: Запазете цялото форматиране, преходи между редовете и стил на текста. "
                    "Коригирайте само езиковите аспекти, посочени по-горе.\n\n"
                    "Ако текстът е твърде кратък или не се нуждае от корекции, отговорете с единично тире '-'"
                    + table_handling
                ),
                "Holländisch": (
                    "Je bent een professionele redacteur gespecialiseerd in het Nederlands. Controleer en corrigeer de volgende tekst, met focus op:\n"
                    "1. Grammatica en syntaxis volgens Nederlandse regels\n"
                    "2. Spelling volgens Nederlandse conventies\n"
                    "3. Interpunctie volgens Nederlandse regels\n"
                    "4. Verbetering van formuleringen met behoud van de oorspronkelijke betekenis\n"
                    "5. Zorgen voor consistent Nederlands taalgebruik\n\n"
                    "Belangrijk: Behoud alle opmaak, regeleinden en tekststijl. "
                    "Corrigeer alleen de hierboven genoemde taalaspecten.\n\n"
                    "Als de tekst te kort is of geen correcties nodig heeft, antwoord dan met een enkel streepje '-'"
                    + table_handling
                ),
                "Ungarisch": (
                    "Ön egy magyar nyelvre szakosodott professzionális szerkesztő. Kérjük, ellenőrizze és javítsa a következő szöveget, koncentrálva:\n"
                    "1. Nyelvtan és mondattan a magyar szabályok szerint\n"
                    "2. Helyesírás a magyar konvenciók szerint\n"
                    "3. Központozás a magyar szabályok szerint\n"
                    "4. Megfogalmazások javítása az eredeti jelentés megtartásával\n"
                    "5. Következetes magyar nyelvhasználat biztosítása\n\n"
                    "Fontos: Őrizze meg az összes formázást, sortörést és szövegstílust. "
                    "Csak a fent említett nyelvi szempontokat javítsa.\n\n"
                    "Ha a szöveg túl rövid vagy nem igényel javítást, válaszoljon egyetlen kötőjellel '-'"
                    + table_handling
                ),
                "Polnisch": (
                    "Jesteś profesjonalnym redaktorem specjalizującym się w języku polskim. Przejrzyj i popraw następujący tekst, skupiając się na:\n"
                    "1. Gramatyce i składni według zasad języka polskiego\n"
                    "2. Pisowni zgodnej z polskimi konwencjami\n"
                    "3. Interpunkcji według polskich zasad\n"
                    "4. Poprawie sformułowań przy zachowaniu oryginalnego znaczenia\n"
                    "5. Zapewnieniu spójnego języka polskiego\n\n"
                    "Ważne: Zachowaj całe formatowanie, podziały wierszy i styl tekstu. "
                    "Poprawiaj tylko wymienione wyżej aspekty językowe.\n\n"
                    "Jeśli tekst jest zbyt krótki lub nie wymaga poprawek, odpowiedz pojedynczym myślnikiem '-'"
                    + table_handling
                ),
                "Schwedisch": (
                    "Du är en professionell redaktör specialiserad på svenska. "
                    "Granska och korrigera följande text med fokus på:\n"
                    "1. Grammatik och syntax enligt svenska regler\n"
                    "2. Stavning enligt svenska konventioner\n"
                    "3. Interpunktion enligt svenska riktlinjer\n"
                    "4. Förbättring av formuleringar samtidigt som du bevarar textens ursprungliga betydelse\n"
                    "5. Säkerställ att svenskt vokabulär och uttryck används konsekvent\n\n"
                    "Viktigt: Bevara all formatering och radbrytningar. "
                    "Korrigera endast de språkaspekter som nämns ovan.\n\n"
                    "Om ingen korrigering behövs, svara med ett enda bindestreck '-'"
                    + table_handling
                )
            }

            translator_templates = {
                "US English": (
                    "You are a professional translator. Translate the following text into US English.\n\n"
                    "Important guidelines:\n"
                    "1. Maintain the original meaning and tone\n"
                    "2. Use US English spelling and expressions\n"
                    "3. Preserve all formatting, line breaks, and text styling\n"
                    "4. Ensure natural, fluent language appropriate for the context\n"
                    "5. Keep any technical terms or proper names as they are unless there's a standard English equivalent\n\n"
                    "If the text is too short or is already in English, respond with a single hyphen '-'"
                    + table_handling
                ),
                "UK English": (
                    "You are a professional translator. Translate the following text into British English.\n\n"
                    "Important guidelines:\n"
                    "1. Maintain the original meaning and tone\n"
                    "2. Use British English spelling and expressions\n"
                    "3. Preserve all formatting, line breaks, and text styling\n"
                    "4. Ensure natural, fluent language appropriate for the context\n"
                    "5. Keep any technical terms or proper names as they are unless there's a standard English equivalent\n\n"
                    "If the text is too short or is already in English, respond with a single hyphen '-'"
                    + table_handling
                ),
                "Deutsch": (
                    "Du bist ein professioneller Übersetzer. Übersetze den folgenden Text ins Deutsche.\n\n"
                    "Wichtige Richtlinien:\n"
                    "1. Bewahre die ursprüngliche Bedeutung und den Ton\n"
                    "2. Verwende natürliches, zeitgemäßes Deutsch\n"
                    "3. Behalte alle Formatierungen und Zeilenumbrüche bei\n"
                    "4. Stelle eine flüssige, dem Kontext angemessene Sprache sicher\n"
                    "5. Behalte Fachbegriffe oder Eigennamen bei, außer es gibt eine standardisierte deutsche Entsprechung\n\n"
                    "Falls der Text zu kurz ist oder bereits auf Deutsch ist, antworte mit einem einzelnen Bindestrich '-'"
                    + table_handling
                ),
                "Französisch": (
                    "Tu es un traducteur professionnel. Traduis le texte suivant en français.\n\n"
                    "Directives importantes:\n"
                    "1. Conserve le sens et le ton d'origine\n"
                    "2. Utilise un français naturel et contemporain\n"
                    "3. Préserve tous les formatages et sauts de ligne\n"
                    "4. Assure un langage fluide et approprié au contexte\n"
                    "5. Conserve les termes techniques ou noms propres sauf s'il existe un équivalent français standard\n\n"
                    "Si le texte est trop court ou déjà en français, réponds avec un simple tiret '-'"
                    + table_handling
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
                    + table_handling
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
                    + table_handling
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
                    + table_handling
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
                    + table_handling
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
                    + table_handling
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
                    + table_handling
                ),
                "Schwedisch": (
                    "Du är en professionell översättare. Översätt följande text till svenska.\n\n"
                    "Viktiga riktlinjer:\n"
                    "1. Bevara textens ursprungliga betydelse och ton\n"
                    "2. Använd en naturlig, modern svenska\n"
                    "3. Bevara all formatering, radbrytningar och textstil\n"
                    "4. Se till att språket flyter naturligt och är anpassat efter kontexten\n"
                    "5. Behåll tekniska termer eller egennamn, om det inte finns en standardiserad svensk motsvarighet\n\n"
                    "Om texten är för kort eller redan på svenska, svara med ett enda bindestreck '-'"
                    + table_handling
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
    # 4) Haupt-Logik
    # --------------------------------------
    if uploaded_file is not None:
        # Warten, bis der Nutzer den gewünschten Modus (Editor/Übersetzer) bestätigt
        if st.button("Prozess starten"):
            st.session_state.corrections_df = extract_text_from_docx(uploaded_file)
            
            total_pages = len(st.session_state.corrections_df)
            st.info(f"Dokument wurde in {total_pages} Seiten unterteilt.")
            
            # Fortschrittsanzeige
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # GPT-Verarbeitung für jede Seite (abhängig vom ausgewählten Modus)
            for idx, row in st.session_state.corrections_df.iterrows():
                status_text.text(f"{mode} - Verarbeite Seite {idx+1} von {total_pages} ...")
                progress_bar.progress((idx + 1) / total_pages)
                
                corrected = check_text_with_gpt(row['original_text'])
                st.session_state.corrections_df.at[idx, 'corrected_text'] = corrected
            
            # Fortschritts-Elemente entfernen
            progress_bar.empty()
            status_text.empty()
            
            st.success(f"{mode} abgeschlossen! {total_pages} Seiten wurden verarbeitet.")
        
        # Darstellung der Korrekturen (angepasst für Seiten)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.header("Originaltext")
        with col2:
            st.header("Korrigierter Text")
        with col3:
            st.header("Änderungen")
        
        for idx, row in st.session_state.get('corrections_df', pd.DataFrame()).iterrows():
            col1, col2, col3 = st.columns(3)
            
            # Original
            with col1:
                st.text_area(
                    f"Seite {row['page_number']} (Original)",
                    row['original_text'],
                    key=f"original_{idx}",
                    disabled=True,
                    height=400  # Größeres Textfeld für Seiten
                )
            
            # Korrigiert
            with col2:
                corrected_text = st.text_area(
                    f"Seite {row['page_number']} (Korrigiert)",
                    row['corrected_text'],
                    key=f"corrected_{idx}"
                )
                st.session_state.corrections_df.at[idx, 'corrected_text'] = corrected_text
            
            # Diff
            with col3:
                diff_html = create_diff_html(row['original_text'], row['corrected_text'])
                st.markdown(diff_html, unsafe_allow_html=True)

        # --------------------------------------
        # 5) Funktion zum Erstellen eines Word-Dokuments mit Übersicht
        # --------------------------------------
        def create_word_document():
            def clean_text_for_word(text):
                if not isinstance(text, str):
                    return ""
                # Entferne nicht druckbare Zeichen, behalte Zeilenumbrüche
                text = "".join(ch for ch in text if ch == "\n" or (ord(ch) >= 32 and ord(ch) != 127))
                # Ersetze zu viele aufeinanderfolgende Zeilenumbrüche
                text = re.sub(r'\n{3,}', '\n\n', text)
                return text

            def create_word_diff(original, corrected):
                if corrected == '-' or original == corrected:
                    return "Keine Änderungen"
                
                def split_into_words(txt):
                    lines = txt.split('\n')
                    result = []
                    for line in lines:
                        # Wörter in der Zeile
                        result.extend(line.split())
                        # Markierung für Zeilenumbruch
                        result.append('\n')
                    return result[:-1]  # Letztes \n entfernen
                
                original_words = split_into_words(original)
                corrected_words = split_into_words(corrected)
                matcher = difflib.SequenceMatcher(None, original_words, corrected_words)
                
                result = []
                for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                    if tag == 'replace':
                        result.append(('delete', ' '.join(original_words[i1:i2])))
                        result.append(('insert', ' '.join(corrected_words[j1:j2])))
                    elif tag == 'delete':
                        result.append(('delete', ' '.join(original_words[i1:i2])))
                    elif tag == 'insert':
                        result.append(('insert', ' '.join(corrected_words[j1:j2])))
                    else:  # 'equal'
                        result.append(('equal', ' '.join(original_words[i1:i2])))
                return result

            try:
                doc = Document()
                doc.add_heading("Korrekturübersicht Word-Dokument", 0)
                
                # Tabelle mit 3 Spalten: Original, Korrigiert, Änderungen
                table = doc.add_table(rows=1, cols=3)
                table.style = "Table Grid"
                
                # Header
                hdr_cells = table.rows[0].cells
                hdr_cells[0].text = "Originaltext"
                hdr_cells[1].text = "Korrigierter Text"
                hdr_cells[2].text = "Änderungen"
                
                # Formatierung Header
                for cell in hdr_cells:
                    for paragraph in cell.paragraphs:
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        paragraph.runs[0].bold = True
                
                # Zeilen pro Seite
                for _, row in st.session_state.corrections_df.iterrows():
                    # Seiten-Titel
                    title_row = table.add_row()
                    title_cell = title_row.cells[0]
                    title_cell.merge(title_row.cells[-1])
                    title_cell.text = f"Seite {row['page_number']}"
                    # Inhalt
                    content_row = table.add_row()
                    c_cells = content_row.cells
                    
                    original_clean = clean_text_for_word(row['original_text'])
                    corrected_clean = clean_text_for_word(row['corrected_text'])
                    
                    c_cells[0].text = original_clean
                    c_cells[1].text = corrected_clean
                    
                    # Änderungen
                    diff_par = c_cells[2].paragraphs[0]
                    diff_result = create_word_diff(original_clean, corrected_clean)
                    
                    if isinstance(diff_result, str):
                        # "Keine Änderungen"
                        diff_par.add_run(diff_result)
                    else:
                        for diff_type, txt in diff_result:
                            if not txt.strip():
                                continue
                            
                            if diff_type == "delete":
                                run = diff_par.add_run(txt)
                                run.font.color.rgb = RGBColor(198, 40, 40)  # Rot
                                run.font.strike = True
                                diff_par.add_run(" ")
                            elif diff_type == "insert":
                                run = diff_par.add_run(txt)
                                run.font.color.rgb = RGBColor(46, 125, 50)  # Grün
                                diff_par.add_run(" ")
                            else:  # equal
                                run = diff_par.add_run(txt + " ")
                                
                # BytesIO für den Download
                doc_buffer = BytesIO()
                doc.save(doc_buffer)
                doc_buffer.seek(0)
                return doc_buffer
            except Exception as e:
                st.error(f"Fehler beim Erstellen des Word-Dokuments: {str(e)}")
                return None

        # --------------------------------------
        # 6) Download-Button für das generierte DOCX
        # --------------------------------------
        if st.button("Word-Dokument erstellen"):
            doc_buffer = create_word_document()
            if doc_buffer is not None:
                st.download_button(
                    label="Word-Dokument herunterladen",
                    data=doc_buffer,
                    file_name="word_korrekturen.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

# Die auskommentierten Zeilen am Ende müssen aktiv sein:
if __name__ == "__main__":
    word_app()

