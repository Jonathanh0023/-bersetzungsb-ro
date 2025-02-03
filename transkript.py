import os
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.shared import Inches
import streamlit as st
import replicate
import requests
import tempfile
import smtplib
from email.message import EmailMessage
import math
import io

def send_email_notification(receiver_emails, file_name, download_link):
    sender_email = "jonathan.heeckt@bonsai-research.com" 
    password = "pjtpqvtmdkrhfgvk"  

    # Send the email to each receiver
    for receiver_email in receiver_emails:
        msg = EmailMessage()
        msg['Subject'] = 'Transkription abgeschlossen'
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg.set_content(f"Moin,\n\nDie Transkription für '{file_name}' ist abgeschlossen und kann hier heruntergeladen werden: {download_link}\n\nLG Jonathan")

        with smtplib.SMTP('smtp.office365.com', 587) as smtp:
            smtp.starttls()
            smtp.login(sender_email, password)
            smtp.send_message(msg)


# Constants for styles and files
BASE_STYLE = 'Normal'
FONT_NAME = 'UCity'
FONT_SIZE = 12
SPEAKER_ZERO_COLOR = (245, 0, 126)     # Bonsai Pink
SPEAKER_ONE_COLOR = (0, 0, 0)          # Black
SPEAKER_TWO_COLOR = (0, 0, 255)        # Blue
SPEAKER_THREE_COLOR = (0, 255, 0)      # Green
SPEAKER_FOUR_COLOR = (255, 0, 0)       # Red
SPEAKER_FIVE_COLOR = (255, 255, 0)     # Yellow
SPEAKER_SIX_COLOR = (255, 0, 255)      # Magenta
SPEAKER_SEVEN_COLOR = (0, 255, 255)    # Cyan
SPEAKER_EIGHT_COLOR = (128, 0, 0)      # Maroon
SPEAKER_NINE_COLOR = (0, 128, 0)       # Dark Green
SPEAKER_TEN_COLOR = (0, 0, 128)        # Navy
TRANSCRIPT_FILENAME = "Transkript.docx"

class StyleError(Exception):
    pass

class SegmentKeyError(Exception):
    pass

class TimestampError(Exception):
    pass

class AudioProcessError(Exception):
    pass

def get_styles(doc, name, font_size=FONT_SIZE, color_rgb=(0, 0, 0), base_style='Normal', font_name='UCity'):
    """Creates a new Word style with provided parameters."""
    try:
        style = doc.styles.add_style(name, doc.styles[base_style].type)
        
        # Explicitly set the font to UCity for this style
        style.font.name = font_name
        style.font.size = Pt(font_size)
        style.font.color.rgb = RGBColor(*color_rgb)
        style.paragraph_format.left_indent = Inches(0.1)
        style.paragraph_format.right_indent = Inches(0.1)
        style.paragraph_format.space_after = Inches(0.1)
        style.paragraph_format.space_before = Inches(0.0)
        
        return style
    except Exception as e:
        raise StyleError(f'Error while generating style: {e}')


def format_json_to_chat(segments, output_file_path, speaker_names=None):   
    """Transforms a JSON object into a formatted conversation saved as a Word document."""
    doc = Document()
    font = doc.styles['Normal'].font
    font.name = 'UCity'

    # Get styles for each speaker
    speaker_styles = {
        "SPEAKER_00": get_styles(doc, 'Speaker0', color_rgb=SPEAKER_ZERO_COLOR),
        "SPEAKER_01": get_styles(doc, 'Speaker1', color_rgb=SPEAKER_ONE_COLOR),
        "SPEAKER_02": get_styles(doc, 'Speaker2', color_rgb=SPEAKER_TWO_COLOR),
        "SPEAKER_03": get_styles(doc, 'Speaker3', color_rgb=SPEAKER_THREE_COLOR),
        "SPEAKER_04": get_styles(doc, 'Speaker4', color_rgb=SPEAKER_FOUR_COLOR),
        "SPEAKER_05": get_styles(doc, 'Speaker5', color_rgb=SPEAKER_FIVE_COLOR),
        "SPEAKER_06": get_styles(doc, 'Speaker6', color_rgb=SPEAKER_SIX_COLOR),
        "SPEAKER_07": get_styles(doc, 'Speaker7', color_rgb=SPEAKER_SEVEN_COLOR),
        "SPEAKER_08": get_styles(doc, 'Speaker8', color_rgb=SPEAKER_EIGHT_COLOR),
        "SPEAKER_09": get_styles(doc, 'Speaker9', color_rgb=SPEAKER_NINE_COLOR),
        "SPEAKER_10": get_styles(doc, 'Speaker10', color_rgb=SPEAKER_TEN_COLOR)
    }

    last_speaker = None

    for segment in segments:
        try: 
            original_speaker_label = segment['speaker']  # Save the original label
            if speaker_names and original_speaker_label in speaker_names:
                display_speaker_name = speaker_names[original_speaker_label]  # This is the name to be displayed in the doc
            else:
                display_speaker_name = original_speaker_label

            text = segment['text']
            formatted_timestamp = format_segment_time(segment)
            
            # If speaker changes, add an additional line break
            if last_speaker and last_speaker != display_speaker_name:
                doc.add_paragraph()

            # Add speaker's name and timestamp in bold
            p = doc.add_paragraph()
            p.add_run(f"{display_speaker_name} {formatted_timestamp}: ").bold = True
            p.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

            # Add speaker's text on the next line
            p = doc.add_paragraph(text, style=speaker_styles.get(original_speaker_label, 'Normal'))
            p.alignment = WD_PARAGRAPH_ALIGNMENT.JUSTIFY
            
            last_speaker = display_speaker_name
        except KeyError as e:
            raise SegmentKeyError(f'Missing key in segment: {e}')

    doc.save(output_file_path)

