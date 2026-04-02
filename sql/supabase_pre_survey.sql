-- Run once in Supabase SQL editor (or add to your migration pipeline).
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

-- Adjust policies to match your existing `players` / service-role pattern.
-- If the app uses the service role key only, RLS may already be bypassed.
