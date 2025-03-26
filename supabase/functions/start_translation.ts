import { serve } from "https://deno.land/std@0.140.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

serve(async (req: Request) => {
  try {
    const { email, api_key, file_data, parameters } = await req.json();

    // Hier fügen wir den OpenAI API-Key zu den Parametern hinzu.
    // In einer Produktion solltest du den API-Key besonders schützen.
    const updatedParameters = { ...parameters, openai_api_key: api_key };

    // Supabase-Client initialisieren
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Neuen Job in der Tabelle "translations" anlegen (Status "pending")
    const { data, error } = await supabase
      .from("translations")
      .insert({
        email,
        original_text: file_data,
        parameters: updatedParameters,
        status: "pending"
      })
      .select();

    if (error) throw error;

    const job = data[0];
    // Job-ID zurückliefern
    return new Response(
      JSON.stringify({ job_id: job.id, message: "Job created" }),
      { status: 200 }
    );
  } catch (err) {
    return new Response(
      JSON.stringify({ error: err.message }),
      { status: 500 }
    );
  }
});
