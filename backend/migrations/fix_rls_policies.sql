-- ============================================================
-- FIX: Broken RLS policies that used "using (true)" without 
-- role checks — allowing ANY user to access ALL data.
-- 
-- Run this in Supabase Dashboard → SQL Editor
-- ============================================================

-- 1. Drop the broken "full access" policies
DROP POLICY IF EXISTS "Service role full access profiles" ON public.profiles;
DROP POLICY IF EXISTS "Service role full access resumes" ON public.resumes;
DROP POLICY IF EXISTS "Service role full access applications" ON public.applications;

-- 2. Recreate with proper service_role check
CREATE POLICY "Service role full access profiles"
  ON public.profiles FOR ALL
  USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access resumes"
  ON public.resumes FOR ALL
  USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access applications"
  ON public.applications FOR ALL
  USING (auth.role() = 'service_role');

-- 3. Verify user-facing policies are correct
-- Users should only access their own data
-- (These should already exist, but recreate if missing)

DO $$
BEGIN
  -- Profiles: users can read/update their own profile
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can view own profile' AND tablename = 'profiles') THEN
    CREATE POLICY "Users can view own profile"
      ON public.profiles FOR SELECT
      USING (auth.uid() = user_id);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can update own profile' AND tablename = 'profiles') THEN
    CREATE POLICY "Users can update own profile"
      ON public.profiles FOR UPDATE
      USING (auth.uid() = user_id);
  END IF;

  -- Resumes
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can view own resume' AND tablename = 'resumes') THEN
    CREATE POLICY "Users can view own resume"
      ON public.resumes FOR SELECT
      USING (auth.uid() = user_id);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can manage own resume' AND tablename = 'resumes') THEN
    CREATE POLICY "Users can manage own resume"
      ON public.resumes FOR ALL
      USING (auth.uid() = user_id);
  END IF;

  -- Applications
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can view own applications' AND tablename = 'applications') THEN
    CREATE POLICY "Users can view own applications"
      ON public.applications FOR SELECT
      USING (auth.uid() = user_id);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can manage own applications' AND tablename = 'applications') THEN
    CREATE POLICY "Users can manage own applications"
      ON public.applications FOR ALL
      USING (auth.uid() = user_id);
  END IF;
END $$;
