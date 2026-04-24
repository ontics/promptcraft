"""
Database helper module for PromptCraft analytics.
Handles Supabase database and storage operations.
"""
import os
import base64
import threading
from datetime import datetime
from supabase import create_client, Client
from typing import Any, List, Optional, Dict
import io
from PIL import Image

# Initialize Supabase client
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')

if supabase_url and supabase_key:
    supabase: Optional[Client] = create_client(supabase_url, supabase_key)
else:
    supabase = None
    print("⚠️  WARNING: Supabase credentials not found. Database logging disabled.")


def is_configured() -> bool:
    """Check if Supabase is configured."""
    return supabase is not None


# In-memory cache for game_id and round_id to avoid DB lookups
_game_id_cache: Dict[str, int] = {}  # session_id -> game_id
_round_id_cache: Dict[tuple, int] = {}  # (game_id, round_number) -> round_id


def create_game(total_players: int) -> Optional[int]:
    """
    Create a new game session in the database.
    Returns game_id if successful, None otherwise.
    """
    if not is_configured():
        return None
    
    try:
        result = supabase.table('games').insert({
            'started_at': datetime.utcnow().isoformat(),
            'total_players': total_players,
            'rounds_completed': 0
        }).execute()
        
        if result.data:
            game_id = result.data[0]['game_id']
            print(f"✅ Created game session: game_id={game_id}")
            return game_id
    except Exception as e:
        print(f"❌ Error creating game: {e}")
    return None


def end_game(game_id: int, rounds_completed: int):
    """Mark a game as ended in the database. Idempotent - won't duplicate if already ended."""
    if not is_configured() or not game_id:
        return
    
    try:
        # Check if game is already ended to avoid duplicate calls
        result = supabase.table('games').select('ended_at').eq('game_id', game_id).execute()
        if result.data and result.data[0].get('ended_at'):
            # Game already ended, skip
            return
        
        supabase.table('games').update({
            'ended_at': datetime.utcnow().isoformat(),
            'rounds_completed': rounds_completed
        }).eq('game_id', game_id).execute()
        print(f"✅ Ended game: game_id={game_id}")
    except Exception as e:
        print(f"❌ Error ending game: {e}")


def create_round(game_id: int, round_number: int) -> Optional[int]:
    """
    Create a new round in the database.
    Returns round_id if successful, None otherwise.
    Note: target_description removed - use round_number as proxy for target image in analytics.
    """
    if not is_configured() or not game_id:
        return None
    
    try:
        result = supabase.table('rounds').insert({
            'game_id': game_id,
            'round_number': round_number,
            'started_at': datetime.utcnow().isoformat()
        }).execute()
        
        if result.data:
            round_id = result.data[0]['round_id']
            _round_id_cache[(game_id, round_number)] = round_id
            print(f"✅ Created round: round_id={round_id}, game_id={game_id}, round={round_number}")
            return round_id
    except Exception as e:
        print(f"❌ Error creating round: {e}")
    return None


def end_round(round_id: int):
    """Mark a round as ended in the database. Idempotent - won't duplicate if already ended."""
    if not is_configured() or not round_id:
        return
    
    try:
        # Check if round is already ended to avoid duplicate calls
        result = supabase.table('rounds').select('ended_at').eq('round_id', round_id).execute()
        if result.data and result.data[0].get('ended_at'):
            # Round already ended, skip
            return
        
        supabase.table('rounds').update({
            'ended_at': datetime.utcnow().isoformat()
        }).eq('round_id', round_id).execute()
        print(f"✅ Ended round: round_id={round_id}")
    except Exception as e:
        print(f"❌ Error ending round: {e}")


