-- Run this entire script in the Supabase SQL Editor:
-- https://supabase.com/dashboard/project/_/sql/new

-- Profiles table
create table if not exists public.profiles (
  user_id uuid references auth.users(id) primary key,
  name text,
  email text,
  skills text[] default '{}',
  experience_years int default 0,
  target_roles text[] default '{}',
  location text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- RLS for profiles
alter table public.profiles enable row level security;
drop policy if exists "Users can view own profile" on public.profiles;
create policy "Users can view own profile" on public.profiles for select using (auth.uid() = user_id);
drop policy if exists "Users can update own profile" on public.profiles;
create policy "Users can update own profile" on public.profiles for update using (auth.uid() = user_id);
drop policy if exists "Users can insert own profile" on public.profiles;
create policy "Users can insert own profile" on public.profiles for insert with check (auth.uid() = user_id);
drop policy if exists "Service role full access profiles" on public.profiles;
create policy "Service role full access profiles" on public.profiles for all using (auth.role() = 'service_role');

-- Resumes table
create table if not exists public.resumes (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users(id) not null,
  raw_text text,
  skills text[] default '{}',
  education jsonb default '[]',
  experience jsonb default '[]',
  projects jsonb default '[]',
  file_path text,
  parsed_at timestamptz default now()
);

-- RLS for resumes  
alter table public.resumes enable row level security;
drop policy if exists "Users can manage own resumes" on public.resumes;
create policy "Users can manage own resumes" on public.resumes for all using (auth.uid() = user_id);
drop policy if exists "Service role full access resumes" on public.resumes;
create policy "Service role full access resumes" on public.resumes for all using (auth.role() = 'service_role');

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (user_id, name, email)
  values (new.id, new.raw_user_meta_data->>'full_name', new.email);
  return new;
end;
$$ language plpgsql security definer set search_path = public;

-- Drop trigger if exists, then create
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Applications table
create table if not exists public.applications (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users(id) not null,
  job_id text not null,
  job_title text not null,
  company text not null,
  status text not null check (status in ('Saved', 'Applied', 'Interview', 'Offer', 'Rejected')),
  notes text default '',
  applied_date timestamptz default now(),
  updated_at timestamptz default now()
);

-- RLS for applications
alter table public.applications enable row level security;
drop policy if exists "Users can manage own applications" on public.applications;
create policy "Users can manage own applications" on public.applications for all using (auth.uid() = user_id);
drop policy if exists "Service role full access applications" on public.applications;
create policy "Service role full access applications" on public.applications for all using (auth.role() = 'service_role');

-- Shared job cache (user-specific data stays in the RLS-protected tables above).
create table if not exists public.jobs (
  id text primary key,
  title text not null,
  company text not null,
  location text not null default '',
  salary text,
  description text not null default '',
  url text not null default '',
  source text not null default '',
  posted_date text,
  tags text[] default '{}',
  job_type text,
  fetched_at timestamptz not null default now()
);
create index if not exists idx_jobs_fetched on public.jobs (fetched_at desc);
alter table public.jobs enable row level security;
drop policy if exists "Allow public read" on public.jobs;
create policy "Allow public read" on public.jobs for select using (true);
drop policy if exists "Allow service role insert/update" on public.jobs;
create policy "Allow service role insert/update" on public.jobs for all using (auth.role() = 'service_role');

-- Private PDF objects: each authenticated user owns only their UUID folder.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('resumes', 'resumes', false, 10485760, array['application/pdf'])
on conflict (id) do update set public = false,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "Read own resume PDFs" on storage.objects;
create policy "Read own resume PDFs" on storage.objects for select to authenticated
using (bucket_id = 'resumes' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "Upload own resume PDFs" on storage.objects;
create policy "Upload own resume PDFs" on storage.objects for insert to authenticated
with check (bucket_id = 'resumes' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "Update own resume PDFs" on storage.objects;
create policy "Update own resume PDFs" on storage.objects for update to authenticated
using (bucket_id = 'resumes' and (storage.foldername(name))[1] = auth.uid()::text)
with check (bucket_id = 'resumes' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "Delete own resume PDFs" on storage.objects;
create policy "Delete own resume PDFs" on storage.objects for delete to authenticated
using (bucket_id = 'resumes' and (storage.foldername(name))[1] = auth.uid()::text);
