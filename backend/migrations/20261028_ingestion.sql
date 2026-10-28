-- Additive migration: preserves all jobs, saved applications and resume data.
begin;
alter table public.jobs add column if not exists expires_at timestamptz;
alter table public.jobs add column if not exists first_seen_at timestamptz default now();
alter table public.jobs add column if not exists employment_type text;
alter table public.jobs add column if not exists provider_id text;
alter table public.jobs add column if not exists source_url text;
alter table public.jobs add column if not exists location_restrictions text[] default '{}';
alter table public.jobs add column if not exists timezone_restrictions integer[] default '{}';
alter table public.jobs add column if not exists availability text not null default 'unverified';
create index if not exists idx_jobs_expiry on public.jobs(expires_at);

create table if not exists public.job_ingestion_state (
  id text primary key,
  lease_owner uuid,
  lease_until timestamptz,
  updated_at timestamptz not null default now(),
  sources jsonb not null default '{}'
);
create table if not exists public.job_fetch_runs (
  id uuid primary key,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  status text not null,
  sources jsonb not null default '{}'
);
alter table public.job_ingestion_state enable row level security;
alter table public.job_fetch_runs enable row level security;
revoke all on public.job_ingestion_state, public.job_fetch_runs from anon, authenticated;
grant all on public.job_ingestion_state, public.job_fetch_runs to service_role;

-- Cross-process lease: only the backend service role can claim an ingestion run.
create or replace function public.claim_job_refresh(p_owner uuid, p_seconds integer default 600)
returns boolean language plpgsql security definer set search_path = public as $$
declare changed integer;
begin
  if auth.role() is distinct from 'service_role' then
    raise exception 'service role required';
  end if;
  insert into public.job_ingestion_state(id, lease_owner, lease_until)
    values ('global', p_owner, now() + make_interval(secs => least(greatest(p_seconds, 30), 900)))
  on conflict(id) do update set lease_owner = excluded.lease_owner,
    lease_until = excluded.lease_until, updated_at = now()
    where job_ingestion_state.lease_until is null or job_ingestion_state.lease_until < now();
  get diagnostics changed = row_count;
  return changed = 1;
end;
$$;
revoke all on function public.claim_job_refresh(uuid, integer) from public, anon, authenticated;
grant execute on function public.claim_job_refresh(uuid, integer) to service_role;
commit;