def save_pre_survey_pending(
    player_id: str,
    proficiency: str,
    frequency: str,
    skills_text: str,
) -> bool:
    """
    Store pre-survey answers before a game_id exists (lobby).
    Flushed onto the `players` row when create_player runs after the game starts.
    """
    if not is_configured() or not player_id:
        return False
    try:
        now = datetime.utcnow().isoformat()
        supabase.table('pre_survey_pending').upsert(
            {
                'player_id': player_id,
                'proficiency': proficiency,
                'frequency': frequency,
                'skills_text': skills_text,
                'submitted_at': now,
            },
            on_conflict='player_id',
        ).execute()
        print(f"✅ Saved pre_survey_pending for player {player_id[:8]}...")
        return True
    except Exception as e:
        print(f"❌ Error saving pre_survey_pending: {e}")
        return False


def update_player_pre_survey(
    game_id: int,
    player_id: str,
    proficiency: str,
    frequency: str,
    skills_text: str,
) -> bool:
    """Write pre-survey columns on the analytics `players` row (game already created)."""
    if not is_configured() or not game_id or not player_id:
        return False
    try:
        now = datetime.utcnow().isoformat()
        supabase.table('players').update(
            {
                'pre_survey_proficiency': proficiency,
                'pre_survey_frequency': frequency,
                'pre_survey_skills_text': skills_text,
                'pre_survey_submitted_at': now,
            }
        ).eq('player_id', player_id).eq('game_id', game_id).execute()
        print(f"✅ Updated pre-survey on players row for {player_id[:8]}... game_id={game_id}")
        return True
    except Exception as e:
        print(f"❌ Error updating player pre-survey: {e}")
        return False


def player_has_completed_post_survey(game_id: int, player_id: str) -> bool:
    """True if post_survey_submitted_at is set for this player row and game."""
    if not is_configured() or not game_id or not player_id:
        return False
    try:
        result = (
            supabase.table('players')
            .select('post_survey_submitted_at')
            .eq('game_id', game_id)
            .eq('player_id', player_id)
            .execute()
        )
        if result.data and result.data[0].get('post_survey_submitted_at'):
            return True
    except Exception as e:
        print(f"❌ Error checking post-survey: {e}")
    return False


def update_player_post_survey(
    game_id: int,
    player_id: str,
    free_q1: str,
    free_q2: str,
    free_q3: str,
    free_q4: str,
    likert_best_work: str,
    likert_effort: str,
    extended: Optional[Dict[str, Any]] = None,
) -> bool:
    """Persist post-game survey answers on the analytics `players` row."""
    if not is_configured() or not game_id or not player_id:
        return False
    try:
        now = datetime.utcnow().isoformat()
        row = {
            'post_survey_free_q1': free_q1,
            'post_survey_free_q2': free_q2,
            'post_survey_free_q3': free_q3,
            'post_survey_free_q4': free_q4,
            'post_survey_likert_best_work': likert_best_work,
            'post_survey_likert_effort': likert_effort,
            'post_survey_submitted_at': now,
        }
        if extended is not None:
            row['post_survey_extended'] = extended
        supabase.table('players').update(row).eq('player_id', player_id).eq('game_id', game_id).execute()
        print(f"✅ Saved post-survey for player {player_id[:8]}... game_id={game_id}")
        return True
    except Exception as e:
        print(f"❌ Error updating post-survey: {e}")
        if extended is not None and 'post_survey_extended' in str(e).lower():
            try:
                fallback = {
                    'post_survey_free_q1': free_q1,
                    'post_survey_free_q2': free_q2,
                    'post_survey_free_q3': free_q3,
                    'post_survey_free_q4': free_q4,
                    'post_survey_likert_best_work': likert_best_work,
                    'post_survey_likert_effort': likert_effort,
                    'post_survey_submitted_at': now,
                }
                supabase.table('players').update(fallback).eq('player_id', player_id).eq('game_id', game_id).execute()
                print(f"✅ Saved post-survey (without extended JSON) for player {player_id[:8]}... game_id={game_id}")
                return True
            except Exception as e2:
                print(f"❌ Error updating post-survey fallback: {e2}")
        return False


