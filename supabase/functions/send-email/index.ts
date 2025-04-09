// supabase/functions/send-email/index.ts
import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'

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
    const { email, fileUrl, originalFilename, jobId } = await req.json()

    // Validiere die Eingangsdaten
    if (!email || !fileUrl) {
      return new Response(
        JSON.stringify({ error: 'Fehlende erforderliche Felder (email, fileUrl)' }),
        {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          status: 400,
        }
      )
    }

    // Resend API-Schlüssel holen
    const resendApiKey = Deno.env.get('RESEND_API_KEY')
    if (!resendApiKey) {
      return new Response(
        JSON.stringify({ error: 'Server-Konfigurationsfehler: RESEND_API_KEY fehlt' }),
        {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          status: 500,
        }
      )
    }

    // Erstelle einen beschreibenden Dateinamen, wenn originalFilename fehlt
    const displayFilename = originalFilename || 'Übersetzungsdatei.xlsx'
    
    // Sende die E-Mail über Resend API
    const response = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${resendApiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        from: 'BonsAI Übersetzungsbüro <uebersetzung@bons.ai>',
        to: email,
        subject: 'Deine Übersetzung ist fertig! 🚀',
        html: `
          <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border-radius: 10px; border: 1px solid #e0dbdb;">
            <div style="text-align: center; margin-bottom: 20px;">
              <img src="https://sw01.rogsurvey.de/data/bonsai/Kara_23_19/logo_Bonsa_BONSAI_neu.png" alt="bonsAI Logo" style="height: 60px;">
            </div>
            <h1 style="color: #e5007f; text-align: center;">Deine Übersetzung ist fertig! 🎉</h1>
            <p>Hallo,</p>
            <p>gute Neuigkeiten! Deine Übersetzung ist abgeschlossen und bereit zum Herunterladen.</p>
            <div style="background-color: #f7f7f7; padding: 15px; border-radius: 8px; margin: 20px 0;">
              <p><strong>Dateiname:</strong> ${displayFilename}</p>
              <p><strong>Job-ID:</strong> ${jobId || 'Nicht verfügbar'}</p>
            </div>
            <div style="text-align: center; margin: 30px 0;">
              <a href="${fileUrl}" style="background-color: #e5007f; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">Übersetzung herunterladen</a>
            </div>
            <p>Falls du Fragen hast oder weitere Unterstützung benötigst, kontaktiere uns gerne:</p>
            <ul>
              <li>Jonathan Heeckt (jonathan.heeckt@rogator.de)</li>
              <li>Tobias Bucher (tobias.bucher@rogator.de)</li>
            </ul>
            <p>Vielen Dank, dass du das bonsAI Übersetzungsbüro nutzt!</p>
            <hr style="border: none; border-top: 1px solid #e0dbdb; margin: 20px 0;">
            <p style="font-size: 12px; color: #666; text-align: center;">
              Diese E-Mail wurde automatisch vom bonsAI Übersetzungssystem versendet.<br>
              © 2024 bonsAI | Rogator GmbH
            </p>
          </div>
        `
      })
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Fehler beim Senden der E-Mail:', errorText)
      return new Response(
        JSON.stringify({ error: `Fehler beim Senden der E-Mail: ${errorText}` }),
        {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          status: 500,
        }
      )
    }

    const responseData = await response.json()

    // Erfolgreich
    return new Response(
      JSON.stringify({ 
        success: true, 
        message: 'E-Mail erfolgreich gesendet',
        emailId: responseData.id
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
