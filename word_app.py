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
                    "Falls keine Korrektur nötig ist, antworte mit einem einzelnen Bindestrich '-'."
                    + table_handling
                ),
                "Französisch": (
                    "Tu es un correcteur professionnel spécialisé en français. "
                    "Examine et corrige le texte suivant en te concentrant sur:\n"
                    "1. Grammaire et syntaxe\n"
                    "2. Orthographe selon les règles actuelles du français\n"
                    "3. Ponctuation selon les règles françaises\n"
                    "4. Amélioration des formulations tout en conservant le sens original\n"
                    "5. Expression française cohérente\n\n"
                    "Important: Préserve tous les formatages et retours à la ligne. "
                    "Corrige uniquement les aspects linguistiques mentionnés ci-dessus.\n\n"
                    "Si aucune correction n'est nécessaire, réponds avec un simple tiret '-'."
                    + table_handling
                ),
                "Italienisch": (
                    "Sei un correttore professionale specializzato in italiano. "
                    "Esamina e correggi il seguente testo, concentrandoti su:\n"
                    "1. Grammatica e sintassi\n"
                    "2. Ortografia secondo le regole italiane attuali\n"
                    "3. Punteggiatura secondo le regole italiane\n"
                    "4. Miglioramento delle formulazioni mantenendo il significato originale\n"
                    "5. Espressione italiana coerente\n\n"
                    "Importante: Conserva tutta la formattazione e le interruzioni di riga. "
                    "Correggi solo gli aspetti linguistici menzionati sopra.\n\n"
                    "Se non è necessaria alcuna correzione, rispondi con un singolo trattino '-'."
                    + table_handling
                ),
                "Dänisch": (
                    "Du er en professionel redaktør specialiseret i dansk. "
                    "Gennemgå og ret følgende tekst med fokus på:\n"
                    "1. Grammatik og syntaks\n"
                    "2. Stavning efter danske regler\n"
                    "3. Tegnsætning efter danske regler\n"
                    "4. Forbedring af formuleringer med bibeholdelse af den oprindelige betydning\n"
                    "5. Konsistent dansk sprogbrug\n\n"
                    "Vigtigt: Bevar al formatering og linjeskift. "
                    "Ret kun de sproglige aspekter nævnt ovenfor.\n\n"
                    "Hvis ingen korrektion er nødvendig, svar med en enkelt bindestreg '-'."
                    + table_handling
                ),
                "Bulgarisch": (
                    "Вие сте професионален редактор, специализиран в български език. "
                    "Прегледайте и коригирайте следния текст, като се съсредоточите върху:\n"
                    "1. Граматика и синтаксис\n"
                    "2. Правопис според настоящите български правила\n"
                    "3. Пунктуация според българските правила\n"
                    "4. Подобряване на формулировките при запазване на оригиналния смисъл\n"
                    "5. Последователен български изказ\n\n"
                    "Важно: Запазете цялото форматиране и преходи между редовете. "
                    "Коригирайте само езиковите аспекти, посочени по-горе.\n\n"
                    "Ако не е необходима корекция, отговорете с единично тире '-'."
                    + table_handling
                ),
                "Holländisch": (
                    "Je bent een professionele redacteur gespecialiseerd in het Nederlands. "
                    "Controleer en corrigeer de volgende tekst, met focus op:\n"
                    "1. Grammatica en syntaxis\n"
                    "2. Spelling volgens de huidige Nederlandse regels\n"
                    "3. Interpunctie volgens Nederlandse regels\n"
                    "4. Verbetering van formuleringen met behoud van de oorspronkelijke betekenis\n"
                    "5. Consequent Nederlands taalgebruik\n\n"
                    "Belangrijk: Behoud alle opmaak en regeleinden. "
                    "Corrigeer alleen de hierboven genoemde taalaspecten.\n\n"
                    "Als geen correctie nodig is, antwoord dan met een enkel streepje '-'."
                    + table_handling
                ),
                "Ungarisch": (
                    "Ön egy magyar nyelvre szakosodott professzionális szerkesztő. "
                    "Kérjük, ellenőrizze és javítsa a következő szöveget, koncentrálva:\n"
                    "1. Nyelvtan és mondattan\n"
                    "2. Helyesírás a jelenlegi magyar szabályok szerint\n"
                    "3. Központozás a magyar szabályok szerint\n"
                    "4. Megfogalmazások javítása az eredeti jelentés megtartásával\n"
                    "5. Következetes magyar nyelvhasználat\n\n"
                    "Fontos: Őrizze meg az összes formázást és sortörést. "
                    "Csak a fent említett nyelvi szempontokat javítsa.\n\n"
                    "Ha nincs szükség javításra, válaszoljon egyetlen kötőjellel '-'."
                    + table_handling
                ),
                "Polnisch": (
                    "Jesteś profesjonalnym redaktorem specjalizującym się w języku polskim. "
                    "Przejrzyj i popraw następujący tekst, skupiając się na:\n"
                    "1. Gramatyce i składni\n"
                    "2. Pisowni według aktualnych zasad języka polskiego\n"
                    "3. Interpunkcji według polskich zasad\n"
                    "4. Poprawie sformułowań przy zachowaniu oryginalnego znaczenia\n"
                    "5. Spójnym polskim języku\n\n"
                    "Ważne: Zachowaj całe formatowanie i podziały wierszy. "
                    "Poprawiaj tylko wymienione wyżej aspekty językowe.\n\n"
                    "Jeśli nie jest potrzebna żadna korekta, odpowiedz pojedynczym myślnikiem '-'."
                    + table_handling
                ),
                "Schwedisch": (
                    "Du är en professionell redaktör specialiserad på svenska. "
                    "Granska och korrigera följande text med fokus på:\n"
                    "1. Grammatik och syntax\n"
                    "2. Stavning enligt aktuella svenska regler\n"
                    "3. Skiljetecken enligt svenska regler\n"
                    "4. Förbättring av formuleringar med bibehållande av den ursprungliga meningen\n"
                    "5. Konsekvent svenskt språkbruk\n\n"
                    "Viktigt: Bevara all formatering och radbrytningar. "
                    "Korrigera endast de språkliga aspekter som nämns ovan.\n\n"
                    "Om ingen korrigering behövs, svara med ett enda bindestreck '-'."
                    + table_handling
                )
            }
            
            translator_templates = {
                "US English": (
                    "You are a professional translator. Translate the following text into US English.\n\n"
                    "Important guidelines:\n"
                    "1. Maintain the original meaning and tone\n"
                    "2. Use US English spelling and expressions\n"
                    "3. Preserve all formatting and line breaks\n"
                    "4. Ensure natural, fluent language appropriate for the context\n"
                    "5. Keep any technical terms or proper names as they are unless there's a standard English equivalent\n\n"
                    "If the text is too short or is already in English, respond with a single hyphen '-'."
                    + table_handling
                ),
                "UK English": (
                    "You are a professional translator. Translate the following text into UK English.\n\n"
                    "Important guidelines:\n"
                    "1. Maintain the original meaning and tone\n"
                    "2. Use UK English spelling and expressions\n"
                    "3. Preserve all formatting and line breaks\n"
                    "4. Ensure natural, fluent language appropriate for the context\n"
                    "5. Keep any technical terms or proper names as they are unless there's a standard English equivalent\n\n"
                    "If the text is too short or is already in English, respond with a single hyphen '-'."
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
                    "Falls der Text zu kurz ist oder bereits auf Deutsch ist, antworte mit einem einzelnen Bindestrich '-'."
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
                    "Si le texte est trop court ou déjà en français, réponds avec un simple tiret '-'."
                    + table_handling
                ),
                "Italienisch": (
                    "Sei un traduttore professionista. Traduci il seguente testo in italiano.\n\n"
                    "Linee guida importanti:\n"
                    "1. Mantieni il significato e il tono originale\n"
                    "2. Usa un italiano naturale e contemporaneo\n"
                    "3. Preserva tutta la formattazione e le interruzioni di riga\n"
                    "4. Assicura un linguaggio fluido e appropriato al contesto\n"
                    "5. Mantieni i termini tecnici o i nomi propri a meno che non esista un equivalente italiano standard\n\n"
                    "Se il testo è troppo breve o è già in italiano, rispondi con un singolo trattino '-'."
                    + table_handling
                ),
                "Dänisch": (
                    "Du er en professionel oversætter. Oversæt følgende tekst til dansk.\n\n"
                    "Vigtige retningslinjer:\n"
                    "1. Bevar den oprindelige betydning og tone\n"
                    "2. Brug naturligt, moderne dansk\n"
                    "3. Bevar al formatering og linjeskift\n"
                    "4. Sikre et flydende sprog passende til konteksten\n"
                    "5. Behold fagudtryk eller egennavne, medmindre der findes en standard dansk ækvivalent\n\n"
                    "Hvis teksten er for kort eller allerede er på dansk, svar med en enkelt bindestreg '-'."
                    + table_handling
                ),
                "Bulgarisch": (
                    "Вие сте професионален преводач. Преведете следния текст на български.\n\n"
                    "Важни насоки:\n"
                    "1. Запазете оригиналното значение и тон\n"
                    "2. Използвайте естествен, съвременен български език\n"
                    "3. Запазете цялото форматиране и преходите между редовете\n"
                    "4. Осигурете плавен език, подходящ за контекста\n"
                    "5. Запазете технически термини или собствени имена, освен ако няма стандартен български еквивалент\n\n"
                    "Ако текстът е твърде кратък или вече е на български, отговорете с единично тире '-'."
                    + table_handling
                ),
                "Holländisch": (
                    "Je bent een professionele vertaler. Vertaal de volgende tekst naar het Nederlands.\n\n"
                    "Belangrijke richtlijnen:\n"
                    "1. Behoud de oorspronkelijke betekenis en toon\n"
                    "2. Gebruik natuurlijk, hedendaags Nederlands\n"
                    "3. Behoud alle opmaak en regeleinden\n"
                    "4. Zorg voor vloeiende taal die past bij de context\n"
                    "5. Behoud technische termen of eigennamen, tenzij er een standaard Nederlands equivalent bestaat\n\n"
                    "Als de tekst te kort is of al in het Nederlands is, antwoord dan met een enkel streepje '-'."
                    + table_handling
                ),
                "Ungarisch": (
                    "Ön professzionális fordító. Fordítsa le a következő szöveget magyarra.\n\n"
                    "Fontos irányelvek:\n"
                    "1. Tartsa meg az eredeti jelentést és hangnemet\n"
                    "2. Használjon természetes, modern magyar nyelvet\n"
                    "3. Őrizze meg az összes formázást és sortörést\n"
                    "4. Biztosítson folyékony, a kontextushoz illő nyelvet\n"
                    "5. Tartsa meg a szakkifejezéseket vagy tulajdonneveket, hacsak nincs standard magyar megfelelő\n\n"
                    "Ha a szöveg túl rövid vagy már magyar nyelvű, válaszoljon egyetlen kötőjellel '-'."
                    + table_handling
                ),
                "Polnisch": (
                    "Jesteś profesjonalnym tłumaczem. Przetłumacz poniższy tekst na język polski.\n\n"
                    "Ważne wytyczne:\n"
                    "1. Zachowaj oryginalne znaczenie i ton\n"
                    "2. Używaj naturalnego, współczesnego języka polskiego\n"
                    "3. Zachowaj całe formatowanie i podziały wierszy\n"
                    "4. Zapewnij płynny język odpowiedni do kontekstu\n"
                    "5. Zachowaj terminy techniczne lub nazwy własne, chyba że istnieje standardowy polski odpowiednik\n\n"
                    "Jeśli tekst jest zbyt krótki lub jest już w języku polskim, odpowiedz pojedynczym myślnikiem '-'."
                    + table_handling
                ),
                "Schwedisch": (
                    "Du är en professionell översättare. Översätt följande text till svenska.\n\n"
                    "Viktiga riktlinjer:\n"
                    "1. Behåll den ursprungliga innebörden och tonen\n"
                    "2. Använd naturlig, modern svenska\n"
                    "3. Bevara all formatering och radbrytningar\n"
                    "4. Säkerställ ett flytande språk som är lämpligt för sammanhanget\n"
                    "5. Behåll tekniska termer eller egennamn såvida det inte finns en standard svensk motsvarighet\n\n"
                    "Om texten är för kort eller redan är på svenska, svara med ett enda bindestreck '-'."
                    + table_handling
                )
            }

            # Wähle den richtigen Systemprompt basierend auf dem Modus und der Zielsprache
            templates = editor_templates if mode == "Editor" else translator_templates
            system_prompt = templates.get(target_language, templates["US English"])
            
            # Füge ggf. zusätzlichen Kontext hinzu
            if additional_context and additional_context.strip():
                system_prompt += f"\n\nAdditional context: {additional_context}"

            # GPT-Anfrage durchführen
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
            
            # Extrahiere den bearbeiteten Text
            processed_text = response.choices[0].message.content.strip()
            
            # Wenn die Antwort nur ein "-" ist, behalte den ursprünglichen Text bei
            if processed_text == "-":
                processed_text = text
                
            return processed_text
            
        except Exception as e:
            st.error(f"Fehler bei der GPT-Anfrage: {str(e)}")
            return text  # Bei Fehlern Originaltext zurückgeben