def flush_pre_survey_pending_to_player(player_id: str, game_id: int) -> None:
    """Copy lobby-time pre-survey from pre_survey_pending onto `players`, then remove pending."""
    if not is_configured() or not game_id or not player_id:
        return
    try:
        result = (
            supabase.table('pre_survey_pending')
            .select('proficiency, frequency, skills_text, submitted_at')
            .eq('player_id', player_id)
            .execute()
        )
        if not result.data:
            return
        row = result.data[0]
        supabase.table('players').update(
            {
                'pre_survey_proficiency': row.get('proficiency'),
                'pre_survey_frequency': row.get('frequency'),
                'pre_survey_skills_text': row.get('skills_text'),
                'pre_survey_submitted_at': row.get('submitted_at'),
            }
        ).eq('player_id', player_id).eq('game_id', game_id).execute()
        supabase.table('pre_survey_pending').delete().eq('player_id', player_id).execute()
        print(f"✅ Flushed pre_survey_pending → players for {player_id[:8]}...")
    except Exception as e:
        print(f"❌ Error flushing pre_survey_pending: {e}")


def upsert_experiment_pre_survey(
    player_id: str,
    proficiency: str,
    frequency: str,
    skills_text: str,
    game_id: Optional[int] = None,
) -> bool:
    """Row in experiment_pre_surveys (one per player per game_id; game_id null until game starts)."""
    if not is_configured() or not player_id:
        return False
    try:
        now = datetime.utcnow().isoformat()
        row: Dict[str, Any] = {
            'player_id': player_id,
            'proficiency': proficiency,
            'frequency': frequency,
            'skills_text': skills_text,
            'submitted_at': now,
        }
        if game_id is not None:
            row['game_id'] = game_id
        supabase.table('experiment_pre_surveys').upsert(row, on_conflict='player_id').execute()
        print(f"✅ experiment_pre_surveys upsert player={player_id[:8]}...")
        return True
    except Exception as e:
        print(f"❌ Error upserting experiment_pre_surveys: {e}")
        return False


def link_pre_survey_response_to_game(player_id: str, game_id: int) -> None:
    """Set game_id on the player's pre-survey row after the game is created."""
    if not is_configured() or not game_id or not player_id:
        return
    try:
        supabase.table('experiment_pre_surveys').update({'game_id': game_id}).eq(
            'player_id', player_id
        ).execute()
    except Exception as e:
        print(f"❌ Error linking experiment_pre_surveys game_id: {e}")


def create_player(game_id: int, player_id: str, player_name: str, condition: Optional[str] = None, character: Optional[str] = None):
    """Create or update a player in the database."""
    if not is_configured() or not game_id:
        return
    
    try:
        # Check if player already exists
        existing = supabase.table('players').select('player_id').eq('player_id', player_id).execute()
        
        if existing.data:
            row = {
                'game_id': game_id,
                'player_name': player_name,
                'condition': condition,
                'character': character,
            }
            supabase.table('players').update(row).eq('player_id', player_id).execute()
        else:
            ins = {
                'player_id': player_id,
                'game_id': game_id,
                'player_name': player_name,
                'condition': condition,
                'character': character,
                'joined_at': datetime.utcnow().isoformat(),
            }
            supabase.table('players').insert(ins).execute()
        
        _game_id_cache[player_id] = game_id
        print(f"✅ Created/updated player: {player_id} ({player_name})")
        flush_pre_survey_pending_to_player(player_id, game_id)
        link_pre_survey_response_to_game(player_id, game_id)
        link_onboarding_practice_vote_to_game(player_id, game_id)
    except Exception as e:
        print(f"❌ Error creating player: {e}")


def save_onboarding_practice_vote(
    player_id: str,
    player_name: str,
    p1: int,
    p2: int,
    p3: int,
) -> bool:
    """Upsert onboarding practice point distribution for a player (before or after game_id exists)."""
    if not is_configured() or not player_id:
        return False
    try:
        now = datetime.utcnow().isoformat()
        existing = (
            supabase.table('onboarding_practice_votes')
            .select('game_id')
            .eq('player_id', player_id)
            .execute()
        )
        game_id_val = None
        if existing.data:
            game_id_val = existing.data[0].get('game_id')
        row = {
            'player_id': player_id,
            'player_name': player_name,
            'points_slot_1': p1,
            'points_slot_2': p2,
            'points_slot_3': p3,
            'submitted_at': now,
        }
        if game_id_val is not None:
            row['game_id'] = game_id_val
        supabase.table('onboarding_practice_votes').upsert(row, on_conflict='player_id').execute()
        print(f"✅ Saved onboarding_practice_vote for player {player_id[:8]}...")
        return True
    except Exception as e:
        print(f"❌ Error saving onboarding_practice_vote: {e}")
        return False


