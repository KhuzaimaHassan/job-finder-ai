-- ============================================================
-- Job Finder AI — Supabase Jobs Table Migration
-- Run this once in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

CREATE TABLE IF NOT EXISTS public.jobs (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    company     TEXT NOT NULL,
    location    TEXT NOT NULL DEFAULT '',
    salary      TEXT,
    description TEXT NOT NULL DEFAULT '',
    url         TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL DEFAULT '',
    posted_date TEXT,
    tags        TEXT[] DEFAULT '{}',
    job_type    TEXT,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast full-text search on title + company
CREATE INDEX IF NOT EXISTS idx_jobs_title   ON public.jobs USING gin(to_tsvector('english', title));
CREATE INDEX IF NOT EXISTS idx_jobs_source  ON public.jobs (source);
CREATE INDEX IF NOT EXISTS idx_jobs_fetched ON public.jobs (fetched_at DESC);

-- Allow public read (the API reads jobs for all users)
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read" ON public.jobs
    FOR SELECT USING (true);

CREATE POLICY "Allow service role insert/update" ON public.jobs
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================
-- Done! Go back to your terminal and run the scraper.
-- ============================================================
