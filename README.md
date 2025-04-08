# bonsAI Übersetzungsbüro

Diese Anwendung bietet eine benutzerfreundliche Oberfläche für die automatisierte Übersetzung von Excel-Dateien mit KI. Die Übersetzung wird im Hintergrund verarbeitet und der Benutzer erhält eine E-Mail, sobald die Übersetzung abgeschlossen ist.

## Architektur

Das System besteht aus drei Hauptkomponenten:

1. **Streamlit-App**: Benutzeroberfläche mit mehreren Modulen, darunter:
   - Jobs-Übersicht (`jobs_app.py`): Anzeige aller laufenden und abgeschlossenen Jobs
   - Übersetzungsformular (`allgemeine_app.py`): Eingabe der Übersetzungsparameter und Hochladen von Excel-Dateien
   - Weitere Module für spezifische Übersetzungsaufgaben

2. **Supabase Edge Functions**: Server-seitige Funktionen für die Verarbeitung von Anfragen:
   - `start-translation`: Erstellt einen neuen Übersetzungsauftrag und triggert den Hintergrundprozess
   - `send-email`: Versendet E-Mail-Benachrichtigungen nach Abschluss der Übersetzung

3. **Trigger.dev Job**: Asynchrone Verarbeitung der Übersetzung im Hintergrund:
   - `translation-job.ts`: Hauptkomponente für die Übersetzungslogik
   - Maximale Laufzeit: 5 Stunden pro Job
   - Fortschrittsverfolgung und Fehlerbehandlung

## Datenbankstruktur

Die Anwendung verwendet eine Supabase-Datenbank mit folgender Haupttabelle:

```sql
CREATE TABLE IF NOT EXISTS public.translation_jobs (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  progress INTEGER NOT NULL DEFAULT 0,
  file_url TEXT,
  source_language TEXT,
  target_language TEXT,
  error_message TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  completed_at TIMESTAMP WITH TIME ZONE
);
```

Die Felder umfassen:
- `error_message`: Speichert detaillierte Fehlermeldungen bei fehlgeschlagenen Jobs
- `status`: Aktueller Zustand des Jobs (ausstehend, in Bearbeitung, abgeschlossen, fehlgeschlagen)
- `progress`: Fortschritt in Prozent (0-100)

## Einrichtung

### Voraussetzungen

- Node.js und npm
- Supabase-Konto
- Trigger.dev-Konto
- OpenAI API-Schlüssel
- Resend-Konto für E-Mail-Versand

### Einrichtung in Supabase

1. Schema in `schema/translation_jobs_table.sql` für die Datenbankstruktur verwenden
2. Erstelle einen Storage-Bucket `uebersetzung-output` in Supabase und aktiviere öffentlichen Zugriff
3. Deploye die Edge-Funktionen:

```bash
# Stelle sicher, dass du die Supabase CLI installiert hast
npm install -g supabase

# Logge dich ein und wähle dein Projekt
supabase login
supabase link

# Deploye die Edge-Funktionen
supabase functions deploy start-translation
supabase functions deploy send-email
```

4. Setze folgende Umgebungsvariablen in Supabase:

- `SUPABASE_SERVICE_ROLE_KEY`: Service-Rolle-Schlüssel von Supabase
- `TRIGGER_DEV_API_KEY`: API-Schlüssel von Trigger.dev
- `TRIGGER_PROJECT_ID`: Projekt-ID in Trigger.dev (proj_hobmfqqsjwwoistsziye)
- `RESEND_API_KEY`: API-Schlüssel für Resend-E-Mail-Service

### Einrichtung bei Trigger.dev

1. Registriere dich bei [Trigger.dev](https://trigger.dev) und erstelle ein neues Projekt
2. Initialisiere das Projekt:

```bash
npx trigger.dev@latest init
```

3. Installiere Abhängigkeiten:

```bash
npm install @supabase/supabase-js openai xlsx
```

4. Konfiguriere die maximale Laufzeit auf 3 Stunden in `trigger.config.ts`:

```typescript
export default defineConfig({
  project: "proj_hobmfqqsjwwoistsziye",
  maxDuration: 5 * 60 * 60, // 3 Stunden in Sekunden
  dirs: ["./src/trigger"],
});
```

5. Führe den Entwicklungsserver aus:

```bash
npx trigger.dev@latest dev
```

6. Deploye den Job:

```bash
npx trigger.dev@latest deploy
```

## Verwendung

1. Starte die Streamlit-App mit:

```bash
streamlit run main.py
```

2. Öffne die Anwendung im Browser und navigiere zu einem der Übersetzungsmodule
3. Fülle die Formularfelder aus und lade eine Excel-Datei hoch
4. Klicke auf "Übersetzen", um den Übersetzungsjob zu starten
5. Verfolge den Fortschritt im "Alle Jobs"-Bereich
6. Nach Abschluss erhältst du eine E-Mail mit einem Link zur übersetzten Datei

## Fehlerbehandlung

Das System verfügt über umfassende Fehlerbehandlung:

1. **In der Datenbank**: Fehler werden im `error_message`-Feld gespeichert, Status wird auf "error" gesetzt
2. **In der Benutzeroberfläche**: Fehlermeldungen werden in der Jobs-Übersicht angezeigt
3. **Logging**: Ausführliche Logs in Trigger.dev und Supabase-Konsole

Wenn Probleme auftreten, überprüfe:
- Trigger.dev-Logs im Dashboard
- Supabase-Funktionslogs in der Konsole
- Die Einträge in der `translation_jobs`-Tabelle mit Fehlermeldungen

## Technische Hinweise

- Die Übersetzungen verwenden die OpenAI GPT-API mit Batch-Verarbeitung zur Optimierung
- Excel-Dateien werden Base64-kodiert zwischen den Diensten übertragen
- Übersetzungsergebnisse werden in der Spalte "Text zur Übersetzung / Versionsanpassung" gespeichert
- Die Qualitätssicherung (QM-Check) markiert potenzielle Probleme in der Übersetzung
- Die Benutzeroberfläche ist komplett auf Deutsch und unterstützt die automatische Aktualisierung 