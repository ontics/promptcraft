-- Run in Supabase SQL editor after base post_survey columns exist.
-- Stores Likert matrices + single-choice from stories/post-game-survey-likert-matrices-and-text-color.md

alter table public.players
  add column if not exists post_survey_extended jsonb;
