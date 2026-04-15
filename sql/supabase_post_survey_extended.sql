-- Run after sql/supabase_post_survey.sql.
-- Stores additional matrix responses for the post-game survey.

alter table public.players
  add column if not exists post_survey_extended jsonb;
