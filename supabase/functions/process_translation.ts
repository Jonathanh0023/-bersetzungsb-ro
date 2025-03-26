import { serve } from "https://deno.land/std@0.140.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// --- Helper-Funktion: Retry-Mechanismus mit exponentiellem Backoff ---
async function retry<T>(fn: () => Promise<T>, retries = 3, delay = 2000): Promise<T> {
  let attempt = 0;
  while (true) {
    try {
      return await fn();
    } catch (err) {
      attempt++;
      if (attempt >= retries) throw err;
      await new Promise((res) => setTimeout(res, delay * attempt));
    }
  }
}

// --- Funktion zur Generierung der Systemnachricht ---
function generateSystemMessage(
  source_language: string,
  respondent_group: string,
  survey_topic: string,
  target_language: string,
  survey_content: string,
  country: string
): string {
  return (
    `You are assisting an English-speaking programmer in translating a questionnaire from ${source_language} into ${target_language}.` +
    `The topic of the survey is '${survey_topic}'. Your primary goal is to ensure that the translation sounds natural and fluent for native speakers while preserving all technical and programming elements accurately.\n\n` +
    `Programming Instructions: All programming instructions, including codes and strings (e.g., 'Screenout', 'Quote'), must remain exactly as they are in the translation. ` +
    `Rogator-specific syntax, which always begins with !% and ends with %!, represents dynamic placeholders and must be retained unchanged, as these will later be populated by the software.\n\n` +
    `Curly Brace Elements: Retain all elements within curly braces and any country codes without translating them.\n\n` +
    `Form of Address: Use the polite form ('Sie') for direct addresses. For job titles or personal forms of address, ensure gender inclusivity by using both masculine and feminine forms or a gender-neutral term if appropriate.\n\n` +
    `Content Translation: Translate the meaning rather than word-for-word. Ensure the translation is fluent and natural for native speakers, without changing the original intent.` +
    `For example: If the sentence already uses a polite form of address, such as 'Veuillez' or 'Pourriez-vous' in French, it is not necessary to include phrases like 's'il vous plaît' for example.` +
    `The German phrase ‘Würden Sie uns bitte’ would be translated into French as ‘Veuillez nous’ and the ‘s'il vous plaît’ can be omitted.\n\n` +
    `Language-Specific Conventions: Pay special attention to conventional sentence structures and placement of polite expressions in the target language. For French, for example, the phrase 's'il vous plaît' is typically placed at the beginning or end of the sentence, not in the middle.` +
    `Consistency in Style: Ensure a consistent and natural style throughout the translation, adapting the language to suit ${target_language} linguistic nuances. Your response should include only the translated text. ` +
    `If the input is a code or a placeholder, reproduce it exactly without translation.\n\n` +
    `For reference, here is background information on the questionnaire's purpose and target audience:\n${survey_content}\n\n` +
    `Also, be sure to consider cultural nuances and conventions relevant to ${country}. If any cultural adjustments need to be made to improve clarity, precision and appropriateness for respondents in ${country}, please integrate them. When translating, base your translation on how the wording, sentence structure and linguistic expression is usually formulated in ${country}.\n\n` +
    `Attention to detail: Take the necessary time to carefully consider each term. It is critical to maintain accuracy, modified sentence structure, and cultural appropriateness in ${country} in the translated text.`
  );
}

