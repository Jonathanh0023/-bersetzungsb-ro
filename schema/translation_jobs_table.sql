-- translation_jobs Tabelle in Supabase
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

-- Füge RLS-Richtlinien hinzu (optional)
ALTER TABLE public.translation_jobs ENABLE ROW LEVEL SECURITY;

-- Öffentliche Zugriffspolitik für Lesen
CREATE POLICY "Allow public read" ON public.translation_jobs
  FOR SELECT USING (true);

-- Öffentliche Zugriffspolitik für Einfügen/Aktualisieren von Supabase Edge Funktionen
CREATE POLICY "Allow service role to insert/update" ON public.translation_jobs
  FOR ALL USING (auth.role() = 'service_role'); 