def link_onboarding_practice_vote_to_game(player_id: str, game_id: int) -> None:
    """Attach game_id to an existing onboarding practice vote row when the player joins analytics `players`."""
    if not is_configured() or not game_id or not player_id:
        return
    try:
        supabase.table('onboarding_practice_votes').update({'game_id': game_id}).eq(
            'player_id', player_id
        ).execute()
    except Exception as e:
        print(f"❌ Error linking onboarding_practice_vote to game: {e}")


def upload_image_to_storage(image_bytes: bytes, file_path: str) -> Optional[str]:
    """
    Upload an image to Supabase Storage.
    Returns public URL if successful, None otherwise.
    
    Args:
        image_bytes: Image file bytes
        file_path: Path within the bucket (e.g., "1/abc123/1/42.png")
    """
    if not is_configured():
        return None
    
    try:
        # Upload to Supabase Storage
        result = supabase.storage.from_('generated-images').upload(
            file_path,
            image_bytes,
            file_options={"content-type": "image/png"}
        )
        
        # Get public URL
        url = supabase.storage.from_('generated-images').get_public_url(file_path)
        print(f"✅ Uploaded image to Storage: {file_path} ({len(image_bytes)} bytes)")
        return url
    except Exception as e:
        print(f"❌ Error uploading image to Storage: {e}")
        print(f"   File path: {file_path}")
        print(f"   File size: {len(image_bytes)} bytes")
        return None


def save_prompt_sync(game_id: int, round_id: int, player_id: str, prompt_index: int, 
                     prompt_text: str, image_url: Optional[str], ai_response: Optional[str],
                     submitted_at: Optional[datetime] = None,
                     image_generated_at: Optional[datetime] = None,
                     error_type: Optional[str] = None,
                     error_message: Optional[str] = None,
                     finish_reason: Optional[str] = None,
                     file_size_kb: Optional[float] = None,
                     safety_ratings: Optional[dict] = None,
                     word_count: Optional[int] = None,
                     prompt_sent_elapsed_seconds: Optional[int] = None) -> Optional[int]:
    """
    Save a prompt and image to the database (synchronous).
    Returns prompt_id if successful, None otherwise.
    Note: is_refinement removed - can be determined from prompt_index >= 2
    """
    if not is_configured() or not game_id or not round_id:
        return None
    
    try:
        data = {
            'player_id': player_id,
            'round_id': round_id,
            'game_id': game_id,
            'prompt_index': prompt_index,
            'prompt_text': prompt_text,
            'ai_response': ai_response
        }
        
        if submitted_at:
            data['submitted_at'] = submitted_at.isoformat()
        if image_generated_at:
            data['image_generated_at'] = image_generated_at.isoformat()
        if image_url:
            data['image_url'] = image_url
        
        # Error tracking fields
        if error_type:
            data['error_type'] = error_type
        if error_message:
            data['error_message'] = error_message
        if finish_reason:
            data['finish_reason'] = finish_reason
        if file_size_kb is not None:
            data['file_size_kb'] = file_size_kb
        if safety_ratings:
            data['safety_ratings'] = safety_ratings
        if word_count is not None:
            data['word_count'] = word_count
        if prompt_sent_elapsed_seconds is not None:
            data['prompt_sent_elapsed_seconds'] = prompt_sent_elapsed_seconds
        
        result = supabase.table('prompts').insert(data).execute()
        
        if result.data:
            prompt_id = result.data[0]['prompt_id']
            print(f"✅ Saved prompt: prompt_id={prompt_id}, player={player_id}, index={prompt_index}, error_type={error_type}")
            return prompt_id
    except Exception as e:
        print(f"❌ Error saving prompt: {e}")
    return None


