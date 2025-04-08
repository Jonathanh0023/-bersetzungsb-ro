import { task } from "@trigger.dev/sdk/v3";d
import OpenAI from "openai";
import * as XLSX from "xlsx";
import { createClient } from "@supabase/supabase-js";

// Interface für die Payload-Struktur
interface TranslationPayload {
  jobId: string;
  email?: string;
  source_language: string;
  target_language: string;
  country: string;
  respondent_group: string;
  survey_topic: string;
  survey_content: string;
  fileName: string;
  fileData: string; // Base64-kodiertes Excel-File
  api_key: string;
  model: string;
  batch_size: number;
  system_message?: string;
}

// Interface für Excel-Zeilen
interface TranslationRow {
  [key: string]: any;
  "Vergleichstext Ursprungsversion"?: string;
  "Text zur Übersetzung / Versionsanpassung"?: string;
  QMS?: string;
}

// Interface für Rückgabewert
interface TranslationResult {
  success: boolean;
  message: string;
  jobId: string;
  resultUrl?: string;
}

/**
 * Eine einfache Retry-Funktion, die einen asynchronen Aufruf mehrfach versucht.
 */
async function retry<T>(
  fn: () => Promise<T>,
  attempts: number = 5,
  delay: number = 2000
): Promise<T> {
  let lastError;
  for (let i = 0; i < attempts; i++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      const waitTime = Math.min(delay * Math.pow(2, i), 10000);
      await new Promise((res) => setTimeout(res, waitTime));
    }
  }
  throw lastError;
}

// Funktion zur Übersetzung (analog zur Python-Funktion)
async function askAssistantTranslation(
  client: OpenAI,
  model: string,
  messages: any[]
): Promise<string> {
  return retry(async () => {
    const response = await client.chat.completions.create({ model, messages });
    return response.choices[0]?.message.content || "";
  }, 5, 2000);
}

// Funktion für den QM-Check
async function askAssistantQmCheck(
  client: OpenAI,
  model: string,
  messages: any[]
): Promise<string> {
  return retry(async () => {
    const response = await client.chat.completions.create({ model, messages });
    return response.choices[0]?.message?.content?.trim() || "";
  }, 5, 2000);
}

