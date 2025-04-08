// trigger_dev_job.js
import { TriggerClient, eventTrigger } from "@trigger.dev/sdk";
import { z } from "zod";
import { Resend } from "resend";
import OpenAI from "openai";
import ExcelJS from "exceljs";
import { createClient } from "@supabase/supabase-js";

export const client = new TriggerClient({
  id: "bonsai-translation-app",
  apiKey: process.env.TRIGGER_DEV_API_KEY,
});

const supabaseUrl = "https://tyggaqynkmujggfszrvc.supabase.co";
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
const supabase = createClient(supabaseUrl, supabaseKey);

const resend = new Resend(process.env.RESEND_API_KEY);

// Hilfsfunktion zum Aktualisieren des Fortschritts
async function updateProgress(jobId, progress, status = "processing") {
  try {
    await supabase
      .from("translation_jobs")
      .update({
        progress,
        status,
        updated_at: new Date().toISOString(),
        ...(status === "completed" ? { completed_at: new Date().toISOString() } : {}),
      })
      .eq("id", jobId);
  } catch (error) {
    console.error("Fehler beim Aktualisieren des Fortschritts:", error);
  }
}

// Hilfsfunktion für OpenAI API-Anfragen mit retry-Logik
async function callOpenAI(openai, model, messages, maxRetries = 3) {
  let retries = 0;
  
  while (retries < maxRetries) {
    try {
      const response = await openai.chat.completions.create({
        model: model,
        messages: messages,
      });
      
      return response.choices[0].message.content;
    } catch (error) {
      retries++;
      console.error(`OpenAI API Fehler (Versuch ${retries}/${maxRetries}):`, error);
      
      if (retries >= maxRetries) {
        throw error;
      }
      
      // Exponentielles Backoff
      await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, retries)));
    }
  }
}