// --- Funktion zum Aufruf der OpenAI API (echter Übersetzungs-Call) ---
async function callOpenAI(apiKey: string, model: string, messages: any[]): Promise<string> {
  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${apiKey}`
    },
    body: JSON.stringify({
      model: model,
      messages: messages,
      temperature: 0.7,
      max_tokens: 1024
    })
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error?.message || "OpenAI API error");
  }
  return data.choices[0].message.content;
}

// --- Funktion zum Versenden der E-Mail via resend.com ---
async function sendEmail(recipient: string, subject: string, body: string) {
  const resendApiKey = Deno.env.get("RESEND_API_KEY");
  const senderEmail = Deno.env.get("SENDER_EMAIL");
  if (!resendApiKey || !senderEmail) {
    throw new Error("Email-Konfiguration nicht gesetzt");
  }
  const emailPayload = {
    from: senderEmail,
    to: recipient,
    subject,
    html: body,
  };

  return await retry(async () => {
    const response = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${resendApiKey}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(emailPayload)
    });
    if (!response.ok) {
      const errorDetails = await response.text();
      throw new Error(`E-Mail Versand fehlgeschlagen: ${errorDetails}`);
    }
    return response.json();
  });
}

serve(async (req: Request) => {
  try {
    // Erwarte ein JSON-Payload mit "job_id" (optional; falls nicht angegeben, wird der erste pending Job abgearbeitet)
    const { job_id } = await req.json().catch(() => ({}));

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Hole den zu verarbeitenden Job – entweder anhand der übergebenen Job-ID oder den ersten pending Job
    let query = supabase.from("translations").select("*").eq("status", "pending");
    if (job_id) {
      query = supabase.from("translations").select("*").eq("id", job_id).eq("status", "pending");
    }
    const { data, error } = await query;
    if (error) throw error;
    if (data.length === 0) {
      return new Response(
        JSON.stringify({ message: "No pending jobs" }),
        { status: 200 }
      );
    }
    const job = data[0];

    // Erzeuge die Systemnachricht anhand der im Job gespeicherten Parameter
    const params = job.parameters;
    const system_message = generateSystemMessage(
      params.source_language,
      params.respondent_group,
      params.survey_topic,
      params.target_language,
      params.survey_content,
      params.country
    );
    // Der Benutzertext ist der Originaltext aus der hochgeladenen Datei
    const user_message = job.original_text;
    const messages = [
      { role: "system", content: system_message },
      { role: "user", content: user_message }
    ];

    // Rufe die OpenAI API mit dem im Job hinterlegten API-Key und Modell auf
    const openaiApiKey = params.openai_api_key;
    const model = params.model || "gpt-4";
    const translated_text = await callOpenAI(openaiApiKey, model, messages);

    // Erzeuge den Excel-Output (hier als einfacher Text) und wandle ihn in Bytes um
    const excelContent = `Übersetzter Inhalt:\n\n${translated_text}`;
    const excelBytes = new TextEncoder().encode(excelContent);
    const filename = `translation_${job.id}_${Date.now()}.xlsx`;

    // Lade die Excel-Datei in den Storage-Bucket "uebersetzung-output" hoch
    const { data: storageData, error: storageError } = await retry(() =>
      supabase.storage.from("uebersetzung-output").upload(filename, excelBytes, { upsert: true })
    );
    if (storageError) throw storageError;

    // Hole die öffentliche URL der hochgeladenen Datei
    const { data: publicUrlData, error: urlError } = supabase.storage.from("uebersetzung-output").getPublicUrl(filename);
    if (urlError) throw urlError;
    const excel_url = publicUrlData.publicUrl;

    // Aktualisiere den Job in der DB mit den Übersetzungsergebnissen und setze den Status auf "completed"
    const { data: updateData, error: updateError } = await retry(() =>
      supabase.from("translations").update({
        translated_text: translated_text,
        excel_url: excel_url,
        status: "completed"
      }).eq("id", job.id)
    );
    if (updateError) throw updateError;

    // Versende die E-Mail an den Nutzer – der Betreff enthält die Job-ID
    const emailSubject = `Deine Übersetzung mit der Job-ID ${job.id} ist abgeschlossen`;
    const emailBody = `<p>Hallo,</p>
      <p>deine Übersetzung ist abgeschlossen. Hier das Ergebnis:</p>
      <p>${translated_text}</p>
      <p>Den aktuellen Excel-Output kannst du hier herunterladen: <a href="${excel_url}">Download</a></p>
      <p>Viele Grüße</p>`;
    await sendEmail(job.email, emailSubject, emailBody);

    return new Response(
      JSON.stringify({
        message: "Job processed successfully",
        job_id: job.id
      }),
      { status: 200 }
    );
  } catch (err) {
    return new Response(
      JSON.stringify({ error: err.message }),
      { status: 500 }
    );
  }
});
