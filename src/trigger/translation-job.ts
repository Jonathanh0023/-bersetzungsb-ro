import { task } from "@trigger.dev/sdk/v3";
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
        logger.info("Fortschritt aktualisiert", { progress, batch: i / batch_size + 1 });
      }

      // QMS-Spalte ergänzen (falls sie nicht existiert)
      if (!("QMS" in rows[0])) {
        for (const row of rows) {
          row["QMS"] = "";
        }
      }

      // Qualitätssicherung und QMS-Prüfung für jede Übersetzung
      logger.info("Starte Qualitätsprüfung");
      for (let i = 0; i < rows.length; i++) {
        const source = rows[i]["Vergleichstext Ursprungsversion"];
        const target = rows[i]["Text zur Übersetzung / Versionsanpassung"];

        if (source && target && source.trim() !== target.trim()) {
          try {
            const qmCheckMessages = [
              {
                role: "system",
                content: `You are a quality assurance specialist checking translations from ${source_language} to ${target_language}. Your job is to identify potential issues with the translation such as:
                1. Mistranslations or inaccuracies
                2. Missing content
                3. Awkward phrasing or grammatical errors
                4. Terminology consistency issues

                If you find any issues, describe them briefly. If the translation looks good, just respond with "OK".
                Be concise and to the point - your entire response should not exceed 100 characters.
                Remember: Only respond with "OK" if there are no issues with the translation.`,
              },
              {
                role: "user",
                content: `Original (${source_language}): ${source}\n\nTranslation (${target_language}): ${target}`,
              },
            ];

            const qmCheckResult = await askAssistantQmCheck(openai, model, qmCheckMessages);
            if (qmCheckResult.toLowerCase() !== "ok") {
              rows[i]["QMS"] = qmCheckResult;
            }
          } catch (error) {
            logger.error("Fehler bei QM-Check", { row: i, error });
          }
        }

        // Aktualisiere den Fortschritt in Supabase für QM-Checks
        if (i % 10 === 0 || i === rows.length - 1) {
          const progress = Math.min(100, 90 + Math.floor((i / rows.length) * 10));
          await supabase
            .from("translation_jobs")
            .update({
              progress,
              updated_at: new Date().toISOString(),
            })
            .eq("id", jobId);
          logger.info("QM-Fortschritt aktualisiert", { progress, qmRow: i });
        }
      }

      // Rückkonvertierung in Excel
      logger.info("Konvertiere Daten zurück in Excel");
      const newWorksheet = XLSX.utils.json_to_sheet(rows);
      const newWorkbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(newWorkbook, newWorksheet, "Translated");
      const excelBuffer = XLSX.write(newWorkbook, { type: "buffer", bookType: "xlsx" });

      // Dateiname generieren
      const originalName = fileName || "translation.xlsx";
      const fileNameParts = originalName.split('.');
      fileNameParts.pop(); // Entferne die Erweiterung
      const baseFileName = fileNameParts.join('.');
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const newFileName = `${baseFileName}_translated_${timestamp}.xlsx`;

      // Datei in Supabase Storage hochladen
      logger.info("Lade übersetzte Datei in Supabase Storage hoch");
      const { data: uploadData, error: uploadError } = await supabase.storage
        .from("uebersetzung-output")
        .upload(`${jobId}/${newFileName}`, excelBuffer, {
          contentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          upsert: true,
        });

      if (uploadError) {
        throw new Error(`Fehler beim Hochladen der Datei: ${uploadError.message}`);
      }

      // Öffentlichen URL generieren
      const { data: urlData } = await supabase.storage
        .from("uebersetzung-output")
        .getPublicUrl(`${jobId}/${newFileName}`);

      // Job als abgeschlossen markieren
      await supabase
        .from("translation_jobs")
        .update({
          status: "completed",
          progress: 100,
          file_url: urlData.publicUrl,
          updated_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
        })
        .eq("id", jobId);

      // Sende E-Mail-Benachrichtigung, falls eine E-Mail-Adresse angegeben wurde
      if (email) {
        try {
          logger.info("Sende E-Mail-Benachrichtigung", { email });
          const emailResponse = await fetch(`${supabaseUrl}/functions/v1/send-email`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Authorization": `Bearer ${supabaseKey}`
            },
            body: JSON.stringify({
              email,
              fileUrl: urlData.publicUrl,
              originalFilename: fileName,
              jobId
            })
          });

          if (!emailResponse.ok) {
            const emailError = await emailResponse.text();
            logger.error("Fehler beim Senden der E-Mail", { error: emailError });
          } else {
            logger.info("E-Mail erfolgreich gesendet");
          }
        } catch (emailError) {
          logger.error("Fehler beim Senden der E-Mail", { error: emailError });
        }
      }

      logger.info("Aufgabe erfolgreich abgeschlossen", { jobId, fileUrl: urlData.publicUrl });
      return {
        success: true,
        message: "Translation completed successfully",
        jobId,
        resultUrl: urlData.publicUrl,
      } as TranslationResult;

    } catch (error) {
      logger.error("Unerwarteter Fehler bei der Verarbeitung", { jobId, error });

      // In Supabase als Fehler markieren
      await supabase
        .from("translation_jobs")
        .update({
          status: "error",
          error_message: `Fehler: ${error.message || "Unbekannter Fehler"}`,
          updated_at: new Date().toISOString(),
        })
        .eq("id", jobId);

      // Fehler zurückgeben
      return {
        success: false,
        message: `Error: ${error.message || "Unknown error"}`,
        jobId,
      } as TranslationResult;
    }
  },
});

// Event-Listener für das Initiieren einer Übersetzung
export const translationTriggered = translationTask.on({
  id: "translation-requested",
  event: "translation.requested",
  run: async (event, ctx) => {
    return {};
  },
});
