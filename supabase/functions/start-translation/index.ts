// supabase/functions/start-translation/index.ts
import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.15.0'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

serve(async (req) => {
  // Handle CORS preflight request
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const { email, file_url, source_language, target_language, original_filename } = await req.json()

    // Validiere die Eingangsdaten
    if (!email || !file_url || !source_language || !target_language) {
      return new Response(
        JSON.stringify({ error: 'Fehlende erforderliche Felder' }),
        {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          status: 400,
        }
      )
    }

    // Supabase Client initialisieren
    const supabaseUrl = Deno.env.get('SUPABASE_URL') || 'https://tyggaqynkmujggfszrvc.supabase.co'
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')
    
    if (!supabaseServiceKey) {
      return new Response(
        JSON.stringify({ error: 'Server-Konfigurationsfehler: SUPABASE_SERVICE_ROLE_KEY fehlt' }),
        {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          status: 500,
        }
      )
    }

    const supabase = createClient(supabaseUrl, supabaseServiceKey)

    // Ein einzigartiges ID erstellen
    const jobId = crypto.randomUUID()

    // Job in der Datenbank erfassen
    const { data, error } = await supabase
      .from('translation_jobs')
      .insert({
        id: jobId,
        email: email,
        file_url: file_url,
        source_language: source_language,
        target_language: target_language,
        status: 'pending',
        progress: 0,
        original_filename: original_filename || 'unbekannt.xlsx'
      })

    if (error) {
      console.error('Fehler beim Erstellen des Jobs:', error)
      return new Response(
        JSON.stringify({ error: `Datenbankfehler: ${error.message}` }),
        {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          status: 500,
        }
      )
    }

    // Trigger.dev API für die Übersetzung aufrufen
    const triggerApiKey = Deno.env.get('TRIGGER_DEV_API_KEY')
    const triggerProjectId = Deno.env.get('TRIGGER_PROJECT_ID')
    
    if (!triggerApiKey || !triggerProjectId) {
      return new Response(
        JSON.stringify({ error: 'Server-Konfigurationsfehler: Trigger.dev Einstellungen fehlen' }),
        {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          status: 500,
        }
      )
    }

    const response = await fetch(`https://app.trigger.dev/api/v1/projects/${triggerProjectId}/events/dynamic`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${triggerApiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        name: 'translation.requested',
        payload: {
          jobId: jobId,
          fileUrl: file_url,
          email: email,
          sourceLanguage: source_language,
          targetLanguage: target_language,
          originalFilename: original_filename || 'unbekannt.xlsx'
        }
      })
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Fehler beim Trigger.dev Aufruf:', errorText)
      
      // Aktualisiere den Job-Status auf Fehler
      await supabase
        .from('translation_jobs')
        .update({
          status: 'error',
          error_message: `Fehler beim Starten des Übersetzungsjobs: ${errorText}`
        })
        .eq('id', jobId)

      return new Response(
        JSON.stringify({ error: `Fehler beim Aufruf von Trigger.dev: ${errorText}` }),
        {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          status: 500,
        }
      )
    }

    // Erfolgreich
    return new Response(
      JSON.stringify({ 
        success: true, 
        message: 'Übersetzungsjob erfolgreich gestartet',
        jobId: jobId
      }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 200,
      }
    )
  } catch (error) {
    console.error('Unerwarteter Fehler:', error)
    return new Response(
      JSON.stringify({ error: `Unerwarteter Fehler: ${error.message}` }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 500,
      }
    )
  }
})