def update_prompt_image_url(prompt_id: int, image_url: str):
    """Update the image_url for a prompt after async upload completes."""
    if not is_configured() or not prompt_id:
        return
    
    try:
        supabase.table('prompts').update({
            'image_url': image_url
        }).eq('prompt_id', prompt_id).execute()
        print(f"✅ Updated prompt image URL: prompt_id={prompt_id}")
    except Exception as e:
        print(f"❌ Error updating prompt image URL: {e}")


def save_image_selection(
    player_id: str,
    round_id: int,
    game_id: int,
    prompt_id: int,
    prompt_index_at_selection: Optional[int] = None,
    cumulative_word_count: Optional[int] = None,
    max_prompt_index_at_selection: Optional[int] = None,
    selection_steps_back_from_latest: Optional[int] = None,
    heuristic_snapshot: Optional[dict] = None,
):
    """Save a player's image selection. Uses upsert to handle duplicate selections gracefully."""
    if not is_configured() or not game_id or not round_id:
        return
    
    try:
        row = {
            'player_id': player_id,
            'round_id': round_id,
            'game_id': game_id,
            'prompt_id': prompt_id,
            'selected_at': datetime.utcnow().isoformat(),
        }
        if prompt_index_at_selection is not None:
            row['prompt_index_at_selection'] = prompt_index_at_selection
        if cumulative_word_count is not None:
            row['cumulative_word_count'] = cumulative_word_count
        if max_prompt_index_at_selection is not None:
            row['max_prompt_index_at_selection'] = max_prompt_index_at_selection
        if selection_steps_back_from_latest is not None:
            row['selection_steps_back_from_latest'] = selection_steps_back_from_latest
        if heuristic_snapshot is not None:
            row['heuristic_snapshot'] = heuristic_snapshot
        supabase.table('image_selections').upsert(row).execute()
        print(f"✅ Saved image selection: player={player_id}, prompt_id={prompt_id}")
    except Exception as e:
        print(f"❌ Error saving image selection: {e}")


def save_vote(voter_id: str, voted_for_player_id: str, voted_for_prompt_id: int, 
              round_id: int, game_id: int):
    """Deprecated: single-vote model. New experiment uses save_point_allocation."""
    if not is_configured() or not game_id or not round_id:
        return
    try:
        supabase.table('votes').insert({
            'voter_id': voter_id,
            'voted_for_player_id': voted_for_player_id,
            'voted_for_prompt_id': voted_for_prompt_id,
            'round_id': round_id,
            'game_id': game_id,
            'voted_at': datetime.utcnow().isoformat()
        }).execute()
        print(f"✅ Saved vote: voter={voter_id}, voted_for_prompt={voted_for_prompt_id}")
    except Exception as e:
        print(f"❌ Error saving vote: {e}")


def find_voting_round_id_by_game_fixture_key(game_id: int, fixture_set_key: str) -> Optional[int]:
    """Lookup shared hardcoded vignette row: stable identity for cross-player analytics."""
    if not is_configured() or not game_id or not fixture_set_key:
        return None
    try:
        r = (
            supabase.table('voting_rounds')
            .select('voting_round_id')
            .eq('game_id', game_id)
            .eq('fixture_set_key', fixture_set_key)
            .eq('kind', 'hardcoded')
            .limit(1)
            .execute()
        )
        if r.data:
            return int(r.data[0]['voting_round_id'])
    except Exception as e:
        print(f"❌ Error find_voting_round_id_by_game_fixture_key: {e}")
    return None


def find_voting_round_id_final(game_id: int) -> Optional[int]:
    """Shared final allocation row (round 10) for this game."""
    if not is_configured() or not game_id:
        return None
    try:
        r = (
            supabase.table('voting_rounds')
            .select('voting_round_id')
            .eq('game_id', game_id)
            .eq('kind', 'final')
            .limit(1)
            .execute()
        )
        if r.data:
            return int(r.data[0]['voting_round_id'])
    except Exception as e:
        print(f"❌ Error find_voting_round_id_final: {e}")
    return None


