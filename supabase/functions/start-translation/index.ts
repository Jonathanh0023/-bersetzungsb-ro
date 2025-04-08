import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.38.0'
import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'

// Umgebungsvariablen aus Supabase abrufen
const supabaseUrl = Deno.env.get('SUPABASE_URL') || 'https://tyggaqynkmujggfszrvc.supabase.co'
const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')
const triggerApiKey = Deno.env.get('TRIGGER_DEV_API_KEY')
const projectId = Deno.env.get('TRIGGER_PROJECT_ID') || 'proj_hobmfqqsjwwoistsziye'
const triggerApiUrl = `https://api.trigger.dev/api/v1/projects/${projectId}/events/translation.request`

// Erstellt einen Supabase-Client mit der Service-Rolle
const supabase = createClient(supabaseUrl, supabaseKey)

serve(async (req) => {
  try {
    // CORS-Header setzen
    if (req.method === 'OPTIONS') {
      return new Response('ok', {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'POST',
          'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        },
      })
    }

    // Nur POST-Anfragen zulassen
    if (req.method !== 'POST') {
      return new Response(JSON.stringify({ error: 'Nur POST-Anfragen sind erlaubt' }), {
        status: 405,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        },
      })
    }

    // Anfrageinhalt auslesen
    const payload = await req.json()
    
    // Payload validieren
    const requiredFields = [
      'email', 'fileData', 'fileName', 'source_language', 'target_language',
      'country', 'respondent_group', 'survey_topic', 'survey_content',
      'api_key', 'model', 'batch_size', 'system_message'
    ]
    
    const missingFields = requiredFields.filter(field => !payload[field])
    if (missingFields.length > 0) {
      return new Response(JSON.stringify({ 
        error: `Fehlende Felder: ${missingFields.join(', ')}` 
      }), {
        status: 400,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        },
      })
    }

    // Einen neuen Eintrag in der translation_jobs-Tabelle erstellen
    const jobId = crypto.randomUUID()
    const { error: dbError } = await supabase
      .from('translation_jobs')
      .insert({
        id: jobId,
        email: payload.email,
        status: 'pending',
        progress: 0,
        source_language: payload.source_language,
        target_language: payload.target_language,
        original_filename: payload.fileName || payload.original_filename || 'unknown.xlsx',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      })

    if (dbError) {
      throw new Error(`Fehler beim Erstellen des Jobs: ${dbError.message}`)
    }

    // Prüfen, ob die Trigger.dev API-Konfiguration vorhanden ist
    if (!triggerApiKey) {
      throw new Error('Trigger.dev API-Schlüssel nicht konfiguriert')
    }

    // Trigger.dev-Event auslösen
    const triggerResponse = await fetch(triggerApiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${triggerApiKey}`,
      },
      body: JSON.stringify({
        id: jobId,
        payload: payload
      }),
    })

    if (!triggerResponse.ok) {
      const triggerError = await triggerResponse.text()
      throw new Error(`Fehler beim Auslösen des Trigger.dev-Events: ${triggerError}`)
    }

    // Erfolgreiche Antwort senden
    return new Response(JSON.stringify({ 
      success: true, 
      message: 'Übersetzungsjob gestartet', 
      jobId 
    }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      },
    })
  } catch (error) {
    console.error('Fehler in Edge Function:', error)
    
    // Fehler behandeln
    return new Response(JSON.stringify({ 
      error: error.message || 'Ein unbekannter Fehler ist aufgetreten'
    }), {
      status: 500,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      },
    })
  }
}) 