def format_segment_time(segment):
    """Transforms a start and end time into timestamp format [MM:SS-MM:SS]."""
    try:
        start_time = float(segment['start'])
        end_time = float(segment['end'])
        start_minutes, start_seconds = divmod(int(start_time), 60)
        end_minutes, end_seconds = divmod(int(end_time), 60)
        return f"[{start_minutes:02}:{start_seconds:02}-{end_minutes:02}:{end_seconds:02}]"
    except ValueError as e:
        raise TimestampError(f'Error while parsing time values: {e}')
    
def upload_to_hosting_service(uploaded_file):
    """
    Uploads the file to tmpfiles.org and returns the direct URL to the file.
    """
    # The API endpoint for uploading files
    upload_url = "https://tmpfiles.org/api/v1/upload"
    
    # Post the file to the endpoint
    response = requests.post(upload_url, files={'file': uploaded_file})
    
    # Check if the upload was successful
    response.raise_for_status()
    
    # Parse the JSON response to get the direct file URL
    response_data = response.json()
    file_url = response_data.get('data', {}).get('url')
    
    if not file_url:
        raise ValueError(f"Failed to retrieve the file URL from the tmpfiles response. Full response: {response_data}")
    
    # Construct the direct download link
    direct_download_link = file_url.replace("https://tmpfiles.org/", "https://tmpfiles.org/dl/")
    
    return direct_download_link


def process_audio(uploaded_file=None, direct_url=None, num_speakers=2, language="", prompt="", base_name=None, speaker_names=None, translate=False):
    try:
        # Erstelle einen expliziten Client mit dem Token
        if 'replicate_token' in st.session_state:
            client = replicate.Client(api_token=st.session_state.replicate_token)
            
        if direct_url:  # If a direct URL is provided
            file_url = direct_url
        elif uploaded_file:  # If an audio file is uploaded
            # Save the uploaded file to a temporary location
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
                temp_audio.write(uploaded_file.read())
                file_url = upload_to_hosting_service(open(temp_audio.name, 'rb'))
                
                # Print the file URL to verify
                print(f"Uploaded file URL: {file_url}")
                
        else:
            raise ValueError("Either a direct URL or an uploaded file is required.")

        # Verwende den Client anstelle von replicate.run
        output = client.run(
            "thomasmol/whisper-diarization:cbd15da9f839c5f932742f86ce7def3a03c22e2b4171d42823e83e314547003f",
            input={
                "file_url": file_url,
                "group_segments": True,
                "num_speakers": num_speakers,
                "language": language,
                "prompt": prompt,
                "offset_seconds": 0,
                "translate": translate,
            }
        )
        
        if base_name:
            output_filename = f"{base_name}.docx"
        else:
            output_filename = TRANSCRIPT_FILENAME

        if 'segments' in output:
            output_path = os.path.join(os.getcwd(), output_filename)
            format_json_to_chat(output['segments'], output_path, speaker_names)

            # Upload the transcript file and get the download link
            with open(output_path, 'rb') as transcript_file:
                transcript_download_link = upload_to_hosting_service(transcript_file)

            return output_path, transcript_download_link  # Return both the local path and download link
        else:
            raise AudioProcessError('The output is not as expected')
    except Exception as e:
        raise AudioProcessError(f'Error in processing audio: {e}')



