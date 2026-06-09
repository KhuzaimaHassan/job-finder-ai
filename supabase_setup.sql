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
$$ language plpgsql security definer;

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
