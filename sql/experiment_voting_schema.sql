-- Promptcraft experiment: point-allocation voting + heuristics
-- Apply in Supabase SQL editor after backup. Adjust if table names already exist.

-- ---------------------------------------------------------------------------
-- prompts: generation + heuristic fields (analytics; similarity optional/offline)
-- ---------------------------------------------------------------------------
ALTER TABLE prompts ADD COLUMN IF NOT EXISTS word_count int;
ALTER TABLE prompts ADD COLUMN IF NOT EXISTS prompt_sent_elapsed_seconds int;
ALTER TABLE prompts ADD COLUMN IF NOT EXISTS similarity_to_target real;
ALTER TABLE prompts ADD COLUMN IF NOT EXISTS similarity_method text;

-- ---------------------------------------------------------------------------
-- image_selections: snapshot at submission time
-- ---------------------------------------------------------------------------
ALTER TABLE image_selections ADD COLUMN IF NOT EXISTS prompt_index_at_selection int;
ALTER TABLE image_selections ADD COLUMN IF NOT EXISTS cumulative_word_count int;
ALTER TABLE image_selections ADD COLUMN IF NOT EXISTS heuristic_snapshot jsonb;
ALTER TABLE image_selections ADD COLUMN IF NOT EXISTS max_prompt_index_at_selection int;
ALTER TABLE image_selections ADD COLUMN IF NOT EXISTS selection_steps_back_from_latest int;

-- ---------------------------------------------------------------------------
-- Legacy single-vote table: optional archive; new writes go to point_allocations
-- ---------------------------------------------------------------------------
-- You may keep `votes` for historical data; new code should not insert into it.

-- ---------------------------------------------------------------------------
-- voting_rounds: one row per voting screen (1–10)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS voting_rounds (
  voting_round_id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  game_id           bigint NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
  voting_round_index int NOT NULL,
  kind              text NOT NULL CHECK (kind IN ('hardcoded', 'final')),
  fixture_set_key   text,
  target_image_url  text,
  started_at        timestamptz DEFAULT now(),
  ended_at          timestamptz,
  UNIQUE (game_id, voting_round_index)
);

CREATE INDEX IF NOT EXISTS idx_voting_rounds_game ON voting_rounds(game_id);

-- ---------------------------------------------------------------------------
-- voter_ballots: one ballot per voter per voting_round
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS voter_ballots (
  ballot_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  game_id           bigint NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
  voting_round_id   bigint NOT NULL REFERENCES voting_rounds(voting_round_id) ON DELETE CASCADE,
  voter_player_id   text NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
  UNIQUE (voting_round_id, voter_player_id)
);

CREATE INDEX IF NOT EXISTS idx_voter_ballots_round ON voter_ballots(voting_round_id);

-- ---------------------------------------------------------------------------
-- ballot_options: three slots; fixture_image_id for hardcoded analysis
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ballot_options (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ballot_id           bigint NOT NULL REFERENCES voter_ballots(ballot_id) ON DELETE CASCADE,
  slot_index          smallint NOT NULL CHECK (slot_index BETWEEN 1 AND 3),
  source              text NOT NULL CHECK (source IN ('fixture', 'player_submission')),
  fixture_image_id    text,
  image_url           text NOT NULL,
  owner_player_id     text REFERENCES players(player_id) ON DELETE SET NULL,
  prompt_id           bigint REFERENCES prompts(prompt_id) ON DELETE SET NULL,
  heuristic_snapshot  jsonb,
  UNIQUE (ballot_id, slot_index)
);

CREATE INDEX IF NOT EXISTS idx_ballot_options_ballot ON ballot_options(ballot_id);

-- ---------------------------------------------------------------------------
-- point_allocations: integers summing to 10
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS point_allocations (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ballot_id           bigint NOT NULL UNIQUE REFERENCES voter_ballots(ballot_id) ON DELETE CASCADE,
  game_id             bigint NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
  voting_round_id     bigint NOT NULL REFERENCES voting_rounds(voting_round_id) ON DELETE CASCADE,
  voter_player_id     text NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
  points_slot_1       int NOT NULL CHECK (points_slot_1 >= 0 AND points_slot_1 <= 10),
  points_slot_2       int NOT NULL CHECK (points_slot_2 >= 0 AND points_slot_2 <= 10),
  points_slot_3       int NOT NULL CHECK (points_slot_3 >= 0 AND points_slot_3 <= 10),
  submitted_at        timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT point_allocations_sum_10 CHECK (points_slot_1 + points_slot_2 + points_slot_3 = 10)
);

CREATE INDEX IF NOT EXISTS idx_point_allocations_round ON point_allocations(voting_round_id);

-- Timing: seconds from first allocation round start (round 1) and from current round start, at submit time
ALTER TABLE point_allocations ADD COLUMN IF NOT EXISTS seconds_since_session_start double precision;
ALTER TABLE point_allocations ADD COLUMN IF NOT EXISTS seconds_since_round_start double precision;