def main():
    st.title("BonsAI Transkriptionsapp")
    if not enter_replicate_api_token():
        st.warning("⚠️ Bitte gib einen gültigen API Token ein, um fortzufahren.")
        st.stop()

    # Eingabefeld für die Anzahl der Transkripte
    num_transcripts = st.number_input("Anzahl der Transkripte:", min_value=1, value=1)

    # Container für jedes Transkript erstellen
    for transcript_idx in range(num_transcripts):
        with st.expander(f"Transkript {transcript_idx + 1}", expanded=True):
            # Zwei Spalten erstellen für Dropdown und manuellen Input
            col1, col2 = st.columns(2)
            
            with col1:
                language_dropdown = st.selectbox(
                    f"Welche Sprache wird gesprochen? (Transkript {transcript_idx + 1})",
                    ('de', 'en', 'it', 'fr', 'es', 'pl', 'sv', 'dk', 'bu', 'nl', 'hu'),
                    index=None,
                    placeholder="Bitte wähle die Sprache",
                    key=f"lang_dropdown_{transcript_idx}"
                )
            
            with col2:
                custom_language = st.text_input(
                    "Sprache nicht vorhanden? Hier den Ländercode eingeben:",
                    placeholder="z.B. ja für Japanisch",
                    key=f"custom_lang_{transcript_idx}"
                )
            
            language = custom_language if custom_language else language_dropdown

            translate = st.checkbox("Transkript auf Englisch übersetzen", 
                                 value=False, 
                                 key=f"translate_{transcript_idx}")

            num_speakers = st.number_input(
                "Anzahl Sprecher:", 
                min_value=1, 
                value=2,
                key=f"num_speakers_{transcript_idx}"
            )
            
            # Collect speaker names
            speaker_names = {}
            for i in range(1, num_speakers + 1):
                speaker_name = st.text_input(
                    f"Name Sprecher {i} (optional):",
                    key=f"speaker_{transcript_idx}_{i}"
                )
                if speaker_name:
                    speaker_names[f"SPEAKER_{i-1:02}"] = speaker_name

            prompt = st.text_input(
                "Info für die KI (optional):",
                key=f"prompt_{transcript_idx}"
            )

            uploaded_file = st.file_uploader(
                "Audio-Datei hochladen (bei mehr als 100 MB wird die Datei automatisch in mehrere Teile aufgeteilt und die Transkription mit den einzelnen Teilen erneut durchgeführt):", 
                type=["wav", "mp3", "mp4"],
                key=f"file_uploader_{transcript_idx}"
            )
            
            direct_url_input = st.empty()
            direct_url = direct_url_input.text_input(
                "Oder verwende einen Downloadlink zur Datei:",
                key=f"direct_url_{transcript_idx}"
            )
            
            base_name = None
            if uploaded_file:
                file_size = uploaded_file.size
                if file_size > 100 * 1024 * 1024:
                    parts = split_file(uploaded_file)
                    st.warning("""
                        Die hochgeladene Datei ist größer als 100 MB. Da der Hosting-Service eine Größenbeschränkung von 100 MB hat, 
                        wurde die Datei automatisch in mehrere Teile aufgeteilt. 
                        
                        Bitte lade alle Teile herunter und führe die Transkription mit den einzelnen Teilen erneut durch.
                        """)
                    
                    for idx, part in enumerate(parts):
                        st.download_button(
                            label=f"Download Teil {idx + 1}",
                            data=part,
                            file_name=f"{os.path.splitext(uploaded_file.name)[0]}_teil{idx + 1}{os.path.splitext(uploaded_file.name)[1]}",
                            mime=uploaded_file.type,
                            key=f"download_part_{transcript_idx}_{idx}"
                        )
                else:
                    file_url = upload_to_hosting_service(uploaded_file)
                    base_name = os.path.splitext(uploaded_file.name)[0]
                    direct_url_input.text_input(
                        "Oder verwende eine URL zur Datei:", 
                        value=file_url,
                        key=f"direct_url_input_{transcript_idx}"
                    )
                    direct_url = file_url

            # Speichere die Konfiguration für dieses Transkript
            if 'transcript_configs' not in st.session_state:
                st.session_state.transcript_configs = {}
            
            st.session_state.transcript_configs[transcript_idx] = {
                'language': language,
                'num_speakers': num_speakers,
                'prompt': prompt,
                'direct_url': direct_url,
                'base_name': base_name,
                'speaker_names': speaker_names,
                'translate': translate
            }

    # E-Mail-Eingabe außerhalb der Transkript-Schleifen
    user_email = st.text_input(
        "Bitte gib deine E-Mail-Adresse ein, falls du die Downloadlinks zugeschickt haben möchtest, sobald die Transkripte fertig sind. Es können mehrere E-Mail-Adressen eingeben werden. Diese müssen durch Komma getrennt werden (optional):"
    )

    # Gemeinsamer "Transkribieren" Button für alle Transkripte
    if st.button("Alle Transkripte erstellen", key="button_transcribe_all"):
        missing_language = False
        for idx in range(num_transcripts):
            config = st.session_state.transcript_configs.get(idx, {})
            if not config.get('language'):
                missing_language = True
                st.error(f"Bitte wähle eine Sprache für Transkript {idx + 1} aus.")
        
        if not missing_language:
            with st.spinner("Transkribiere alle Dateien..."):
                results = []
                for idx in range(num_transcripts):
                    config = st.session_state.transcript_configs[idx]
                    try:
                        output_path, transcript_download_link = process_audio(
                            direct_url=config['direct_url'],
                            num_speakers=config['num_speakers'],
                            language=config['language'],
                            prompt=config['prompt'],
                            base_name=f"{config['base_name']}_{idx+1}" if config['base_name'] else f"Transkript_{idx+1}",
                            speaker_names=config['speaker_names'],
                            translate=config['translate']
                        )
                        results.append((output_path, transcript_download_link))
                    except Exception as e:
                        st.error(f"Fehler bei Transkript {idx + 1}: {str(e)}")
                        continue
            # Speichere die Ergebnisse in st.session_state, statt sie sofort anzuzeigen
            if results:
                st.session_state["transcription_results"] = results
                # Sende E-Mail-Benachrichtigung nur einmal
                if user_email and "email_sent" not in st.session_state:
                    email_list = [email.strip() for email in user_email.split(',')]
                    for idx, (output_path, download_link) in enumerate(results):
                        if output_path:
                            send_email_notification(
                                email_list,
                                os.path.basename(output_path),
                                download_link
                            )
                    st.session_state["email_sent"] = True

    # Am Ende von main(): Download-Buttons anzeigen, basierend auf den gespeicherten Ergebnissen
    if "transcription_results" in st.session_state:
        results = st.session_state["transcription_results"]
        st.success("Fertig!")
        for idx, (output_path, download_link) in enumerate(results):
            if output_path:
                with open(output_path, "rb") as f:
                    doc_bytes = f.read()
                    st.download_button(
                        label=f"Download Transkript {idx + 1}",
                        data=doc_bytes,
                        file_name=os.path.basename(output_path),
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"download_transcript_{idx}"
                    )

