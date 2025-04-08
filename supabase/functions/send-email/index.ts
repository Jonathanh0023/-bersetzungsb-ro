import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'

interface EmailRequest {
  to: string;
  subject: string;
  content: string;
}

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
    const { to, subject, content }: EmailRequest = await req.json()
    
    // Validierung
    if (!to || !subject || !content) {
      return new Response(JSON.stringify({ 
        error: 'Fehlende Parameter (to, subject oder content)'
      }), {
        status: 400,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        },
      })
    }

    // E-Mail-Versand hier implementieren
    // Je nach Verfügbarkeit z.B. mit SMTP, Resend, SendGrid, usw.
    // Hier ein Beispiel mit Resend (erfordert RESEND_API_KEY als Umgebungsvariable):
    
    const resendApiKey = Deno.env.get('RESEND_API_KEY')
    
    if (!resendApiKey) {
      console.warn('RESEND_API_KEY nicht konfiguriert, E-Mail wird nicht versendet')
      
      // Simuliere erfolgreichen Versand für Testzwecke
      console.log(`Simulierter E-Mail-Versand an ${to}: ${subject}`)
      
      return new Response(JSON.stringify({ 
        success: true, 
        message: 'E-Mail-Versand simuliert (RESEND_API_KEY nicht konfiguriert)' 
      }), {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        },
      })
    }

    // Mit Resend API senden, falls API-Schlüssel konfiguriert ist
    const response = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${resendApiKey}`
      },
      body: JSON.stringify({
        from: 'Übersetzungsbüro <no-reply@bonsai-research.ai>',
        to: [to],
        subject: subject,
        html: content
      })
    })

    const result = await response.json()
    
    if (!response.ok) {
      throw new Error(`Fehler beim E-Mail-Versand: ${JSON.stringify(result)}`)
    }

    // Erfolgreiche Antwort senden
    return new Response(JSON.stringify({ 
      success: true, 
      message: 'E-Mail erfolgreich gesendet', 
      id: result.id 
    }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      },
    })
  } catch (error) {
    console.error('Fehler in send-email Edge Function:', error)
    
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