def create_voting_round_row(
    game_id: int,
    voting_round_index: int,
    kind: str,
    fixture_set_key: Optional[str],
    target_image_url: Optional[str],
) -> Optional[int]:
    """
    voting_round_index: stable content id — fixture file index 1–9 for hardcoded rounds,
    or TOTAL_VOTING_ROUNDS (10) for kind=final. Not the per-player display order.
    """
    if not is_configured() or not game_id:
        return None
    try:
        result = supabase.table('voting_rounds').insert({
            'game_id': game_id,
            'voting_round_index': voting_round_index,
            'kind': kind,
            'fixture_set_key': fixture_set_key,
            'target_image_url': target_image_url,
            'started_at': datetime.utcnow().isoformat(),
        }).execute()
        if result.data:
            rid = result.data[0]['voting_round_id']
            print(f"✅ voting_rounds row voting_round_id={rid} index={voting_round_index}")
            return rid
    except Exception as e:
        print(f"❌ Error creating voting_round: {e}")
    return None


def end_voting_round_row(voting_round_id: int) -> None:
    if not is_configured() or not voting_round_id:
        return
    try:
        supabase.table('voting_rounds').update({
            'ended_at': datetime.utcnow().isoformat(),
        }).eq('voting_round_id', voting_round_id).execute()
    except Exception as e:
        print(f"❌ Error ending voting_round: {e}")


def create_ballot_with_options(
    game_id: int,
    voting_round_id: int,
    voter_player_id: str,
    options: List[Dict[str, Any]],
) -> Optional[int]:
    """
    options: three dicts with keys slot_index (1-3), source ('fixture'|'player_submission'|'round10_synthetic'),
    fixture_image_id (optional), image_url, owner_player_id (optional), prompt_id (optional),
    heuristic_snapshot (optional dict). For allocation fixture rounds 1–9, heuristic_snapshot may
    include _allocation_heuristic_source_fixture_id (canonical id for the text box; image id is fixture_image_id).
    """
    if not is_configured() or not game_id or not voting_round_id:
        return None
    try:
        br = supabase.table('voter_ballots').insert({
            'game_id': game_id,
            'voting_round_id': voting_round_id,
            'voter_player_id': voter_player_id,
        }).execute()
        if not br.data:
            return None
        ballot_id = br.data[0]['ballot_id']
        for opt in options:
            row = {
                'ballot_id': ballot_id,
                'slot_index': opt['slot_index'],
                'source': opt['source'],
                'image_url': opt['image_url'],
            }
            if opt.get('fixture_image_id') is not None:
                row['fixture_image_id'] = opt['fixture_image_id']
            if opt.get('owner_player_id') is not None:
                row['owner_player_id'] = opt['owner_player_id']
            if opt.get('prompt_id') is not None:
                row['prompt_id'] = opt['prompt_id']
            if opt.get('heuristic_snapshot') is not None:
                row['heuristic_snapshot'] = opt['heuristic_snapshot']
            supabase.table('ballot_options').insert(row).execute()
        print(f"✅ ballot_id={ballot_id} voter={voter_player_id[:8]}...")
        return ballot_id
    except Exception as e:
        print(f"❌ Error creating ballot/options: {e}")
    return None