export const translationTask = task({
  id: "translation-job",
  run: async (payload: any, params: any) => {
    // Versuche, den Logger aus den Params zu erhalten; falls nicht vorhanden, setze einen Fallback ein.
    const logger =
      params?.ctx?.logger ?? {
        info: console.log,
        error: console.error,
      };

    logger.info("Task gestartet");

    const data = payload as TranslationPayload;
    const {
      jobId,
      email,
      source_language,
      target_language,
      country,
      respondent_group,
      survey_topic,
      survey_content,
      fileName,
      fileData,
      api_key,
      model,
      batch_size,
      system_message,
    } = data;

    // Supabase konfigurieren
    const supabaseUrl =
      process.env.SUPABASE_URL || "https://example.supabase.co";
    const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
    if (!supabaseKey) {
      throw new Error("SUPABASE_SERVICE_ROLE_KEY nicht konfiguriert");
    }
    const supabase = createClient(supabaseUrl, supabaseKey);

    try {
      // Setze den Job auf "processing"
      await supabase
        .from("translation_jobs")
        .update({
          status: "processing",
          progress: 5,
          updated_at: new Date().toISOString(),
        })
        .eq("id", jobId);
      logger.info("Jobstatus auf 'processing' gesetzt", { jobId });

      // OpenAI-Client initialisieren
      const openai = new OpenAI({ apiKey: api_key });

      // Excel-Datei verarbeiten (Base64-String decodieren)
      logger.info("Excel-Datei wird verarbeitet");
      const workbook = XLSX.read(fileData, { type: "base64" });
      const worksheet = workbook.Sheets[workbook.SheetNames[0]];
      const rows: TranslationRow[] = XLSX.utils.sheet_to_json(worksheet);

      // Überprüfe, ob die erforderlichen Spalten existieren
      if (
        !rows.length ||
        !("Vergleichstext Ursprungsversion" in rows[0]) ||
        !("Text zur Übersetzung / Versionsanpassung" in rows[0])
      ) {
        throw new Error(
          "Die Excel-Datei enthält nicht die erforderlichen Spalten 'Vergleichstext Ursprungsversion' und/oder 'Text zur Übersetzung / Versionsanpassung'."
        );
      }
      logger.info("Excel-Datei validiert", { zeilen: rows.length });

      // Für den Kontext: bisherige Übersetzungen
      let previousTranslations: string[] = [];

      // Batch-Verarbeitung der Zeilen
      for (let i = 0; i < rows.length; i += batch_size) {
        const batchRows = rows.slice(i, i + batch_size);
        logger.info("Starte Batch-Verarbeitung", {
          batch: i / batch_size + 1,
          anzahl: batchRows.length,
        });

        // Sammle Texte, die übersetzt werden sollen
        const translatableTexts: string[] = [];
        const translatablePositions: number[] = [];
        const batchResult: string[] = new Array(batchRows.length).fill("");

        for (let pos = 0; pos < batchRows.length; pos++) {
          const text = batchRows[pos]["Vergleichstext Ursprungsversion"];
          if (typeof text === "string") {
            const trimmed = text.trim();
            if (trimmed === "" || /^[\d.]+$/.test(trimmed)) {
              batchResult[pos] = text;
            } else {
              translatableTexts.push(text);
              translatablePositions.push(pos);
            }
          } else {
            batchResult[pos] = text || "";
          }
        }

        // Übersetze alle gesammelten Texte in einem Batch (falls vorhanden)
        if (translatableTexts.length > 0) {
          const separator = "|||";
          const joinedText = translatableTexts.join(separator);
          const extendedSystemMessage = `${system_message || ""}\n\nEarlier translations:\n${previousTranslations.join("\n")}`;

          const messages = [
            { role: "system", content: extendedSystemMessage },
            { role: "user", content: joinedText },
          ];

          let translatedResponse = "";
          try {
            translatedResponse = await askAssistantTranslation(openai, model, messages);
            logger.info("Batch-Übersetzung erfolgreich", { batch: i / batch_size + 1 });
          } catch (err) {
            logger.error("Fehler bei Batch-Übersetzung", { batch: i / batch_size + 1, error: err });
            translatedResponse = "";
          }
          let translatedLines = translatedResponse.split(separator);

          // Fallback: Falls die Anzahl der Übersetzungen nicht übereinstimmt
          if (translatedLines.length !== translatableTexts.length) {
            logger.error("Fehler: Anzahl der übersetzten Zeilen stimmt nicht überein", {
              expected: translatableTexts.length,
              erhalten: translatedLines.length,
            });
            for (let j = 0; j < translatableTexts.length; j++) {
              try {
                const singleMessages = [
                  { role: "system", content: extendedSystemMessage },
                  { role: "user", content: translatableTexts[j] },
                ];
                const singleTranslation = await askAssistantTranslation(openai, model, singleMessages);
                batchResult[translatablePositions[j]] = singleTranslation.trim();
              } catch (err) {
                batchResult[translatablePositions[j]] = "";
              }
            }
          } else {
            for (let j = 0; j < translatableTexts.length; j++) {
              batchResult[translatablePositions[j]] = translatedLines[j].trim();
            }
          }

          // Aktualisiere den Kontext für Konsistenz
          const batchTranslationLines = batchRows.map((row, idx) => {
            const original = row["Vergleichstext Ursprungsversion"];
            const translated = batchResult[idx];
            return `Original: ${original} | Übersetzt: ${translated}`;
          });
          previousTranslations = previousTranslations.concat(batchTranslationLines).slice(-100);

          // Speichere die Übersetzungen in der entsprechenden Spalte
          for (let j = 0; j < batchRows.length; j++) {
            batchRows[j]["Text zur Übersetzung / Versionsanpassung"] = batchResult[j];
          }
        }

        // Aktualisiere den Fortschritt in Supabase
        const progress = Math.min(90, 10 + Math.floor((i / rows.length) * 80));
        await supabase
          .from("translation_jobs")
          .update({
            progress,
            updated_at: new Date().toISOString(),
          })
          .eq("id", jobId);
        logger.info("Fortschritt aktualisiert", { progress });
      }

      // QM-Check pro Zeile
      logger.info("Starte QM-Check");
      for (let index = 0; index < rows.length; index++) {
        const row = rows[index];
        const originalText = row["Vergleichstext Ursprungsversion"];
        const translatedText = row["Text zur Übersetzung / Versionsanpassung"];

        const qmCheckMessage =
          `The following translation is part of a questionnaire on the topic of '${survey_topic}' for the group '${respondent_group}'. ` +
          `The original text is in '${source_language}' and has been translated into '${target_language}'. ` +
          `Ensure that the translation is accurate, preserves context and technical elements. Always mark Brands and programming instructions/HTML codes such as {!%I-progress.txt%!} as True. ` +
          `Respond only with 'True' if the translation is correct, or 'False' if improvements are needed.`;

        const qmMessages = [
          { role: "system", content: qmCheckMessage },
          {
            role: "user",
            content: `Original Text: '${originalText}'\nTranslated Text: '${translatedText}'`,
          },
        ];

        try {
          const qmResult = await askAssistantQmCheck(openai, "gpt-4o", qmMessages);
          row["QMS"] = qmResult;
        } catch (err) {
          row["QMS"] = "False";
        }
        // Aktualisiere Fortschritt des QM-Checks
        const progress = 90 + Math.floor(((index + 1) / rows.length) * 10);
        await supabase
          .from("translation_jobs")
          .update({
            progress,
            updated_at: new Date().toISOString(),
          })
          .eq("id", jobId);
      }
      logger.info("QM-Check abgeschlossen");

      // Erstelle die Ergebnis-Excel-Datei
      const newWorkbook = XLSX.utils.book_new();
      const newWorksheet = XLSX.utils.json_to_sheet(rows);
      XLSX.utils.book_append_sheet(newWorkbook, newWorksheet, "Übersetzungen");
      const outputData = XLSX.write(newWorkbook, { bookType: "xlsx", type: "base64" });

      // Upload in Supabase Storage
      const storageBucket = "uebersetzung-output";
      const uploadResult = await supabase.storage
        .from(storageBucket)
        .upload(`${jobId}.xlsx`, Buffer.from(outputData, "base64"), {
          contentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          upsert: true,
        });
      if (uploadResult.error) {
        throw new Error(`Fehler beim Hochladen der Datei: ${uploadResult.error.message}`);
      }
      const publicUrlResult = supabase.storage
        .from(storageBucket)
        .getPublicUrl(`${jobId}.xlsx`);
      const publicUrl = publicUrlResult.data.publicUrl || "";
      logger.info("Datei erfolgreich hochgeladen und Link generiert", { publicUrl });

      // Setze den Job als abgeschlossen
      try {
        const updateResult = await supabase
          .from("translation_jobs")
          .update({
            status: "completed",
            progress: 100,
            file_url: publicUrl,
            updated_at: new Date().toISOString(),
            completed_at: new Date().toISOString(),
          })
          .eq("id", jobId);
        
        if (updateResult.error) {
          logger.error("Fehler beim Aktualisieren des Jobs", { 
            error: updateResult.error, 
            jobId 
          });
          throw new Error(`Fehler beim Aktualisieren des Jobs: ${updateResult.error.message}`);
        }
        
        logger.info("Job erfolgreich als abgeschlossen markiert", { 
          jobId, 
          resultUrl: publicUrl,
          status: "completed",
          timestamp: new Date().toISOString()
        });
      } catch (err) {
        logger.error("Ausnahmefehler beim Aktualisieren des Jobs", { error: err, jobId });
        throw err;
      }

      // E-Mail-Versand
      if (email) {
        try {
          logger.info("Sende E-Mail mit dem Übersetzungsergebnis", { email });
          
          // HTML-Inhalt für die E-Mail
          const htmlContent = `
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e9e9e9; border-radius: 5px;">
              <h1 style="color: #333; border-bottom: 1px solid #e9e9e9; padding-bottom: 10px;">Übersetzungsauftrag abgeschlossen</h1>
              <p style="font-size: 16px; line-height: 1.5;">Moin!</p>
              <p style="font-size: 16px; line-height: 1.5;">Deine Übersetzung für "${fileName}" wurde erfolgreich abgeschlossen.</p>
              <p style="font-size: 16px; line-height: 1.5;">Details zum Auftrag:</p>
              <ul style="font-size: 15px; line-height: 1.5;">
                <li>Quellsprache: ${source_language}</li>
                <li>Zielsprache: ${target_language}</li>
                <li>Abgeschlossen am: ${new Date().toLocaleDateString('de-DE')} um ${new Date().toLocaleTimeString('de-DE')}</li>
              </ul>
              <div style="margin: 30px 0; text-align: center;">
                <a href="${publicUrl}" style="background-color: #e2007a; color: white; padding: 12px 20px; text-decoration: none; border-radius: 4px; display: inline-block; font-weight: bold;">Übersetzung herunterladen</a>
              </div>
              <p style="font-size: 14px; color: #666; margin-top: 30px; border-top: 1px solid #e9e9e9; padding-top: 10px;">
                Dies ist eine automatisch generierte E-Mail. Bitte antworte nicht auf diese Nachricht.
              </p>
            </div>
          `;
          
          const emailResponse = await fetch(`${supabaseUrl}/functions/v1/send-email`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${supabaseKey}`,
            },
            body: JSON.stringify({
              to: email,
              subject: `Übersetzung abgeschlossen: ${fileName}`,
              content: htmlContent,
            }),
          });
          
          if (!emailResponse.ok) {
            const errorData = await emailResponse.text();
            logger.error("E-Mail-Versand fehlgeschlagen", { 
              error: errorData,
              status: emailResponse.status,
              statusText: emailResponse.statusText
            });
            // Fehler nur loggen, nicht werfen, damit der Job trotzdem als erfolgreich gilt
          } else {
            const responseData = await emailResponse.json();
            logger.info("E-Mail erfolgreich versendet", { 
              email, 
              messageId: responseData.id || "unbekannt",
              status: "success"
            });
          }
        } catch (err) {
          logger.error("Fehler beim E-Mail-Versand", { 
            error: err.message || err, 
            stack: err.stack
          });
          // Fehler nur loggen, nicht werfen, damit der Job trotzdem als erfolgreich gilt
        }
      }

      return {
        success: true,
        message: "Übersetzung und QM-Check erfolgreich abgeschlossen",
        jobId,
        resultUrl: publicUrl,
      } as TranslationResult;
    } catch (error) {
      // Fehlerbehandlung: Status auf 'error' setzen und Fehlermeldung speichern
      logger.error("Fehler bei der Jobverarbeitung", { error: error.message || error });
      
      try {
        await supabase
          .from("translation_jobs")
          .update({
            status: "error",
            error_message: error.message || "Unbekannter Fehler aufgetreten",
            updated_at: new Date().toISOString(),
          })
          .eq("id", jobId);
        
        logger.info("Fehler wurde in der Datenbank dokumentiert", { jobId });
      } catch (dbError) {
        logger.error("Fehler beim Aktualisieren des Fehlerstatus in der Datenbank", {
          originalError: error.message,
          dbError: dbError.message
        });
      }
      
      // Fehler weiterwerfen
      throw error;
    }
  },
});
