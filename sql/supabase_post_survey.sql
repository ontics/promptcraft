-- Run once in Supabase SQL editor (or add to your migration pipeline).
-- Post-game survey fields on analytics `players` rows (same player_id + game_id as rest of app).

alter table public.players
  add column if not exists post_survey_free_q1 text,
  add column if not exists post_survey_free_q2 text,
  add column if not exists post_survey_free_q3 text,
  add column if not exists post_survey_free_q4 text,
  add column if not exists post_survey_likert_best_work text,
  add column if not exists post_survey_likert_effort text,
  add column if not exists post_survey_submitted_at timestamptz;

-- Adjust RLS/policies to match your existing `players` / service-role pattern.