def save_point_allocation(
    ballot_id: int,
    game_id: int,
    voting_round_id: int,
    voter_player_id: str,
    points_slot_1: int,
    points_slot_2: int,
    points_slot_3: int,
    *,
    seconds_since_session_start: Optional[float] = None,
    seconds_since_round_start: Optional[float] = None,
) -> bool:
    if not is_configured() or not ballot_id:
        return False
    if points_slot_1 + points_slot_2 + points_slot_3 != 10:
        return False
    row: Dict[str, Any] = {
        'ballot_id': ballot_id,
        'game_id': game_id,
        'voting_round_id': voting_round_id,
        'voter_player_id': voter_player_id,
        'points_slot_1': points_slot_1,
        'points_slot_2': points_slot_2,
        'points_slot_3': points_slot_3,
        'submitted_at': datetime.utcnow().isoformat(),
    }
    if seconds_since_session_start is not None:
        row['seconds_since_session_start'] = float(seconds_since_session_start)
    if seconds_since_round_start is not None:
        row['seconds_since_round_start'] = float(seconds_since_round_start)
    try:
        supabase.table('point_allocations').insert(row).execute()
        print(f"✅ point_allocation ballot={ballot_id} voter={voter_player_id[:8]}... {points_slot_1}/{points_slot_2}/{points_slot_3}")
        return True
    except Exception as e:
        print(f"❌ Error saving point_allocation: {e}")
        had_timing = 'seconds_since_session_start' in row or 'seconds_since_round_start' in row
        err = str(e).lower()
        if had_timing and any(s in err for s in ('column', 'schema', 'unknown', 'could not find', 'pgrst')):
            try:
                row.pop('seconds_since_session_start', None)
                row.pop('seconds_since_round_start', None)
                supabase.table('point_allocations').insert(row).execute()
                print(f"✅ point_allocation (no timing columns) ballot={ballot_id} voter={voter_player_id[:8]}...")
                return True
            except Exception as e2:
                print(f"❌ Error saving point_allocation (retry): {e2}")
    return False


def upload_image_async(image_data: str, game_id: int, player_id: str, round_id: int, 
                       prompt_id: int, prompt_index: int, player_name: str = None, 
                       round_number: int = None, callback=None):
    """
    Upload an image to Supabase Storage asynchronously (in background thread).
    Updates the database with the image URL once uploaded.
    
    Args:
        image_data: Base64 image data (data URI format: "data:image/png;base64,...")
        game_id: Game ID
        player_id: Player ID (session_id)
        round_id: Round ID
        prompt_id: Prompt ID (to update database after upload)
        prompt_index: Prompt index (for file path, 1-based)
        player_name: Player name (for readable folder structure, optional - will query if not provided)
        round_number: Round number 1, 2, or 3 (for readable folder structure, optional - will query if not provided)
        callback: Optional callback function(image_url, prompt_id) called after successful upload
    """
    def upload_thread():
        try:
            # Extract base64 data
            if image_data.startswith('data:image'):
                # Remove data URI prefix
                base64_data = image_data.split(',')[1]
            else:
                base64_data = image_data
            
            # Decode base64 to bytes
            image_bytes = base64.b64decode(base64_data)
            
            # Get player_name and round_number if not provided
            resolved_player_name = player_name
            resolved_round_number = round_number
            if not resolved_player_name:
                resolved_player_name = get_player_name(player_id)
            if not resolved_round_number:
                resolved_round_number = get_round_number(round_id)
            
            # Fallback to old structure if we can't get names
            if resolved_player_name and resolved_round_number:
                # New readable folder structure: game_{game_id}/{player_name}_{player_id_short}/round_{round_number}/prompt_{prompt_index}.png
                player_id_short = player_id[:8]  # First 8 characters for uniqueness
                sanitized_name = sanitize_folder_name(resolved_player_name)
                file_path = f"game_{game_id}/{sanitized_name}_{player_id_short}/round_{resolved_round_number}/prompt_{prompt_index}.png"
            else:
                # Fallback to old structure if we can't get player_name or round_number
                print(f"⚠️  Warning: Could not get player_name or round_number, using old folder structure")
                file_path = f"{game_id}/{player_id}/{round_id}/{prompt_id}.png"
            
            # Upload to Supabase Storage with retry logic
            max_retries = 3
            retry_delay = 1  # Start with 1 second
            image_url = None
            
            for attempt in range(max_retries):
                try:
                    image_url = upload_image_to_storage(image_bytes, file_path)
                    if image_url:
                        break  # Success!
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"⚠️  Upload attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        print(f"❌ All {max_retries} upload attempts failed for {file_path}: {e}")
            
            # Update database with image URL
            if image_url and prompt_id:
                update_prompt_image_url(prompt_id, image_url)
                
                # Call callback if provided (for memory optimization - clear base64 data)
                if callback:
                    try:
                        callback(image_url, prompt_id)
                    except Exception as e:
                        print(f"⚠️  Error in upload callback: {e}")
            elif not image_url:
                # Upload failed - log warning that base64 will be kept as fallback
                print(f"⚠️  Upload failed for prompt_id {prompt_id} (file_path: {file_path}). Base64 data will be kept as fallback.")
        except Exception as e:
            print(f"❌ Error in async image upload: {e}")
            import traceback
            traceback.print_exc()
    
    # Start upload in background thread
    thread = threading.Thread(target=upload_thread, daemon=True)
    thread.start()