client.defineJob({
  id: "translation-job",
  name: "Übersetzungsjob",
  version: "1.0.0",
  trigger: eventTrigger({
    name: "translation.request",
    schema: z.object({
      jobId: z.string(),
      fileUrl: z.string(),
      email: z.string().email(),
      sourceLanguage: z.string(),
      targetLanguage: z.string(),
      country: z.string(),
      respondentGroup: z.string(),
      surveyTopic: z.string(),
      surveyContent: z.string(),
      apiKey: z.string(),
      model: z.string(),
      batchSize: z.number(),
      systemMessage: z.string()
    })
  }),
  run: async (payload, io, ctx) => {
    try {
      await io.logger.info("Übersetzungsjob gestartet", { jobId: payload.jobId });
      
      // Fortschritt aktualisieren: Job gestartet
      await updateProgress(payload.jobId, 0.01);
      
      // OpenAI Client initialisieren
      const openai = new OpenAI({ apiKey: payload.apiKey });
      
      // Excel-Datei herunterladen
      await io.logger.info("Lade Excel-Datei herunter", { url: payload.fileUrl });
      const fileResponse = await fetch(payload.fileUrl);
      const fileArrayBuffer = await fileResponse.arrayBuffer();
      
      // Excel-Workbook laden
      const workbook = new ExcelJS.Workbook();
      await workbook.xlsx.load(fileArrayBuffer);
      const worksheet = workbook.getWorksheet(1);
      
      // Daten aus Excel extrahieren
      const rows = [];
      worksheet.eachRow((row, rowNumber) => {
        if (rowNumber === 1) return; // Header überspringen
        
        const originalText = row.getCell("Vergleichstext Ursprungsversion").value;
        rows.push({
          rowNumber,
          originalText,
          translatedText: null
        });
      });
      
      await io.logger.info(`${rows.length} Zeilen für die Übersetzung gefunden`);
      
      // Übersetzungskontext für Konsistenz
      let previousTranslations = [];
      
      // Übersetze in Batches
      const batchSize = payload.batchSize;
      const totalBatches = Math.ceil(rows.length / batchSize);
      
      for (let i = 0; i < rows.length; i += batchSize) {
        const batchNumber = Math.floor(i / batchSize) + 1;
        await io.logger.info(`Verarbeite Batch ${batchNumber}/${totalBatches}`);
        
        const batchRows = rows.slice(i, i + batchSize);
        const translatable = batchRows.filter(row => 
          typeof row.originalText === "string" && 
          row.originalText.trim() !== "" && 
          !/^\d+(\.\d+)?$/.test(row.originalText.trim())
        );
        
        if (translatable.length > 0) {
          // Systemanweisung mit bisherigen Übersetzungen ergänzen
          const extendedSystemMessage = `${payload.systemMessage}\n\nEarlier translations to remain consistent in the translation:\n${previousTranslations.join("\n")}`;
          
          // Texte mit Separator verbinden
          const separator = "|||";
          const joinedText = translatable.map(row => row.originalText).join(separator);
          
          // Übersetzung durchführen
          const translationResponse = await callOpenAI(
            openai,
            payload.model,
            [
              { role: "system", content: extendedSystemMessage },
              { role: "user", content: joinedText }
            ]
          );
          
          // Übersetzte Zeilen extrahieren und zuweisen
          const translatedLines = translationResponse.split(separator);
          
          // Prüfen, ob Anzahl der übersetzten Zeilen stimmt
          if (translatedLines.length !== translatable.length) {
            await io.logger.warn(`Mismatch in der Anzahl übersetzter Zeilen: ${translatedLines.length} vs. ${translatable.length}`);
            
            // Fallback: Einzelne Übersetzung für jede Zeile
            for (let j = 0; j < translatable.length; j++) {
              const singleResponse = await callOpenAI(
                openai,
                payload.model,
                [
                  { role: "system", content: extendedSystemMessage },
                  { role: "user", content: translatable[j].originalText }
                ]
              );
              
              translatable[j].translatedText = singleResponse.trim();
            }
          } else {
            // Übersetzte Zeilen zuweisen
            for (let j = 0; j < translatable.length; j++) {
              translatable[j].translatedText = translatedLines[j].trim();
            }
          }
          
          // Übersetzungskontext aktualisieren
          const newTranslations = translatable.map(row => 
            `Original: ${row.originalText} | Übersetzt: ${row.translatedText}`
          );
          previousTranslations = [...previousTranslations, ...newTranslations].slice(-100);
        }
        
        // Nicht übersetzbare Zeilen unverändert lassen
        for (const row of batchRows) {
          if (!row.translatedText && row.originalText) {
            row.translatedText = row.originalText;
          }
        }
        
        // Fortschritt aktualisieren
        const progress = Math.min(0.5 * (batchNumber / totalBatches), 0.5);
        await updateProgress(payload.jobId, progress);
      }
      
      await io.logger.info("Übersetzungen abgeschlossen, starte QM-Check");
      
      // QM-Check für jede übersetzte Zeile
      for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        if (!row.originalText || !row.translatedText) continue;
        
        // QM-Check System-Anweisung
        const qmCheckMessage = `
          The following translation is part of a questionnaire on the topic of '${payload.surveyTopic}' for the group '${payload.respondentGroup}'. 
          The original text is in '${payload.sourceLanguage}' and has been translated into '${payload.targetLanguage}'. 
          Ensure that the translation is accurate, retains the context of the survey, and that all programming codes or programming instructions like 'Screenout' and 'Quote', symbols, country ISO codes like DE, CZ, CH, FR, SP, PL, EN, etc., brands, and special characters are correctly handled. 
          Do not alter or misinterpret these elements. 
          For example, translations like ISO-Codes 'PL' to 'PL' (English to German), 'Elmex' to 'Elmex' (English to Spanish), 'Yes' to 'Tak' (English to Polish) oder 'No' to 'Nein' (English to German) should be marked as 'True'. 
          Programming codes like '&#10148' and html codes within curly braces should remain unchanged and should not be marked as 'False' if they are kept as is. 
          If the translation is correct according to these guidelines, respond with 'True'. If there is a mistake or if you think it could be translated better, respond with 'False'.
        `;
        
        try {
          const qmResult = await callOpenAI(
            openai,
            "gpt-4o",
            [
              { role: "system", content: qmCheckMessage },
              { 
                role: "user", 
                content: `Please check the following translation.\n\nOriginal Text: '${row.originalText}'\nTranslated Text: '${row.translatedText}'\n\nRespond only with 'True' or 'False' based on the accuracy and consistency of the translation.`
              }
            ]
          );
          
          row.qmCheck = qmResult.trim();
        } catch (error) {
          await io.logger.error(`QM-Check Fehler für Zeile ${i+1}`, { error: error.message });
          row.qmCheck = "Error";
        }
        
        // Fortschritt für QM-Check aktualisieren (50%-100%)
        const qmProgress = 0.5 + (0.5 * ((i + 1) / rows.length));
        await updateProgress(payload.jobId, qmProgress);
      }
      
      await io.logger.info("QM-Check abgeschlossen, erstelle Excel-Ausgabe");
      
      // Excel-Datei aktualisieren
      worksheet.getRow(1).getCell("Text zur Übersetzung / Versionsanpassung").value = "Text zur Übersetzung / Versionsanpassung";
      worksheet.getRow(1).getCell(worksheet.columnCount + 1).value = "QMS";
      
      for (const row of rows) {
        const excelRow = worksheet.getRow(row.rowNumber);
        excelRow.getCell("Text zur Übersetzung / Versionsanpassung").value = row.translatedText;
        excelRow.getCell(worksheet.columnCount).value = row.qmCheck || "";
      }
      
      // Excel-Datei schreiben
      const buffer = await workbook.xlsx.writeBuffer();
      
      // In Supabase speichern
      const fileName = `translated_${Date.now()}.xlsx`;
      const { data, error } = await supabase
        .storage
        .from("uebersetzung-output")
        .upload(`results/${fileName}`, buffer, {
          contentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          upsert: true
        });
      
      if (error) {
        throw new Error(`Fehler beim Speichern der Excel-Datei: ${error.message}`);
      }
      
      // Öffentliche URL für die Datei generieren
      const { data: fileUrlData } = await supabase
        .storage
        .from("uebersetzung-output")
        .getPublicUrl(`results/${fileName}`);
      
      // Job-Datensatz aktualisieren
      await supabase
        .from("translation_jobs")
        .update({
          file_url: fileUrlData.publicUrl,
          status: "completed",
          progress: 1,
          completed_at: new Date().toISOString()
        })
        .eq("id", payload.jobId);
      
      // E-Mail mit Resend verschicken
      await io.logger.info("Sende E-Mail mit dem Ergebnis");
      
      await resend.emails.send({
        from: "translation@bonsai-toolbox.de",
        to: payload.email,
        subject: "Deine Übersetzung ist fertig! 🎉",
        html: `
          <h1>Deine Übersetzung ist abgeschlossen!</h1>
          <p>Hallo,</p>
          <p>deine Übersetzung von ${payload.sourceLanguage} nach ${payload.targetLanguage} ist fertiggestellt.</p>
          <p>Du kannst die übersetzte Datei unter folgendem Link herunterladen:</p>
          <p><a href="${fileUrlData.publicUrl}" style="padding: 10px 20px; background-color: #4CAF50; color: white; text-decoration: none; border-radius: 5px;">Übersetzung herunterladen</a></p>
          <p>Der Link ist 7 Tage gültig.</p>
          <p>Vielen Dank für die Nutzung des bonsAI Übersetzungsbüros!</p>
          <p>Beste Grüße,<br>Dein bonsAI Team</p>
        `
      });
      
      return { success: true, fileUrl: fileUrlData.publicUrl };
    } catch (error) {
      await io.logger.error("Fehler bei der Verarbeitung", { error: error.message, stack: error.stack });
      
      // Status auf "failed" setzen
      await supabase
        .from("translation_jobs")
        .update({
          status: "failed",
          updated_at: new Date().toISOString()
        })
        .eq("id", payload.jobId);
      
      // Fehlerbenachrichtigung per E-Mail
      try {
        await resend.emails.send({
          from: "translation@bonsai-toolbox.de",
          to: payload.email,
          subject: "Fehler bei deiner Übersetzung",
          html: `
            <h1>Fehler bei der Übersetzung</h1>
            <p>Hallo,</p>
            <p>leider ist bei der Verarbeitung deiner Übersetzung ein Fehler aufgetreten.</p>
            <p>Fehlermeldung: ${error.message}</p>
            <p>Bitte versuche es später noch einmal oder kontaktiere den Support, wenn das Problem weiterhin besteht.</p>
            <p>Beste Grüße,<br>Dein bonsAI Team</p>
          `
        });
      } catch (emailError) {
        await io.logger.error("Fehler beim Senden der Fehlerbenachrichtigung", { error: emailError.message });
      }
      
      throw error;
    }
  }
}); 