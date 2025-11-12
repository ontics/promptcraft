"""
Database helper module for PromptCraft analytics.
Handles Supabase database and storage operations.
"""
import os
import base64
import threading
from datetime import datetime
from supabase import create_client, Client
from typing import Optional, Dict
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
    """Mark a game as ended in the database."""
    if not is_configured() or not game_id:
        return
    
    try:
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
    """Mark a round as ended in the database."""
    if not is_configured() or not round_id:
        return
    
    try:
        supabase.table('rounds').update({
            'ended_at': datetime.utcnow().isoformat()
        }).eq('round_id', round_id).execute()
        print(f"✅ Ended round: round_id={round_id}")
    except Exception as e:
        print(f"❌ Error ending round: {e}")


def create_player(game_id: int, player_id: str, player_name: str, team: Optional[str] = None, character: Optional[str] = None):
    """Create or update a player in the database."""
    if not is_configured() or not game_id:
        return
    
    try:
        # Check if player already exists
        existing = supabase.table('players').select('player_id').eq('player_id', player_id).execute()
        
        if existing.data:
            # Update existing player
            supabase.table('players').update({
                'game_id': game_id,
                'player_name': player_name,
                'team': team,
                'character': character
            }).eq('player_id', player_id).execute()
        else:
            # Create new player
            supabase.table('players').insert({
                'player_id': player_id,
                'game_id': game_id,
                'player_name': player_name,
                'team': team,
                'character': character,
                'joined_at': datetime.utcnow().isoformat()
            }).execute()
        
        _game_id_cache[player_id] = game_id
        print(f"✅ Created/updated player: {player_id} ({player_name})")
    except Exception as e:
        print(f"❌ Error creating player: {e}")


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
        print(f"✅ Uploaded image to Storage: {file_path}")
        return url
    except Exception as e:
        print(f"❌ Error uploading image to Storage: {e}")
        return None


def save_prompt_sync(game_id: int, round_id: int, player_id: str, prompt_index: int, 
                     prompt_text: str, image_url: Optional[str], ai_response: Optional[str],
                     submitted_at: Optional[datetime] = None,
                     image_generated_at: Optional[datetime] = None,
                     error_type: Optional[str] = None,
                     error_message: Optional[str] = None,
                     finish_reason: Optional[str] = None,
                     file_size_kb: Optional[float] = None,
                     safety_ratings: Optional[dict] = None) -> Optional[int]:
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


def save_image_selection(player_id: str, round_id: int, game_id: int, prompt_id: int):
    """Save a player's image selection."""
    if not is_configured() or not game_id or not round_id:
        return
    
    try:
        supabase.table('image_selections').insert({
            'player_id': player_id,
            'round_id': round_id,
            'game_id': game_id,
            'prompt_id': prompt_id,
            'selected_at': datetime.utcnow().isoformat()
        }).execute()
        print(f"✅ Saved image selection: player={player_id}, prompt_id={prompt_id}")
    except Exception as e:
        print(f"❌ Error saving image selection: {e}")


def save_vote(voter_id: str, voted_for_player_id: str, voted_for_prompt_id: int, 
              round_id: int, game_id: int):
    """Save a vote."""
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


def upload_image_async(image_data: str, game_id: int, player_id: str, round_id: int, 
                       prompt_id: int, prompt_index: int, player_name: str = None, 
                       round_number: int = None):
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
            
            # Upload to Supabase Storage
            image_url = upload_image_to_storage(image_bytes, file_path)
            
            # Update database with image URL
            if image_url and prompt_id:
                update_prompt_image_url(prompt_id, image_url)
        except Exception as e:
            print(f"❌ Error in async image upload: {e}")
    
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

