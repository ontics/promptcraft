-- Run once in Supabase SQL editor (or add to your migration pipeline).
-- Prerequisite: core tables must exist (run sql/bootstrap_core_schema.sql first on a new project).
-- Pre-survey answers: copied from pre_survey_pending onto players when the game starts.

alter table public.players
  add column if not exists pre_survey_proficiency text,
  add column if not exists pre_survey_frequency text,
  add column if not exists pre_survey_skills_text text,
  add column if not exists pre_survey_submitted_at timestamptz;

create table if not exists public.pre_survey_pending (
  player_id text primary key,
  proficiency text not null,
  frequency text not null,
  skills_text text not null,
  submitted_at timestamptz not null
);

alter table public.pre_survey_pending enable row level security;

drop policy if exists "Allow all operations on pre_survey_pending" on public.pre_survey_pending;
create policy "Allow all operations on pre_survey_pending" on public.pre_survey_pending
  for all using (true) with check (true);

-- Adjust policies to match your existing `players` / service-role pattern if needed.