def get_game_id(player_id: str) -> Optional[int]:
    """Get game_id for a player from cache or database."""
    if player_id in _game_id_cache:
        return _game_id_cache[player_id]
    
    if not is_configured():
        return None
    
    try:
        result = supabase.table('players').select('game_id').eq('player_id', player_id).execute()
        if result.data:
            game_id = result.data[0]['game_id']
            _game_id_cache[player_id] = game_id
            return game_id
    except Exception as e:
        print(f"❌ Error getting game_id: {e}")
    return None


def get_round_id(game_id: int, round_number: int) -> Optional[int]:
    """Get round_id from cache or database."""
    cache_key = (game_id, round_number)
    if cache_key in _round_id_cache:
        return _round_id_cache[cache_key]
    
    if not is_configured() or not game_id:
        return None
    
    try:
        result = supabase.table('rounds').select('round_id').eq('game_id', game_id).eq('round_number', round_number).execute()
        if result.data:
            round_id = result.data[0]['round_id']
            _round_id_cache[cache_key] = round_id
            return round_id
    except Exception as e:
        print(f"❌ Error getting round_id: {e}")
    return None

def get_round_number(round_id: int) -> Optional[int]:
    """Get round_number from round_id."""
    if not is_configured() or not round_id:
        return None
    
    try:
        result = supabase.table('rounds').select('round_number').eq('round_id', round_id).execute()
        if result.data:
            return result.data[0]['round_number']
    except Exception as e:
        print(f"❌ Error getting round_number: {e}")
    return None

def get_player_name(player_id: str) -> Optional[str]:
    """Get player_name from player_id."""
    if not is_configured() or not player_id:
        return None
    
    try:
        result = supabase.table('players').select('player_name').eq('player_id', player_id).execute()
        if result.data:
            return result.data[0]['player_name']
    except Exception as e:
        print(f"❌ Error getting player_name: {e}")
    return None

def get_player_by_name_and_game(player_name: str, game_id: int) -> Optional[Dict]:
    """
    Look up a player by name and game_id to restore their data after reconnection.
    Uses case-insensitive matching for player_name.
    Returns player data (player_id, team, character) if found, None otherwise.
    """
    if not is_configured() or not game_id or not player_name:
        return None
    
    try:
        # Get all players for this game and match case-insensitively
        result = supabase.table('players').select('player_id, player_name, condition, character').eq('game_id', game_id).execute()
        if result.data:
            # Case-insensitive match
            player_name_lower = player_name.lower().strip()
            for player in result.data:
                if player.get('player_name', '').lower().strip() == player_name_lower:
                    return player
    except Exception as e:
        print(f"❌ Error looking up player by name: {e}")
    return None

def sanitize_folder_name(name: str) -> str:
    """
    Sanitize a name for use in folder paths.
    Removes/replaces special characters that might cause issues in file systems.
    """
    # Replace spaces with underscores
    name = name.replace(' ', '_')
    # Remove special characters, keep only alphanumeric, underscore, and hyphen
    import re
    name = re.sub(r'[^a-zA-Z0-9_-]', '', name)
    # Limit length to avoid path issues
    if len(name) > 50:
        name = name[:50]
    return name

