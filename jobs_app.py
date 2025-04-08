import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from utils import select_app  # Hinzugefügt für den Home-Button
import time
import streamlit.components.v1 as components

def jobs_app():
    # Anker am Seitenanfang setzen
    st.markdown('<div id="jobs-app-top"></div>', unsafe_allow_html=True)
    
    # Überschrift und Navigation
    col1, col2 = st.columns([8, 2])
    with col1:
        st.markdown(f"<h1>Alle Jobs 📋</h1>", unsafe_allow_html=True)
    with col2:
        st.markdown(
            "<div style='display: flex; justify-content: flex-end;'>",
            unsafe_allow_html=True
        )
        st.button("Home", on_click=lambda: select_app(None), key="home_button_jobs")
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Tabs für verschiedene Job-Typen
    tabs = st.tabs(["Übersetzungsjobs"])
    
    # Tab für Übersetzungsjobs
    with tabs[0]:
        st.subheader("Übersetzungsjobs")
        
        # Funktion zum Abrufen der Übersetzungsjobs aus Supabase
        def get_translation_jobs():
            try:
                # Supabase API URL und Anon Key
                supabase_url = "https://tyggaqynkmujggfszrvc.supabase.co"
                supabase_anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InR5Z2dhcXlua211amdnZnN6cnZjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDI5OTA4MzAsImV4cCI6MjA1ODU2NjgzMH0.VACjxNLN_0AnN37xfrYcb-8b-5bOQgBfgLdl29I-HoE"
                
                # Anfrage an Supabase, um alle Übersetzungsjobs abzurufen
                response = requests.get(
                    f"{supabase_url}/rest/v1/translation_jobs?select=id,original_filename,source_language,target_language,status,progress,created_at,file_url,error_message",
                    headers={
                        "apikey": supabase_anon_key,
                        "Authorization": f"Bearer {supabase_anon_key}"
                    }
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    st.error(f"Fehler beim Abrufen der Jobs: {response.status_code}")
                    return []
            except Exception as e:
                st.error(f"Ein Fehler ist aufgetreten: {str(e)}")
                return []
        
        # Jobs abrufen
        jobs = get_translation_jobs()
        
        # Reload-Button für manuelle Aktualisierung
        if st.button("Aktualisieren", key="refresh_jobs"):
            st.rerun()
        
        if jobs:
            # Daten für die Tabelle vorbereiten
            df = pd.DataFrame(jobs)
            
            # Datum formatieren
            def format_date(date_str):
                try:
                    date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    return date_obj.strftime('%d.%m.%Y %H:%M')
                except:
                    return date_str
            
            # Status in deutsche Bezeichnungen übersetzen
            def translate_status(status):
                status_map = {
                    "pending": "Ausstehend",
                    "processing": "In Bearbeitung",
                    "completed": "Abgeschlossen",
                    "failed": "Fehlgeschlagen",
                    "error": "Fehler"
                }
                return status_map.get(status, status)
            
            if 'created_at' in df.columns:
                df['created_at'] = df['created_at'].apply(format_date)
            
            if 'status' in df.columns:
                df['status'] = df['status'].apply(translate_status)
            
            # Spaltennamen übersetzen
            if not df.empty:
                df = df.rename(columns={
                    'id': 'ID',
                    'original_filename': 'Dateiname',
                    'source_language': 'Quellsprache',
                    'target_language': 'Zielsprache',
                    'status': 'Status',
                    'progress': 'Fortschritt (%)',
                    'created_at': 'Erstellt am',
                    'file_url': 'Download-Link'
                })
                
                # Spalte für Fortschrittsbalken hinzufügen
                df_display = df.copy()
                if 'Fortschritt (%)' in df_display.columns:
                    # Nach Erstelldatum absteigend sortieren (neueste zuerst)
                    df_display = df_display.sort_values(by='Erstellt am', ascending=False)
                    
                    # Eine kompakte Tabelle für alle Jobs erstellen (statt Einzelanzeige)
                    st.write("### Übersicht aller Übersetzungsjobs")
                    
                    # Kompakte Tabellendarstellung mit nur ID, Status und Erstelldatum mit maximaler Höhe
                    compact_df = df_display[['ID', 'Status', 'Erstellt am']]
                    st.dataframe(compact_df, height=300, use_container_width=True)
                    
                    # Detaillierte Ansicht mit Fortschrittsbalken
                    st.write("### Details zu den einzelnen Jobs")
                    for i, row in df_display.iterrows():
                        col1, col2, col3 = st.columns([3, 3, 4])
                        with col1:
                            st.write(f"**Dateiname:** {row['Dateiname']}")
                            st.write(f"**ID:** {row['ID']}")
                        with col2:
                            st.write(f"**Quellsprache:** {row['Quellsprache']}")
                            st.write(f"**Zielsprache:** {row['Zielsprache']}")
                        with col3:
                            st.write(f"**Status:** {row['Status']}")
                            st.write(f"**Erstellt am:** {row['Erstellt am']}")
                            
                            # Zeige Fortschrittsbalken, außer bei Fehlern
                            if 'error' in row['Status'].lower():
                                st.error(f"Fehler: {row.get('error_message', 'Unbekannter Fehler')}")
                            else:
                                # Fortschrittsbalken
                                progress = int(row['Fortschritt (%)'])
                                st.progress(progress / 100)
                                st.write(f"Fortschritt: {progress}%")
                        
                        st.markdown("---")
                else:
                    st.dataframe(df_display)
            else:
                st.info("Keine Übersetzungsjobs gefunden.")
        else:
            st.info("Keine Übersetzungsjobs gefunden oder Verbindung zur Datenbank nicht möglich.")
    
    # JavaScript-Code zum Scrollen zum Seitenanfang
    # Der Zeitstempel stellt sicher, dass das Skript bei jeder Ausführung als neu erkannt wird
    scroll_script = f"""
    <script>
        // Scroll to top of Jobs app (Timestamp {time.time()})
        var el = window.parent.document.getElementById('jobs-app-top');
        if(el) {{
            el.scrollIntoView({{ behavior: 'auto' }});
        }}
    </script>
    """
    components.html(scroll_script, height=0)

# Hilfsfunktion zur App-Auswahl
def select_app(app_name):
    st.session_state.app_selected = app_name