def enter_replicate_api_token():
    """Interactive field to enter the Replicate API token."""
    # Hole den Token aus der Session, falls vorhanden
    if 'replicate_token' in st.session_state:
        replicate_token = st.session_state.replicate_token
    else:
        replicate_token = st.text_input("Bitte hier den geheimen Replicate Token eingeben:", type="password")
        
    if replicate_token:
        os.environ["REPLICATE_API_TOKEN"] = replicate_token
        # Validiere den Token
        try:
            # Versuche eine einfache API-Anfrage
            replicate.Client(api_token=replicate_token).models.get("stability-ai/stable-diffusion")
            st.success("✅ API Token erfolgreich validiert!")
            # Speichere den Token in der Session
            st.session_state.replicate_token = replicate_token
            return True
        except Exception as e:
            st.error("""
            ❌ Der eingegebene API Token ist ungültig. 
            
            Bitte überprüfe, ob du den Token korrekt von replicate.com kopiert hast.
            """)
            # Lösche ungültigen Token aus der Session
            if 'replicate_token' in st.session_state:
                del st.session_state.replicate_token
            return False
    return False

def handle_audio_process(num_speakers, language, prompt, user_email, uploaded_file=None, direct_url=None, base_name=None, speaker_names=None, translate=False):
    try:
        output_path, transcript_download_link = process_audio(
            uploaded_file=uploaded_file, 
            direct_url=direct_url, 
            num_speakers=num_speakers, 
            language=language, 
            prompt=prompt, 
            base_name=base_name, 
            speaker_names=speaker_names,
            translate=translate
        )  
        if output_path is not None:
            st.success(f"Fertig!")
            with open(output_path, "rb") as f:
                doc_bytes = f.read()
                st.download_button(
                    label="Download",
                    data=doc_bytes,
                    file_name=os.path.basename(output_path),
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            if user_email:
                email_list = user_email.split(',')
                send_email_notification(email_list, os.path.basename(output_path), transcript_download_link)

    except Exception as e:
        error_message = str(e)
        if "Unauthenticated" in error_message or "authentication token" in error_message:
            st.error("""
            ⚠️ Authentifizierungsfehler
            
            Bitte stelle sicher, dass du einen gültigen Replicate API Token eingegeben hast.""")
        else:
            st.error(f"Bei der Verarbeitung der Audio-Datei ist ein Fehler aufgetreten:\n{error_message}")

def split_file(file, max_size=100 * 1024 * 1024):
    """Teilt eine Datei in Teile, die jeweils weniger als max_size Bytes groß sind."""
    total_size = len(file.getvalue())
    num_parts = math.ceil(total_size / max_size)
    parts = []
    for i in range(num_parts):
        start = i * max_size
        end = start + max_size
        part = file.getvalue()[start:end]
        parts.append(part)
    return parts

if __name__ == "__main__":
    main()
