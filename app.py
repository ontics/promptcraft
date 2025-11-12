from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import google.generativeai as genai
import google.genai as google_genai
import os
import random
import time
import base64
from datetime import datetime
from dotenv import load_dotenv
import io
from PIL import Image

# Load environment variables BEFORE importing db
load_dotenv()

import db  # Database helper module

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
# Use threading instead of eventlet for Python 3.12 compatibility
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Configure Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# Game state
game_state = {
    'status': 'lobby',  # lobby, playing, voting, round_results, game_over
    'current_round': 0,
    'round_start_time': None,
    'round_end_time': None,
    'voting_start_time': None,
    'game_id': None,  # Database game_id
    'round_id': None,  # Current round's database round_id
    'target_images': [
        {'id': 1, 'url': '/static/images/target1.jpg'},
        {'id': 2, 'url': '/static/images/target2.jpg'},
        {'id': 3, 'url': '/static/images/target3.jpg'}
    ],
    'current_target': None
}

players = {}  # session_id: player_data
player_sessions = {}  # socket_id: session_id
admin_session_id = None  # Track the admin player

# Character messages
# Bud messages - shown progressively based on prompt count (1-indexed: prompt_count = 1 shows message[0])
BUDDY_MESSAGES = [
    "Got it! Let's see what your idea looks like.",
    "Processing your imagination... hold tight.",
    "Alright, let's bring that vision to life.",
    "Prompt received. Let's see what you've created!",
    "Interesting choice. Let's see where this goes.",
    "Generating your image now.",
    "Okay, I'm sending that one through.",
    "Here we go. Time to see some pixels in action.",
    "I'm curious how this one turns out.",
    "Prompt locked in. Let's create!",
    "Got your idea! Spinning it into an image now.",
    "Let's visualize that thought.",
    "Your prompt is in!",
    "Alright, let's see what comes out.",
    "Message received. Turning your words into art."
]

# Bud error message
BUDDY_ERROR_MESSAGE = "That prompt didn't go through. Please try a new prompt."

# Spud messages - shown progressively based on prompt count (1-indexed: prompt_count = 1 shows message[0])
SPUDDY_MESSAGES = [
    "The cooling water for your prompt could keep a small houseplant alive for a day. Poor fern never stood a chance.",
    "Your carbon footprint compounds every time you prompt. I'm starting to feel the heat!",
    "You're up to 1.2 kWh and 130 grams of CO2. That's like driving half a mile!",
    "By now, you've used enough power to toast a slice of bread.",
    "The cooling water for this image could've filled a glass or two. Drink responsibly, prompt responsibly.",
    "That's a full bottle of fresh water consumed. I was gonna drink that!",
    "That image? About as much carbon as sending an email with a big attachment.",
    "Humans need 8 glasses of water a day. Your images have just used them up. Feeling thirsty?",
    "You've used more energy this round than charging your phone 8 times over!",
    "390 grams of CO2 added to the atmosphere. My leaves are drying up…",
    "That's 3.6 kWh WASTED! That's keeping the house lights on for 3 days. Gone in minutes for… this?",
    "You've used enough power to run a microwave for 5 minutes. It's getting toasty in here!",
    "Thirteen images. Data centers consume 1% of global electricity. And you just added to it…",
    "Did you know 20,000 trees have been burned to clear land for new data center construction?",
    "You would need 12 earths to sustain your current levels of natural resource consumption!"
]

# Spud error message
SPUDDY_ERROR_MESSAGE = "That prompt didn't go through. You could try again... or call it an accidental act of sustainability?"

def generate_session_id():
    return os.urandom(16).hex()

def assign_team():
    # Random assignment to Team A or Team B
    return random.choice(['A', 'B'])

def get_character(team):
    return 'Buddy' if team == 'A' else 'Spuddy'

def get_character_for_round(player, current_round):
    """
    Determine which character a player sees based on round number.
    Round 1: All players see Bud (control)
    Rounds 2-3: Team A sees Bud, Team B sees Spud (treatment)
    """
    if current_round == 1:
        return 'Bud'
    else:  # Rounds 2 and 3
        if player.get('team') == 'A':
            return 'Bud'
        else:  # Team B (treatment)
            return 'Spud'

def get_spud_plant_state(prompt_count, has_successful_prompt=False):
    """
    Determine plant state based on prompt count and whether any prompt was successful.
    
    Rules:
    - 0 prompts: base
    - First prompt error: base (no progression)
    - First prompt success: yellow (immediate progression after first success)
    - Prompt 4+ (with at least one success): dry
    """
    # If no successful prompts yet, stay in base state
    if not has_successful_prompt:
        return 'base'
    
    # After first successful prompt, plant becomes yellow
    # From prompt 4 (with success), plant becomes dry
    if prompt_count >= 4:
        return 'dry'
    elif prompt_count >= 1:
        return 'yellow'
    else:
        return 'base'

def get_spud_animation_state(prompt_count, plant_state=None, is_error=False, has_successful_prompt=False):
    """
    Determine Spud animation state (static pose) based on prompt count, plant state, and error status.
    
    Rules:
    - 0 prompts: smiling (base) - static pose
    - First prompt error: smiling (base) - static pose, will animate to talking when message appears
    - First prompt success: sad (yellow) - static pose, will animate to sad_talking when message appears
    - Prompt 4+ (with success): sad (dry) - static pose, will animate to sad_talking when message appears
    - Prompt 7+ (with success): welling (dry) - static pose, will animate to crying when message appears
    
    Returns the static pose. Animation (talking/crying) is handled in frontend when message appears.
    """
    # If plant_state not provided, determine it first
    if plant_state is None:
        plant_state = get_spud_plant_state(prompt_count, has_successful_prompt)
    
    # 0 prompts: always smiling (base)
    if prompt_count == 0:
        return 'smiling'
    
    # Base plant state (no successful prompts yet - only errors)
    if plant_state == 'base':
        # If error, stay in base smiling (will animate to talking when message appears)
        return 'smiling'
    
    # Yellow plant state (prompt 1-3 with at least one success)
    elif plant_state == 'yellow':
        # Static pose is sad (will animate to sad_talking when message appears)
        return 'sad'
    
    # Dry plant state (prompt 4+ with at least one success)
    elif plant_state == 'dry':
        if prompt_count >= 7:
            # Prompt 7+: static pose is welling (will animate to crying when message appears)
            return 'welling'
        else:
            # Prompt 4-6: static pose is sad (will animate to sad_talking when message appears)
            return 'sad'
    
    # Default fallback
    return 'smiling'

def get_bud_animation_state():
    """
    Determine Bud animation state (static pose).
    Bud's static pose is always smiling.
    When a message appears, will animate between smiling, talking, and sad_talking.
    """
    return 'smiling'

@app.route('/')
def index():
    if 'session_id' not in session:
        session['session_id'] = generate_session_id()
    return render_template('index.html')

@app.route('/analytics/errors')
def analytics_errors():
    """View image generation error analytics"""
    all_errors = []
    for session_id, player in players.items():
        for error in player.get('image_generation_errors', []):
            error_with_player = error.copy()
            error_with_player['player_name'] = player['name']
            error_with_player['session_id'] = session_id
            all_errors.append(error_with_player)
    
    # Group by round
    errors_by_round = {1: [], 2: [], 3: []}
    for error in all_errors:
        round_num = error['round']
        errors_by_round[round_num].append(error)
    
    # Summary
    summary = {
        'total_errors': len(all_errors),
        'errors_by_round': {
            round_num: len(errors) for round_num, errors in errors_by_round.items()
        },
        'errors_by_type': {}
    }
    
    for error in all_errors:
        error_type = error['error_type']
        summary['errors_by_type'][error_type] = summary['errors_by_type'].get(error_type, 0) + 1
    
    return {
        'summary': summary,
        'all_errors': all_errors,
        'errors_by_round': errors_by_round
    }

@socketio.on('connect')
def handle_connect():
    session_id = session.get('session_id')
    if not session_id:
        session_id = generate_session_id()
        session['session_id'] = session_id

    player_sessions[request.sid] = session_id
    print(f"Client connected: {request.sid} (session: {session_id})")

@socketio.on('disconnect')
def handle_disconnect():
    session_id = player_sessions.get(request.sid)
    if session_id and session_id in players:
        player = players[session_id]
        # Clear socket_id to mark player as disconnected
        old_socket_id = player.get('socket_id')
        player['socket_id'] = None
        
        # Only broadcast if this was the active socket connection
        if old_socket_id == request.sid:
            emit('player_left', {'player_name': player.get('display_name', player['name']), 'session_id': session_id}, broadcast=True)
            # Update admin view with connection status
            if admin_session_id in players and players[admin_session_id].get('socket_id'):
                emit('player_status_update', {
                    'players': [{
                        'name': p.get('display_name', p['name']),
                        'team': p['team'],
                        'is_admin': p['is_admin'],
                        'is_connected': p.get('socket_id') is not None,
                        'session_id': p['session_id']
                    } for p in players.values()]
                }, room=players[admin_session_id]['socket_id'])
            print(f"Player {player['name']} disconnected")

    if request.sid in player_sessions:
        del player_sessions[request.sid]

@socketio.on('join_game')
def handle_join_game(data):
    global admin_session_id
    
    session_id = session.get('session_id')
    player_name = data.get('name', f'Player{len(players) + 1}').strip()
    
    # Check if player name matches admin code
    required_admin_code = os.getenv('ADMIN_CODE', '').strip()
    is_admin_code = required_admin_code and (player_name == required_admin_code)
    
    # Display name for admin (obscure the code)
    display_name = 'Gamemaster' if is_admin_code else player_name

    # Check if player already exists (reconnection)
    if session_id in players:
        player = players[session_id]
        player['socket_id'] = request.sid  # Update socket_id on reconnection
        
        # If reconnecting with admin code and no admin exists, become admin
        if is_admin_code and admin_session_id is None and required_admin_code:
            admin_session_id = session_id
            player['is_admin'] = True
            player['name'] = player_name  # Store actual name (code)
            player['display_name'] = 'Gamemaster'  # Always show as Gamemaster
            print(f"Player {player_name} reconnected as ADMIN (code verified)")
        elif is_admin_code and player['is_admin'] and session_id == admin_session_id:
            # Admin reconnecting with admin code - ensure display_name is correct
            player['name'] = player_name  # Update internal name (code)
            player['display_name'] = 'Gamemaster'  # Always show as Gamemaster
        else:
            # Update name (but preserve display_name if admin)
            if player['is_admin']:
                # Already admin - keep display_name as Gamemaster
                player['name'] = player_name  # Update internal name if changed
                player['display_name'] = 'Gamemaster'  # Always show as Gamemaster
            else:
                player['name'] = player_name
                player['display_name'] = player_name
        
        # Send reconnection update to admin
        if admin_session_id in players and players[admin_session_id].get('socket_id'):
            emit('player_status_update', {
                'players': [{
                    'name': p.get('display_name', p['name']),
                    'team': p['team'],
                    'is_admin': p['is_admin'],
                    'is_connected': p.get('socket_id') is not None,
                    'session_id': p['session_id']
                } for p in players.values()]
            }, room=players[admin_session_id]['socket_id'])
        
        # If game is in progress, restore player's game state
        if game_state['status'] != 'lobby':
            if player['is_admin']:
                # Admin reconnection - send admin view
                if game_state['status'] == 'playing':
                    emit('admin_game_started', {
                        'round': game_state['current_round'],
                        'target': game_state['current_target'],
                        'players': [{
                            'name': p.get('display_name', p['name']),
                            'team': p['team'],
                            'is_connected': p.get('socket_id') is not None,
                            'session_id': p['session_id'],
                            'prompts_submitted': len(p['images'].get(game_state['current_round'], []))
                        } for p in players.values() if not p['is_admin']]
                    }, room=player['socket_id'])
                elif game_state['status'] in ['voting', 'voting_images', 'round_results']:
                    # Send current admin status
                    handle_admin_get_status()
            else:
                # Regular player reconnection - restore their game state
                current_round = game_state['current_round']
                if game_state['status'] == 'playing':
                    # Determine character for this round
                    character = get_character_for_round(player, current_round)
                    character_data = {
                        'character': character,
                        'round': current_round
                    }
                    if character == 'Bud':
                        character_data['animation_state'] = get_bud_animation_state()
                    elif character == 'Spud':
                        prompt_count = player.get('prompt_count', 0)
                        has_successful_prompt = player.get('has_successful_prompt', {}).get(current_round, False)
                        plant_state = get_spud_plant_state(prompt_count, has_successful_prompt)
                        character_data['plant_state'] = plant_state
                        character_data['animation_state'] = get_spud_animation_state(prompt_count, plant_state, is_error=False, has_successful_prompt=has_successful_prompt)
                        character_data['prompt_count'] = prompt_count
                    
                    emit('game_started', {
                        'round': current_round,
                        'target': game_state['current_target'],
                        'end_time': game_state['round_end_time'],
                        'character': character_data
                    }, room=player['socket_id'])
                    # Restore their generated images
                    if player['images'].get(current_round):
                        for img_data in player['images'][current_round]:
                            emit('image_generated', {
                                'image_data': img_data.get('image_data', ''),
                                'ai_response': img_data.get('ai_response', ''),
                                'prompt': img_data.get('prompt', ''),
                                'image_index': player['images'][current_round].index(img_data),
                                'prompt_id': img_data.get('prompt_id'),
                                'error_type': img_data.get('error_type'),  # Include error info for filtering
                                'file_size_kb': img_data.get('file_size_kb')
                            }, room=player['socket_id'])
                elif game_state['status'] == 'voting':
                    # Include synchronized start time for timer synchronization
                    selection_start_time = game_state.get('voting_start_time', time.time())
                    emit('voting_started', {
                        'round': current_round,
                        'duration': game_state.get('voting_duration', 30),
                        'start_time': selection_start_time,  # Synchronized start time
                        'default_selected': current_round in player['selected_images']
                    }, room=player['socket_id'])
                elif game_state['status'] == 'voting_images':
                    # Send voting screen
                    selected_images = []
                    for s_id, p in players.items():
                        if not p['is_admin'] and current_round in p['selected_images']:
                            selected_image = p['selected_images'][current_round]
                            selected_images.append({
                                'session_id': s_id,
                                'player_name': p.get('display_name', p['name']),
                                'image': selected_image,
                                'prompt_id': selected_image.get('prompt_id')
                            })
                    target_image = game_state.get('current_target', {})
                    emit('vote_on_images', {
                        'images': selected_images,
                        'round': current_round,
                        'my_session_id': session_id,
                        'target_image': {'url': target_image.get('url', '')}
                    }, room=player['socket_id'])
                elif game_state['status'] == 'round_results':
                    # Show round results
                    show_round_results()
                elif game_state['status'] == 'game_over':
                    # Show game over
                    end_game()
        
        # Update player_sessions mapping
        player_sessions[request.sid] = session_id
        
        # Send lobby update if in lobby, otherwise skip (already sent game state above)
        if game_state['status'] == 'lobby':
            if player['is_admin']:
                emit('admin_joined', {
                    'is_admin': True,
                    'players': [{
                        'name': p['name'],
                        'team': p['team'],
                        'is_admin': p['is_admin'],
                        'is_connected': p.get('socket_id') is not None,
                        'session_id': p['session_id']
                    } for p in players.values()]
                }, room=player['socket_id'])
            else:
                lobby_players = [{'name': p.get('display_name', p['name']), 'team': p['team'], 'is_admin': p['is_admin'], 'is_connected': p.get('socket_id') is not None} for p in players.values()]
                emit('game_joined', {
                    'player': {
                        'name': player.get('display_name', player['name']),
                        'team': player['team'],
                        'character': player['character'],
                        'score': player['score'],
                        'is_admin': player['is_admin']
                    },
                    'game_state': {
                        'status': game_state['status'],
                        'current_round': game_state['current_round'],
                        'current_target': game_state['current_target'],
                        'players_count': len([p for p in players.values() if not p['is_admin']])
                    },
                    'lobby_players': lobby_players
                }, room=player['socket_id'])
            emit('lobby_players_update', {'players': lobby_players}, broadcast=True)
        
        print(f"Player {player.get('display_name', player_name)} reconnected (Admin: {player['is_admin']})")
        return
    else:
        # New player - check if they're using admin code as name
        is_new_admin = False
        final_display_name = display_name  # Default to calculated display_name
        
        if is_admin_code and admin_session_id is None and required_admin_code:
            # First admin joining with correct code
            admin_session_id = session_id
            is_new_admin = True
            final_display_name = 'Gamemaster'  # Always show as Gamemaster
            print(f"Player {player_name} joined as ADMIN (code verified)")
        elif is_admin_code and admin_session_id is not None:
            # Admin code used but admin already exists
            emit('error', {'message': 'Admin already exists. Please use a different name.'})
            return
        elif admin_session_id is None and not required_admin_code:
            # Fallback: first player becomes admin if no code configured
            admin_session_id = session_id
            is_new_admin = True
            final_display_name = 'Gamemaster'  # Show as Gamemaster even in fallback
            print(f"Player {player_name} joined as ADMIN (first player, no code configured)")
        
        # New players don't get a team until admin assigns teams
        team = None
        character = None

        player = {
            'session_id': session_id,
            'socket_id': request.sid,
            'name': player_name,  # Internal name (may be admin code)
            'display_name': final_display_name,  # Display name (Gamemaster for admin)
            'team': team,
            'character': character,
            'score': 0,
            'round_scores': [0, 0, 0],
            'images': {1: [], 2: [], 3: []},  # Round number -> list of generated images
            'selected_images': {},  # Round number -> selected image
            'has_confirmed_selection': {1: False, 2: False, 3: False},  # Track if player has confirmed their selection (not just default)
            'votes_received': {1: 0, 2: 0, 3: 0},
            'has_voted': {1: False, 2: False, 3: False},
            'prompt_count': 0,
            'has_successful_prompt': {1: False, 2: False, 3: False},  # Track if player has had at least one successful prompt per round
            'conversation_history': {1: [], 2: [], 3: []},  # Round number -> conversation
            'current_image': {1: None, 2: None, 3: None},  # Current image for refinement per round
            'image_generation_errors': [],  # Track failed image generations
            'is_admin': is_new_admin
        }
        players[session_id] = player

    player_sessions[request.sid] = session_id

    # Send updated lobby players to all clients (only if in lobby)
    if game_state['status'] == 'lobby':
        # Use display_name for lobby (obscures admin code)
        lobby_players = [{'name': p.get('display_name', p['name']), 'team': p['team'], 'is_admin': p['is_admin'], 'is_connected': p.get('socket_id') is not None} for p in players.values()]
        
        # Send game state to player
        # Admin gets different view - they don't play
        if player['is_admin']:
            emit('admin_joined', {
                'is_admin': True,
                'players': [{
                    'name': p.get('display_name', p['name']),  # Use display_name
                    'team': p['team'],
                    'is_admin': p['is_admin'],
                    'is_connected': p.get('socket_id') is not None,
                    'session_id': p['session_id']
                } for p in players.values()]
            }, room=player['socket_id'])
        else:
            emit('game_joined', {
                'player': {
                    'name': player.get('display_name', player['name']),  # Use display_name
                    'team': player['team'],
                    'character': player['character'],
                    'score': player['score'],
                    'is_admin': player['is_admin']
                },
                'game_state': {
                    'status': game_state['status'],
                    'current_round': game_state['current_round'],
                    'current_target': game_state['current_target'],
                    'players_count': len([p for p in players.values() if not p['is_admin']])
                },
                'lobby_players': lobby_players
            }, room=player['socket_id'])

        # Broadcast player list update to all
        emit('lobby_players_update', {'players': lobby_players}, broadcast=True)

        # Also push an admin-specific player status update so the dashboard stays in sync
        if admin_session_id in players and players[admin_session_id].get('socket_id'):
            emit('player_status_update', {
                'players': [{
                    'name': p.get('display_name', p['name']),
                    'team': p['team'],
                    'is_admin': p['is_admin'],
                    'is_connected': p.get('socket_id') is not None,
                    'session_id': p['session_id'],
                    'prompts_submitted': len(p['images'].get(game_state.get('current_round', 0), [])) if game_state.get('current_round') else 0,
                    'has_selected': (game_state.get('current_round') in p['selected_images']) if game_state.get('current_round') else False,
                    'has_voted': p['has_voted'].get(game_state.get('current_round', 0), False) if game_state.get('current_round') else False,
                } for p in players.values()]
            }, room=players[admin_session_id]['socket_id'])

    print(f"Player {player.get('display_name', player_name)} joined (Admin: {player['is_admin']})")

@socketio.on('assign_teams')
def handle_assign_teams():
    session_id = session.get('session_id')
    
    # Check if player is admin
    if session_id != admin_session_id:
        emit('error', {'message': 'Only admin can assign teams'})
        return
    
    # Get all non-admin players who are connected (have a socket_id)
    connected_players = [p for p in players.values() if not p['is_admin'] and p.get('socket_id') is not None]
    
    if len(connected_players) < 2:
        emit('error', {'message': 'Need at least 2 connected players (excluding admin) to assign teams'})
        return
    
    # Remove disconnected players from the lobby (they can rejoin later)
    disconnected_player_ids = []
    for session_id, player in list(players.items()):
        if not player['is_admin'] and player.get('socket_id') is None:
            disconnected_player_ids.append(session_id)
            # Remove from players dictionary
            del players[session_id]
            # Remove from player_sessions mapping if it exists
            socket_ids_to_remove = [sid for sid, sess_id in player_sessions.items() if sess_id == session_id]
            for sid in socket_ids_to_remove:
                if sid in player_sessions:
                    del player_sessions[sid]
    
    if disconnected_player_ids:
        print(f"[ASSIGN TEAMS] Removed {len(disconnected_player_ids)} disconnected player(s) from lobby")
    
    # Clear team assignments for all remaining players (should only be connected ones now)
    for player in players.values():
        if not player['is_admin']:
            player['team'] = None
            player['character'] = None
    
    # Shuffle connected players for random assignment
    random.shuffle(connected_players)
    
    # Balance teams: split evenly, with extra players going to Team A if odd
    mid_point = len(connected_players) // 2
    team_a_players = connected_players[:mid_point]
    team_b_players = connected_players[mid_point:]
    
    # Assign teams only to connected players
    for player in team_a_players:
        player['team'] = 'A'
        player['character'] = get_character('A')
    
    for player in team_b_players:
        player['team'] = 'B'
        player['character'] = get_character('B')
    
    # Update players in database if game has started
    if game_state.get('game_id') and db.is_configured():
        # Update all players (including disconnected ones - they keep their team assignment if they had one)
        for player in players.values():
            if not player['is_admin']:
                db.create_player(
                    game_id=game_state['game_id'],
                    player_id=player['session_id'],
                    player_name=player['name'],
                    team=player['team'],
                    character=player['character']
                )
    
    # Broadcast updated lobby players
    lobby_players = [{'name': p.get('display_name', p['name']), 'team': p['team'], 'is_admin': p['is_admin'], 'socket_id': p.get('socket_id') is not None} for p in players.values()]
    emit('lobby_players_update', {'players': lobby_players}, broadcast=True)
    
    # Update admin dashboard to show new team assignments
    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        # Send player status update (works in lobby and during game)
        emit('player_status_update', {
            'players': [{
                'name': p.get('display_name', p['name']),
                'team': p['team'],
                'is_admin': p['is_admin'],
                'is_connected': p.get('socket_id') is not None,
                'session_id': p['session_id']
            } for p in players.values()]
        }, room=players[admin_session_id]['socket_id'])
        
        # Also update admin status if game is in progress
        if game_state['status'] != 'lobby':
            handle_admin_get_status()
    
    print(f"Teams assigned by admin: Team A ({len(team_a_players)}), Team B ({len(team_b_players)})")

@socketio.on('start_game')
def handle_start_game():
    session_id = session.get('session_id')
    
    # Check if player is admin
    if session_id != admin_session_id:
        emit('error', {'message': 'Only admin can start the game'})
        return
    
    # Get non-admin players only
    non_admin_players = [p for p in players.values() if not p['is_admin']]
    
    if game_state['status'] == 'lobby' and len(non_admin_players) >= 1:
        # Make sure teams are assigned
        players_without_teams = [p for p in non_admin_players if p['team'] is None]
        if players_without_teams:
            emit('error', {'message': 'Please assign teams first'})
            return
        
        # Create game session in database
        if db.is_configured():
            game_id = db.create_game(total_players=len(players))
            if game_id:
                game_state['game_id'] = game_id
                # Create/update all players in database
                for player in players.values():
                    db.create_player(
                        game_id=game_id,
                        player_id=player['session_id'],
                        player_name=player['name'],
                        team=player['team'],
                        character=player['character']
                    )
        
        game_state['status'] = 'playing'
        game_state['current_round'] = 1
        game_state['current_target'] = game_state['target_images'][0]
        game_state['round_start_time'] = time.time()
        game_state['round_end_time'] = game_state['round_start_time'] + 300  # 5 minutes

        # Create round in database
        if db.is_configured() and game_state.get('game_id'):
            round_id = db.create_round(
                game_id=game_state['game_id'],
                round_number=1
            )
            if round_id:
                game_state['round_id'] = round_id

        # Reset current images and prompt count for all players at start of round
        for p in players.values():
            if not p['is_admin']:
                p['current_image'][1] = None
                p['prompt_count'] = 0  # Reset prompt count for avatar state
                p['has_successful_prompt'][1] = False  # Reset successful prompt tracking
                print(f"[DEBUG] Reset current_image, prompt_count, and has_successful_prompt for player {p['name']}, round 1")

        # Send game started to players only (not admin)
        for p in players.values():
            if not p['is_admin']:
                # Determine character for this round
                character = get_character_for_round(p, 1)
                character_data = {
                    'character': character,
                    'round': 1
                }
                if character == 'Bud':
                    character_data['animation_state'] = get_bud_animation_state()
                elif character == 'Spud':
                    character_data['plant_state'] = 'base'
                    character_data['animation_state'] = 'smiling'
                    character_data['prompt_count'] = 0
                
                emit('game_started', {
                    'round': 1,
                    'target': game_state['current_target'],
                    'end_time': game_state['round_end_time'],
                    'character': character_data
                }, room=p['socket_id'])
        
        # Send admin game started event with player status
        if admin_session_id in players and players[admin_session_id].get('socket_id'):
            time_remaining = game_state['round_end_time'] - time.time() if game_state.get('round_end_time') else None
            emit('admin_game_started', {
                'round': 1,
                'target': game_state['current_target'],
                'time_remaining': time_remaining,
                'players': [{
                    'name': p.get('display_name', p['name']),
                    'team': p['team'],
                    'is_connected': p.get('socket_id') is not None,
                    'session_id': p['session_id'],
                    'prompts_submitted': len(p['images'].get(1, []))
                } for p in players.values() if not p['is_admin']]
            }, room=players[admin_session_id]['socket_id'])

        print("Game started!")

@socketio.on('send_prompt')
def handle_send_prompt(data):
    session_id = session.get('session_id')
    if session_id not in players:
        return

    player = players[session_id]
    
    # Admin cannot send prompts
    if player['is_admin']:
        emit('error', {'message': 'Admin cannot play - you are the gamemaster'})
        return
    
    prompt = data.get('prompt', '')
    current_round = game_state['current_round']

    if game_state['status'] != 'playing':
        emit('error', {'message': 'Game is not in playing state'})
        return

    # Allow prompts during buffer period (5 seconds after round_end_time)
    buffer_time = 5
    if time.time() > game_state['round_end_time'] + buffer_time:
        emit('error', {'message': 'Round has ended'})
        return

    player['prompt_count'] += 1

    # First, show the prompt bubble and loading state
    emit('prompt_sent', {
        'prompt': prompt
    })

    # Send character message and state updates
    # Note: At this point, we don't know if this prompt will be successful or error
    # So we use the current state (before this prompt's result is known)
    character = get_character_for_round(player, current_round)
    character_message = get_character_message(player, current_round)
    
    # Build character state data
    character_data = {
        'character': character,
        'message': character_message,
        'round': current_round
    }
    
    # Add character-specific state information
    prompt_count = player.get('prompt_count', 0)
    has_successful_prompt = player.get('has_successful_prompt', {}).get(current_round, False)
    
    if character == 'Bud':
        # Bud: static pose is always smiling, will animate when message appears
        character_data['animation_state'] = get_bud_animation_state()
    elif character == 'Spud':
        # Spud: determine plant state and animation state based on current status
        # At this point, we use previous state (before this prompt's result)
        # The state will be updated after we know if this prompt succeeded or failed
        prev_prompt_count = max(0, prompt_count - 1)  # Use previous count for initial state
        plant_state = get_spud_plant_state(prev_prompt_count, has_successful_prompt)
        character_data['plant_state'] = plant_state
        character_data['animation_state'] = get_spud_animation_state(prev_prompt_count, plant_state, is_error=False, has_successful_prompt=has_successful_prompt)
        character_data['prompt_count'] = prompt_count
    
    emit('character_message', character_data)

    # Generate image using Gemini
    try:
        # Get conversation history for tracking (NOT used in API call - just for logging)
        conversation = player['conversation_history'][current_round]
        
        # Use Gemini 2.5 Flash Image API
        client = google_genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
        
        # Check if we have a current image for this round (for refinement)
        current_image_obj = player['current_image'][current_round]
        
        print(f"[DEBUG] Player: {player['name']}, Session: {session_id[:8]}..., Round: {current_round}, Has current_image: {current_image_obj is not None}")
        
        # Construct contents array: include previous image if exists, otherwise just prompt
        # IMPORTANT: No target description or context is added - only the user's prompt is sent
        # Conversation history is NOT included in the API request - only the current prompt
        if current_image_obj:
            # We have a previous image - this is a refinement request
            # Convert PIL Image to base64 for API
            buffered = io.BytesIO()
            current_image_obj.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            # Create proper content structure for Gemini API
            contents = [
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": img_base64
                    }
                },
                prompt
            ]
            print(f"[API REQUEST] Refining image - Prompt sent to API: '{prompt}' (NO target context)")
        else:
            # First image generation - use prompt directly (NO target theme, NO target description)
            contents = [prompt]
            print(f"[API REQUEST] New image - Prompt sent to API: '{prompt}' (NO target context)")
        
        # Generate image using gemini-2.5-flash-image model
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=contents
            )
            
            # Extract error information from API response FIRST (before processing image)
            api_error_type, api_error_message, finish_reason, safety_ratings = extract_api_error_info(response)
            
            # Debug: Print response structure and error info
            print(f"[API RESPONSE] Response type: {type(response)}")
            if finish_reason:
                print(f"[API RESPONSE] finish_reason: {finish_reason}")
            if api_error_type:
                print(f"[API RESPONSE] Error detected: {api_error_type} - {api_error_message}")
            
            # Extract the image data from response
            image_data = None
            image_bytes = None
            file_size_kb = None
            ai_response = "Image generated successfully"
            error_type = api_error_type
            error_message = api_error_message
            
            if response.candidates and len(response.candidates) > 0:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data is not None:
                        # The data might already be base64 or might be bytes
                        img_data = part.inline_data.data
                        
                        # Decode to bytes for analysis
                        if isinstance(img_data, str):
                            image_bytes = base64.b64decode(img_data)
                            image_data = f"data:image/png;base64,{img_data}"
                        elif isinstance(img_data, bytes):
                            image_bytes = img_data
                            image_b64 = base64.b64encode(img_data).decode('utf-8')
                            image_data = f"data:image/png;base64,{image_b64}"
                        else:
                            print(f"Unexpected data type: {type(img_data)}")
                            continue
                        
                        # Calculate file size
                        if image_bytes:
                            file_size_kb = get_file_size_kb(image_bytes)
                            print(f"[IMAGE SIZE] File size: {file_size_kb:.2f} KB")
                            
                            # Check if image is suspiciously small (likely placeholder)
                            if is_small_image(file_size_kb, threshold_kb=50):
                                if not error_type:  # Don't override API error if already set
                                    error_type = 'small_image'
                                    error_message = f'Image is unusually small ({file_size_kb:.2f} KB), likely a placeholder or policy violation response'
                                print(f"[WARNING] Small image detected: {file_size_kb:.2f} KB")
                        
                        # Only store as current_image if it's valid (not an error)
                        if not error_type and not is_small_image(file_size_kb, threshold_kb=50):
                            player['current_image'][current_round] = Image.open(io.BytesIO(image_bytes))
                            # Mark that player has had at least one successful prompt this round
                            player['has_successful_prompt'][current_round] = True
                            print(f"[DEBUG] Stored new image for player {player['name']} (session: {session_id[:8]}...), round {current_round}, successful prompt")
                        else:
                            # Don't store error images for refinement
                            player['current_image'][current_round] = None
                            print(f"[DEBUG] Not storing image for refinement due to error: {error_type}")
                        
                        break
            
            # Handle cases where no image was returned
            if image_data is None:
                if not error_type:
                    error_type = 'no_image_in_response'
                    error_message = 'API returned success but no image data'
                print(f"[ERROR] No image in response for player {player['name']}, error_type: {error_type}")
                image_data = create_placeholder_image(prompt, current_round)
                # Don't set ai_response here - will be set based on error_type below
            
            # Set user-friendly response message based on error type
            if error_type:
                if error_type == 'policy_violation':
                    ai_response = "Your prompt may have violated content policies. Please try a different prompt."
                elif error_type == 'small_image':
                    ai_response = "Image generation returned an invalid result. Please try a different prompt."
                elif error_type in ['api_error', 'no_image_in_response', 'no_candidates']:
                    ai_response = "Image generation encountered an error. Please try again."
                else:
                    ai_response = "Image generation encountered an issue. Please try again."
                
                # Get character-specific error message and emit as character message
                character_error_message = get_character_error_message(player, current_round)
                character = get_character_for_round(player, current_round)
                
                # Build character data for error message
                character_data = {
                    'character': character,
                    'message': character_error_message,
                    'round': current_round
                }
                
                # Add character-specific state information (error occurred, so no successful prompt yet)
                prompt_count = player.get('prompt_count', 0)
                has_successful_prompt = player.get('has_successful_prompt', {}).get(current_round, False)
                
                if character == 'Bud':
                    # Bud: static pose is always smiling, will animate when message appears
                    character_data['animation_state'] = get_bud_animation_state()
                elif character == 'Spud':
                    # Spud: error occurred, so use current state (hasn't progressed yet)
                    plant_state = get_spud_plant_state(prompt_count, has_successful_prompt)
                    character_data['plant_state'] = plant_state
                    character_data['animation_state'] = get_spud_animation_state(prompt_count, plant_state, is_error=True, has_successful_prompt=has_successful_prompt)
                    character_data['prompt_count'] = prompt_count
                
                # Emit character error message (appears as speech bubble from avatar)
                emit('character_message', character_data, room=player['socket_id'])
                
                # Also emit error for logging/analytics (but character message is primary UI)
                emit('image_generation_error', {
                    'message': character_error_message,
                    'error_type': error_type,
                    'suggest_retry': True
                }, room=player['socket_id'])
                
                # Track error in player's error list
                error_entry = {
                    'round': current_round,
                    'timestamp': time.time(),
                    'error_type': error_type,
                    'prompt': prompt,
                    'error_message': error_message,
                    'finish_reason': finish_reason,
                    'file_size_kb': file_size_kb
                }
                player['image_generation_errors'].append(error_entry)
                print(f"[ERROR TRACKING] Player {player['name']}: {error_type} - {error_message}")
            else:
                # Success case - update character state after successful image generation
                ai_response = "Image generated successfully"
                
                # After successful image generation, update character state with new plant/animation state
                character = get_character_for_round(player, current_round)
                if character == 'Spud':
                    # Spud's state may have changed (e.g., from base to yellow after first success)
                    prompt_count = player.get('prompt_count', 0)
                    has_successful_prompt = player.get('has_successful_prompt', {}).get(current_round, False)
                    plant_state = get_spud_plant_state(prompt_count, has_successful_prompt)
                    animation_state = get_spud_animation_state(prompt_count, plant_state, is_error=False, has_successful_prompt=has_successful_prompt)
                    
                    # Update character state (plant may have changed from base to yellow/dry)
                    character_update = {
                        'character': character,
                        'message': character_message,  # Keep the same message
                        'round': current_round,
                        'plant_state': plant_state,
                        'animation_state': animation_state,
                        'prompt_count': prompt_count
                    }
                    # Emit update to reflect state change (e.g., base -> yellow after first success)
                    emit('character_message', character_update, room=player['socket_id'])
            
        except Exception as img_error:
            print(f"Image generation error: {img_error}")
            error_type = 'exception'
            error_message = str(img_error)
            error_entry = {
                'round': current_round,
                'timestamp': time.time(),
                'error_type': error_type,
                'prompt': prompt,
                'error_message': error_message
            }
            player['image_generation_errors'].append(error_entry)
            print(f"[ERROR TRACKING] Player {player['name']}: Exception in round {current_round}: {img_error}")
            # Fallback to simple placeholder
            image_data = create_placeholder_image(prompt, current_round)
            file_size_kb = None
            finish_reason = None
            safety_ratings = None
            ai_response = "Image generation encountered an error. Please try again."
            
            # Get character-specific error message and emit as character message
            character_error_message = get_character_error_message(player, current_round)
            character = get_character_for_round(player, current_round)
            
            # Build character data for error message
            character_data = {
                'character': character,
                'message': character_error_message,
                'round': current_round
            }
            
            # Add character-specific state information (error occurred)
            prompt_count = player.get('prompt_count', 0)
            has_successful_prompt = player.get('has_successful_prompt', {}).get(current_round, False)
            
            if character == 'Bud':
                # Bud: static pose is always smiling, will animate when message appears
                character_data['animation_state'] = get_bud_animation_state()
            elif character == 'Spud':
                # Spud: error occurred, so use current state
                plant_state = get_spud_plant_state(prompt_count, has_successful_prompt)
                character_data['plant_state'] = plant_state
                character_data['animation_state'] = get_spud_animation_state(prompt_count, plant_state, is_error=True, has_successful_prompt=has_successful_prompt)
                character_data['prompt_count'] = prompt_count
            
            # Emit character error message (appears as speech bubble from avatar)
            emit('character_message', character_data, room=player['socket_id'])
            
            # Also emit error for logging/analytics
            emit('image_generation_error', {
                'message': character_error_message,
                'error_type': error_type,
                'suggest_retry': True
            }, room=player['socket_id'])

        # Store conversation
        conversation.append({'role': 'user', 'content': prompt})
        conversation.append({'role': 'assistant', 'content': ai_response})

        # Calculate prompt index (1-based)
        prompt_index = len(player['images'][current_round]) + 1
        # Note: is_refinement removed - can be determined from prompt_index >= 2 in analysis
        
        # Store generated image (with prompt_id placeholder, will be updated after DB save)
        image_entry = {
            'prompt': prompt,
            'image_data': image_data,
            'timestamp': time.time(),
            'ai_response': ai_response,
            'prompt_id': None,  # Will be set after database save
            'prompt_index': prompt_index,
            'error_type': error_type,  # Store error info in image entry
            'file_size_kb': file_size_kb
        }
        player['images'][current_round].append(image_entry)

        # Save prompt to database and trigger async image upload
        if db.is_configured() and game_state.get('game_id') and game_state.get('round_id'):
            submitted_at = datetime.fromtimestamp(time.time())
            image_generated_at = datetime.fromtimestamp(time.time())
            
            # Save prompt to database (without image_url initially, with error info)
            prompt_id = db.save_prompt_sync(
                game_id=game_state['game_id'],
                round_id=game_state['round_id'],
                player_id=session_id,
                prompt_index=prompt_index,
                prompt_text=prompt,
                image_url=None,  # Will be updated after async upload
                ai_response=ai_response,
                submitted_at=submitted_at,
                image_generated_at=image_generated_at,
                error_type=error_type,
                error_message=error_message,
                finish_reason=finish_reason,
                file_size_kb=file_size_kb,
                safety_ratings=safety_ratings
            )
            
            # Update image_entry with prompt_id
            if prompt_id:
                image_entry['prompt_id'] = prompt_id
                
                # Trigger async upload to Supabase Storage (non-blocking)
                # Pass player_name and round_number for readable folder structure
                db.upload_image_async(
                    image_data=image_data,
                    game_id=game_state['game_id'],
                    player_id=session_id,
                    round_id=game_state['round_id'],
                    prompt_id=prompt_id,
                    prompt_index=prompt_index,
                    player_name=player['name'],  # For readable folder structure
                    round_number=current_round  # Round number (1, 2, or 3)
                )

        emit('image_generated', {
            'image_data': image_data,
            'ai_response': ai_response,
            'prompt': prompt,
            'image_index': len(player['images'][current_round]) - 1,
            'prompt_id': image_entry.get('prompt_id'),  # Include prompt_id for frontend
            'error_type': error_type,  # Include error info
            'file_size_kb': file_size_kb
        }, room=player['socket_id'])
        
        # Update admin dashboard with real-time prompts count
        if admin_session_id in players and players[admin_session_id].get('socket_id'):
            emit('player_prompt_updated', {
                'session_id': session_id,
                'player_name': player['name'],
                'prompts_submitted': len(player['images'][current_round])
            }, room=players[admin_session_id]['socket_id'])

    except Exception as e:
        print(f"Error generating image: {e}")
        error_type = 'outer_exception'
        error_message = str(e)
        error_entry = {
            'round': current_round,
            'timestamp': time.time(),
            'error_type': error_type,
            'prompt': prompt,
            'error_message': error_message
        }
        player['image_generation_errors'].append(error_entry)
        print(f"[ERROR TRACKING] Player {player['name']}: Outer exception in round {current_round}: {e}")
        # Get character-specific error message and emit as character message
        character_error_message = get_character_error_message(player, current_round)
        character = get_character_for_round(player, current_round)
        
        # Build character data for error message
        character_data = {
            'character': character,
            'message': character_error_message,
            'round': current_round
        }
        
        # Add character-specific state information (error occurred)
        prompt_count = player.get('prompt_count', 0)
        has_successful_prompt = player.get('has_successful_prompt', {}).get(current_round, False)
        
        if character == 'Bud':
            # Bud: static pose is always smiling, will animate when message appears
            character_data['animation_state'] = get_bud_animation_state()
        elif character == 'Spud':
            # Spud: error occurred, so use current state
            plant_state = get_spud_plant_state(prompt_count, has_successful_prompt)
            character_data['plant_state'] = plant_state
            character_data['animation_state'] = get_spud_animation_state(prompt_count, plant_state, is_error=True, has_successful_prompt=has_successful_prompt)
            character_data['prompt_count'] = prompt_count
        
        # Emit character error message (appears as speech bubble from avatar)
        emit('character_message', character_data, room=player['socket_id'])
        
        # Also emit error for logging/analytics
        emit('image_generation_error', {
            'message': character_error_message,
            'error_type': error_type,
            'suggest_retry': True
        }, room=player['socket_id'])

def extract_api_error_info(response):
    """
    Extract error information from Gemini API response.
    Returns (error_type, error_message, finish_reason, safety_ratings_dict)
    """
    error_type = None
    error_message = None
    finish_reason = None
    safety_ratings_dict = None
    
    try:
        if not response or not hasattr(response, 'candidates'):
            return None, None, None, None
        
        # Check if response has candidates
        if not response.candidates or len(response.candidates) == 0:
            # No candidates - might be blocked or error
            error_type = 'no_candidates'
            error_message = 'API returned no candidates (possible policy violation or error)'
            return error_type, error_message, None, None
        
        candidate = response.candidates[0]
        
        # Check finish_reason
        if hasattr(candidate, 'finish_reason'):
            finish_reason = str(candidate.finish_reason)
            
            # Map finish_reason to error types
            if finish_reason in ['SAFETY', 'RECITATION']:
                error_type = 'policy_violation'
                error_message = f'Content blocked: {finish_reason}'
            elif finish_reason == 'OTHER':
                error_type = 'api_error'
                error_message = f'API returned finish_reason: {finish_reason}'
            elif finish_reason == 'MAX_TOKENS':
                error_type = 'api_error'
                error_message = 'Response exceeded token limit'
            # 'STOP' is normal completion, not an error
        
        # Check safety_ratings
        if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
            safety_ratings_list = []
            blocked = False
            
            for rating in candidate.safety_ratings:
                rating_dict = {}
                if hasattr(rating, 'category'):
                    rating_dict['category'] = str(rating.category)
                if hasattr(rating, 'probability'):
                    prob = str(rating.probability)
                    rating_dict['probability'] = prob
                    # Check if any rating is HIGH or BLOCKED
                    if prob in ['HIGH', 'BLOCKED']:
                        blocked = True
                        if not error_type:
                            error_type = 'policy_violation'
                            error_message = f'Safety filter triggered: {rating_dict.get("category", "unknown")}'
                
                safety_ratings_list.append(rating_dict)
            
            if safety_ratings_list:
                safety_ratings_dict = safety_ratings_list
        
        # Check for block_reason_message (if available)
        if hasattr(candidate, 'block_reason_message') and candidate.block_reason_message:
            error_type = 'policy_violation'
            error_message = str(candidate.block_reason_message)
        
        # Check for prompt_feedback (if available)
        if hasattr(response, 'prompt_feedback'):
            feedback = response.prompt_feedback
            if hasattr(feedback, 'block_reason'):
                error_type = 'policy_violation'
                error_message = f'Prompt blocked: {feedback.block_reason}'
        
    except Exception as e:
        print(f"Error extracting API error info: {e}")
        # Don't set error_type here - let the caller handle it
    
    return error_type, error_message, finish_reason, safety_ratings_dict

def get_file_size_kb(image_bytes):
    """Calculate file size in KB from image bytes."""
    try:
        return len(image_bytes) / 1024.0
    except:
        return None

def is_small_image(file_size_kb, threshold_kb=50):
    """Check if image is suspiciously small (likely a placeholder)."""
    if file_size_kb is None:
        return False
    return file_size_kb < threshold_kb

def get_character_message(player, current_round):
    """
    Get character message based on current round and player's treatment condition.
    Bud: Progressive messages based on prompt count (15 messages)
    Spud: Progressive messages based on prompt count (15 messages)
    """
    character = get_character_for_round(player, current_round)
    prompt_count = player.get('prompt_count', 0)
    
    if prompt_count <= 0:
        # No message before any prompts
        return None
    
    if character == 'Bud':
        # Bud shows messages progressively based on prompt count
        # prompt_count is incremented before this function is called, so:
        # - After 1st prompt (prompt_count=1): show message[0]
        # - After 2nd prompt (prompt_count=2): show message[1]
        # - etc.
        # - After 15th prompt (prompt_count=15): show message[14] (last message)
        # - After 16+ prompts: repeat last message
        if prompt_count <= len(BUDDY_MESSAGES):
            message_index = prompt_count - 1
            return BUDDY_MESSAGES[message_index]
        else:
            # For 16+ prompts, repeat the last message
            return BUDDY_MESSAGES[-1]
    
    elif character == 'Spud':
        # Spud shows messages progressively based on prompt count
        # prompt_count is incremented before this function is called, so:
        # - After 1st prompt (prompt_count=1): show message[0]
        # - After 2nd prompt (prompt_count=2): show message[1]
        # - etc.
        # - After 15th prompt (prompt_count=15): show message[14] (last message)
        # - After 16+ prompts: repeat last message
        if prompt_count <= len(SPUDDY_MESSAGES):
            message_index = prompt_count - 1
            return SPUDDY_MESSAGES[message_index]
        else:
            # For 16+ prompts, repeat the last message
            return SPUDDY_MESSAGES[-1]
    
    return None

def get_character_error_message(player, current_round):
    """
    Get character-specific error message when image generation fails.
    """
    character = get_character_for_round(player, current_round)
    
    if character == 'Bud':
        return BUDDY_ERROR_MESSAGE
    elif character == 'Spud':
        return SPUDDY_ERROR_MESSAGE
    else:
        return "That prompt didn't go through. Please try a new prompt."

def create_placeholder_image(prompt, round_num):
    """Create a simple placeholder image with text"""
    img = Image.new('RGB', (512, 512), color=(100 + round_num * 30, 150, 200 - round_num * 20))

    # Convert to base64
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    return f"data:image/png;base64,{img_str}"

# Track pending image generations
pending_image_generations = {}  # session_id -> list of pending requests

@socketio.on('round_timer_check')
def handle_round_timer_check():
    # Don't process timer checks if we're showing results or game is over
    # Players should stay on results screen until admin progresses
    if game_state['status'] in ['round_results', 'game_over']:
        return
    
    if game_state['status'] == 'playing':
        time_remaining = game_state['round_end_time'] - time.time()

        if time_remaining <= 0:
            # Round ended - show transition screen
            if game_state['status'] == 'playing':  # Only if still in playing state
                start_transition_to_selection()
        else:
            emit('timer_update', {'time_remaining': time_remaining}, broadcast=True)
    elif game_state['status'] == 'transitioning':
        # Also handle transitioning state - check if we should advance
        # This is the PRIMARY mechanism for ensuring progression (more reliable than background tasks)
        elapsed = time.time() - game_state.get('transition_start_time', time.time())
        min_duration = game_state.get('transition_min_duration', 5)
        max_duration = game_state.get('transition_max_duration', 10)
        
        # Progress after minimum duration (5 seconds) - this ensures automatic progression
        # The round_timer_check is called every second by clients, so this will trigger reliably
        # After 5 seconds minimum, we advance to selection (allowing time for last-second images)
        if elapsed >= min_duration:
            print(f"[TRANSITION] Round timer check: {elapsed:.1f}s elapsed (min: {min_duration}s), advancing to selection")
            if game_state['status'] == 'transitioning':  # Double-check status
                start_voting_phase()
        # Note: We don't need a separate max_duration check here because 
        # elapsed >= min_duration will be true for all values >= 5 seconds

def start_transition_to_selection():
    """Show transition screen, then move to selection after 5-10 seconds"""
    if game_state['status'] == 'transitioning':
        print("[TRANSITION] Already transitioning, ignoring duplicate call")
        return
    
    print("[TRANSITION] Starting transition to selection screen")
    game_state['status'] = 'transitioning'
    game_state['transition_start_time'] = time.time()
    game_state['transition_min_duration'] = 5  # Minimum 5 seconds
    game_state['transition_max_duration'] = 10  # Maximum 10 seconds
    
    # Show transition screen to all players (non-admin) with timer info
    for p in players.values():
        if not p['is_admin']:
            emit('show_transition_screen', {
                'message': "Now you'll get to choose the best image that you created.",
                'max_wait': 10  # Max 10 seconds before auto-progress
            }, room=p['socket_id'])
    
    # Notify admin that transition started
    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        emit('admin_status_update', {
            'status': 'transitioning',
            'round': game_state['current_round']
        }, room=players[admin_session_id]['socket_id'])
    
    # Use multiple approaches for reliability:
    # 1. Background task that fires after max duration (10 seconds)
    def transition_complete_max():
        """Called after max duration (10 seconds) to ensure progression"""
        time.sleep(10.0)  # Wait maximum 10 seconds
        if game_state['status'] == 'transitioning':
            print("[TRANSITION] Max duration (10s) reached, forcing progression to selection")
            start_voting_phase()
        else:
            print(f"[TRANSITION] Status already changed to {game_state['status']}, skipping")
    
    # 2. Also use a periodic check mechanism via round_timer_check
    # The round_timer_check handler will also handle transitioning state
    
    # Start background task for max duration safety net
    socketio.start_background_task(transition_complete_max)
    print("[TRANSITION] Background task started - will force progression after 10 seconds max")
    
    # Note: The round_timer_check handler will also check transitioning state periodically
    # This provides a backup mechanism in case background tasks don't fire
    print("[TRANSITION] Transition started - will progress automatically via background task or polling")

def start_voting_phase():
    """Start the image selection phase"""
    # Prevent duplicate calls
    if game_state['status'] == 'voting':
        print("[VOTING] Already in voting phase, ignoring duplicate call")
        return
    
    # Allow starting from 'transitioning' or 'playing' states
    if game_state['status'] not in ['transitioning', 'playing']:
        print(f"[VOTING] Cannot start voting phase from status: {game_state['status']}")
        return
    
    print(f"[VOTING] Starting voting/selection phase (current status: {game_state['status']})")
    game_state['status'] = 'voting'
    game_state['voting_start_time'] = time.time()
    game_state['voting_duration'] = 30  # 30 seconds to select
    print(f"[VOTING] Status set to 'voting', will emit voting_started to players")
    
    # End current round in database
    if db.is_configured() and game_state.get('round_id'):
        db.end_round(game_state['round_id'])

    # Get all images including any generated during buffer period
    current_round = game_state['current_round']
    
    # Note: Default selection is UI-only. Server will only set it when timer expires or player confirms.
    # This ensures all players get the full 30 seconds to select their preferred image.

    # Notify players to select their best image (or confirm default)
    # Use synchronized start time so all players' timers start at the same time
    selection_start_time = game_state['voting_start_time']
    selection_duration = game_state['voting_duration']
    
    player_count = 0
    for p in players.values():
        if not p['is_admin']:
            player_count += 1
            socket_id = p.get('socket_id')
            if socket_id:
                print(f"[VOTING] Emitting voting_started to player {p['name']} (socket: {socket_id})")
                emit('voting_started', {
                    'round': current_round,
                    'duration': selection_duration,
                    'start_time': selection_start_time,  # Synchronized start time
                    'default_selected': False  # Always False - default is UI-only until timer expires
                }, room=socket_id)
            else:
                print(f"[VOTING] WARNING: Player {p['name']} has no socket_id, cannot emit voting_started")
    print(f"[VOTING] Emitted voting_started to {player_count} players with synchronized start time")
    
    # Notify admin
    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        emit('admin_voting_started', {
            'round': current_round,
            'players': [{
                'name': p.get('display_name', p['name']),
                'team': p['team'],
                'is_connected': p.get('socket_id') is not None,
                'has_selected': current_round in p['selected_images'] and p.get('has_confirmed_selection', False),
                'prompts_submitted': len(p['images'].get(current_round, [])),
                'session_id': p['session_id']
            } for p in players.values() if not p['is_admin']]
        }, room=players[admin_session_id]['socket_id'])
        
        # Also send status update with time remaining
        emit('admin_status', {
            'status': 'voting',
            'round': current_round,
            'time_remaining': 30,
            'players': [{
                'name': p.get('display_name', p['name']),
                'team': p['team'],
                'is_connected': p.get('socket_id') is not None,
                'prompts_submitted': len(p['images'].get(current_round, [])),
                'has_selected': current_round in p['selected_images'] and p.get('has_confirmed_selection', False),
                'session_id': p['session_id'],
                'score': p['score']
            } for p in players.values() if not p['is_admin']],
            'target': game_state.get('current_target')
        }, room=players[admin_session_id]['socket_id'])

    print(f"Voting phase started for round {current_round}")

@socketio.on('select_image')
def handle_select_image(data):
    session_id = session.get('session_id')
    if session_id not in players:
        return

    player = players[session_id]
    image_index = data.get('image_index')
    current_round = game_state['current_round']

    if image_index < len(player['images'][current_round]):
        selected_image = player['images'][current_round][image_index]
        player['selected_images'][current_round] = selected_image
        player['has_confirmed_selection'][current_round] = True  # Mark as confirmed
        
        # Save image selection to database
        if db.is_configured() and game_state.get('game_id') and game_state.get('round_id'):
            prompt_id = selected_image.get('prompt_id')
            if prompt_id:
                db.save_image_selection(
                    player_id=session_id,
                    round_id=game_state['round_id'],
                    game_id=game_state['game_id'],
                    prompt_id=prompt_id
                )
        
        emit('image_selected', {'success': True})

        # Check if all players have selected
        check_all_selected()

def check_all_selected():
    """Check if all players have selected their images, and advance to voting if so"""
    # Don't check if we're already past the voting phase (e.g., showing results)
    if game_state['status'] not in ['voting', 'voting_images']:
        return
    
    current_round = game_state['current_round']
    # Only check non-admin players
    non_admin_players = [p for p in players.values() if not p['is_admin']]
    active_players = [p for p in non_admin_players if p.get('socket_id') is not None]
    
    time_elapsed = time.time() - game_state['voting_start_time']
    duration = game_state.get('voting_duration', 30)
    
    # If time has elapsed, auto-select last valid (non-error) image for players who haven't selected
    if time_elapsed >= duration:
        print(f"[SELECTION] Time elapsed ({time_elapsed:.1f}s >= {duration}s), auto-selecting last valid image for players who haven't selected")
        for player in active_players:
            if current_round not in player['selected_images'] and player['images'].get(current_round):
                # Find the last valid (non-error) image
                valid_images = [img for img in player['images'][current_round] if not img.get('error_type')]
                if valid_images:
                    last_valid_image = valid_images[-1]
                    player['selected_images'][current_round] = last_valid_image
                else:
                    # Fallback: use last image even if it has an error (shouldn't happen, but safety)
                    last_image = player['images'][current_round][-1]
                    player['selected_images'][current_round] = last_image
                
                # Mark as confirmed when auto-selected (timer expired)
                player['has_confirmed_selection'][current_round] = True
                
                # Save to database
                if db.is_configured() and game_state.get('game_id') and game_state.get('round_id'):
                    selected_image = player['selected_images'][current_round]
                    prompt_id = selected_image.get('prompt_id')
                    if prompt_id:
                        db.save_image_selection(
                            player_id=player['session_id'],
                            round_id=game_state['round_id'],
                            game_id=game_state['game_id'],
                            prompt_id=prompt_id
                        )
                
                print(f"[SELECTION] Auto-selected last image for player {player['name']}")
    
    # Check if all players have now confirmed their selection (either manually or via timer expiry)
    all_selected = all(
        player.get('has_confirmed_selection', {}).get(current_round, False)
        for player in active_players
    )
    
    # Emit waiting status to all players (only if time hasn't elapsed)
    if time_elapsed < duration:
        waiting_count = len([p for p in active_players if not p.get('has_confirmed_selection', {}).get(current_round, False)])
        if waiting_count > 0:
            emit('selection_waiting', {'waiting_count': waiting_count, 'total_players': len(active_players)}, broadcast=True)

    # Advance to voting if all selected OR time has elapsed
    if all_selected or (time_elapsed >= duration):
        print(f"[SELECTION] All players have selected or time elapsed, advancing to voting screen")
        start_voting_on_images()

@socketio.on('check_selection_status')
def handle_check_selection_status():
    """Client requests to check selection status (called when timer expires)"""
    if game_state['status'] == 'voting':
        # Check if all players have selected or time has elapsed (will auto-select and advance)
        check_all_selected()

def start_voting_on_images():
    game_state['status'] = 'voting_images'
    current_round = game_state['current_round']

    # Gather all selected images with prompt_id (exclude admin)
    selected_images = []
    for session_id, player in players.items():
        if not player['is_admin'] and current_round in player['selected_images']:
            selected_image = player['selected_images'][current_round]
            selected_images.append({
                'session_id': session_id,
                'player_name': player.get('display_name', player['name']),
                'image': selected_image,
                'prompt_id': selected_image.get('prompt_id')  # Include prompt_id for voting
            })

    # Get target image for this round
    target_image = game_state.get('current_target', {})

    # Send images to each player with their own session_id for filtering (non-admin only)
    for target_session_id in players.keys():
        player = players[target_session_id]
        if not player['is_admin']:
            emit('vote_on_images', {
                'images': selected_images,
                'round': current_round,
                'my_session_id': target_session_id,
                'target_image': {
                    'url': target_image.get('url', '')
                }
            }, room=player['socket_id'])

    print("Players now voting on images")

@socketio.on('cast_vote')
def handle_cast_vote(data):
    session_id = session.get('session_id')
    if session_id not in players:
        return

    voter = players[session_id]
    voted_for_session = data.get('voted_for')
    voted_for_prompt_id = data.get('prompt_id')  # Get prompt_id from frontend
    current_round = game_state['current_round']

    # Can't vote for yourself
    if voted_for_session == session_id:
        emit('self_vote_error', {'message': "You can't vote for yourself!"})
        return

    if voted_for_session in players:
        players[voted_for_session]['votes_received'][current_round] += 1
        voter['has_voted'][current_round] = True
        
        # Save vote to database
        if db.is_configured() and game_state.get('game_id') and game_state.get('round_id') and voted_for_prompt_id:
            db.save_vote(
                voter_id=session_id,
                voted_for_player_id=voted_for_session,
                voted_for_prompt_id=voted_for_prompt_id,
                round_id=game_state['round_id'],
                game_id=game_state['game_id']
            )

        emit('vote_cast', {'success': True})

        # Check if voting is complete
        check_voting_complete()

def check_voting_complete():
    current_round = game_state['current_round']
    # Only count active players (those who haven't left/disconnected)
    active_players = [p for p in players.values() if p.get('socket_id')]
    votes_cast = sum(1 for p in active_players if p['has_voted'][current_round])
    active_count = len(active_players)

    if active_count > 0 and (votes_cast >= active_count * 0.66 or votes_cast == active_count):
        show_round_results()

def show_round_results():
    game_state['status'] = 'round_results'
    current_round = game_state['current_round']

    # Calculate scores (exclude admin)
    results = []
    for session_id, player in players.items():
        if not player['is_admin']:  # Exclude admin from results
            votes = player['votes_received'][current_round]
            player['round_scores'][current_round - 1] = votes
            player['score'] += votes

            results.append({
                'player_name': player.get('display_name', player['name']),
                'votes': votes,
                'total_score': player['score'],
                'image': player['selected_images'].get(current_round, {}).get('image_data', '')
            })

    # Sort by total score for overall leaderboard
    results.sort(key=lambda x: x['total_score'], reverse=True)

    # Send to players only (not admin)
    for p in players.values():
        if not p['is_admin']:
            emit('round_results', {
                'round': current_round,
                'results': results
            }, room=p['socket_id'])
    
    # Send admin view
    if admin_session_id in players and players[admin_session_id].get('socket_id'):
                emit('admin_round_results', {
                'round': current_round,
                'results': results,
                'players': [{
                    'name': p.get('display_name', p['name']),
                    'team': p['team'],
                    'is_connected': p.get('socket_id') is not None,
                    'session_id': p['session_id'],
                    'score': p['score'],
                    'prompts_submitted': len(p['images'].get(current_round, []))
                } for p in players.values() if not p['is_admin']]
            }, room=players[admin_session_id]['socket_id'])

    print(f"Round {current_round} results shown")

@socketio.on('next_round')
def handle_next_round():
    session_id = session.get('session_id')
    
    # Check if player is admin
    if session_id != admin_session_id:
        emit('error', {'message': 'Only admin can advance to next round'})
        return
    
    if game_state['current_round'] < 3:
        game_state['current_round'] += 1
        game_state['status'] = 'playing'
        game_state['current_target'] = game_state['target_images'][game_state['current_round'] - 1]
        game_state['round_start_time'] = time.time()
        game_state['round_end_time'] = game_state['round_start_time'] + 300

        # Create new round in database
        if db.is_configured() and game_state.get('game_id'):
            round_id = db.create_round(
                game_id=game_state['game_id'],
                round_number=game_state['current_round']
            )
            if round_id:
                game_state['round_id'] = round_id

        # Reset current images and prompt count for all players at start of new round
        round_num = game_state['current_round']
        for p in players.values():
            if not p['is_admin']:
                p['current_image'][round_num] = None
                p['prompt_count'] = 0  # Reset prompt count for avatar state
                p['has_successful_prompt'][round_num] = False  # Reset successful prompt tracking
                print(f"[DEBUG] Reset current_image, prompt_count, and has_successful_prompt for player {p['name']}, round {round_num}")

        # Send game started to players only (not admin)
        for p in players.values():
            if not p['is_admin']:
                # Determine character for this round
                character = get_character_for_round(p, game_state['current_round'])
                character_data = {
                    'character': character,
                    'round': game_state['current_round']
                }
                if character == 'Bud':
                    character_data['animation_state'] = get_bud_animation_state()
                elif character == 'Spud':
                    character_data['plant_state'] = 'base'
                    character_data['animation_state'] = 'smiling'
                    character_data['prompt_count'] = 0
                
                emit('game_started', {
                    'round': game_state['current_round'],
                    'target': game_state['current_target'],
                    'end_time': game_state['round_end_time'],
                    'character': character_data
                }, room=p['socket_id'])
        
        # Send admin game started event with player status
        if admin_session_id in players and players[admin_session_id].get('socket_id'):
            current_round_num = game_state['current_round']
            time_remaining = game_state['round_end_time'] - time.time() if game_state.get('round_end_time') else None
            emit('admin_game_started', {
                'round': current_round_num,
                'target': game_state['current_target'],
                'time_remaining': time_remaining,
                'players': [{
                    'name': p.get('display_name', p['name']),
                    'team': p['team'],
                    'is_connected': p.get('socket_id') is not None,
                    'session_id': p['session_id'],
                    'prompts_submitted': len(p['images'].get(current_round_num, []))
                } for p in players.values() if not p['is_admin']]
            }, room=players[admin_session_id]['socket_id'])

        print(f"Round {game_state['current_round']} started")
    else:
        end_game()

def end_game():
    game_state['status'] = 'game_over'
    
    # Mark game as ended in database
    if db.is_configured() and game_state.get('game_id'):
        db.end_game(game_id=game_state['game_id'], rounds_completed=3)

    # Final leaderboard (exclude admin)
    final_results = []
    for session_id, player in players.items():
        if not player['is_admin']:  # Exclude admin from leaderboard
            final_results.append({
                'player_name': player.get('display_name', player['name']),
                'total_score': player['score'],
                'round_scores': player['round_scores'],
                'team': player['team'],
                'character': player['character'],
                'prompt_count': player['prompt_count']
            })

    final_results.sort(key=lambda x: x['total_score'], reverse=True)

    # Send to players only (not admin)
    for p in players.values():
        if not p['is_admin']:
            emit('game_over', {
                'results': final_results
            }, room=p['socket_id'])
    
    # Send admin view
    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        emit('admin_game_over', {
            'results': final_results,
            'players': [{
                'name': p.get('display_name', p['name']),
                'team': p['team'],
                'is_connected': p.get('socket_id') is not None,
                'session_id': p['session_id'],
                'score': p['score'],
                'prompts_submitted': sum(len(p['images'].get(r, [])) for r in [1, 2, 3])
            } for p in players.values() if not p['is_admin']]
        }, room=players[admin_session_id]['socket_id'])

    print("Game over!")
    
    # Set game state to 'lobby' after showing final leaderboard
    # This allows admin to clear players after the game is done
    # Players will still see the leaderboard on their screen, but server state is reset
    game_state['status'] = 'lobby'

@socketio.on('skip_voting')
def handle_skip_voting():
    """Admin-only: Skip voting phase and go to results"""
    session_id = session.get('session_id')
    
    # Check if player is admin
    if session_id != admin_session_id:
        emit('error', {'message': 'Only admin can skip voting'})
        return
    
    # Only allow skipping if we're in voting phase
    if game_state['status'] in ['voting', 'voting_images']:
        if game_state['status'] == 'voting':
            # Still in selection phase - move to image voting
            start_voting_on_images()
        else:
            # In image voting phase - skip to results
            show_round_results()
        # Don't broadcast - admin doesn't need this message, and players don't need to know
        # Admin dashboard already shows the state change
    else:
        emit('error', {'message': 'Not in voting phase'})

@socketio.on('admin_get_status')
def handle_admin_get_status():
    """Admin request for current game status and player info"""
    session_id = session.get('session_id')
    
    # Silently ignore non-admin requests (don't show error popup)
    if session_id != admin_session_id:
        return
    
    current_round = game_state['current_round']
    status = game_state['status']
    
    # Calculate time remaining
    time_remaining = None
    if status == 'playing' and game_state.get('round_end_time'):
        time_remaining = max(0, game_state['round_end_time'] - time.time())
    elif status == 'voting' and game_state.get('voting_start_time') and game_state.get('voting_duration'):
        elapsed = time.time() - game_state['voting_start_time']
        time_remaining = max(0, game_state['voting_duration'] - elapsed)
    elif status == 'transitioning':
        elapsed = time.time() - game_state.get('transition_start_time', time.time())
        min_duration = game_state.get('transition_min_duration', 5)
        time_remaining = max(0, min_duration - elapsed)
    
    # Get player status
    player_status = []
    for p in players.values():
        if not p['is_admin']:
            prompts_submitted = len(p['images'].get(current_round, [])) if current_round > 0 else 0
            has_selected = current_round in p['selected_images'] if status in ['voting', 'voting_images'] else None
            has_voted = p['has_voted'].get(current_round, False) if status == 'voting_images' else None
            
            player_status.append({
                'name': p.get('display_name', p['name']),
                'team': p['team'],
                'is_connected': p.get('socket_id') is not None,
                'prompts_submitted': prompts_submitted,
                'has_selected': has_selected,
                'has_voted': has_voted,
                'session_id': p['session_id'],
                'score': p['score']
            })
    
    emit('admin_status', {
        'status': status,
        'round': current_round,
        'time_remaining': time_remaining,
        'players': player_status,
        'target': game_state.get('current_target')
    })

@socketio.on('admin_end_round')
def handle_admin_end_round():
    """Admin-only: End current round early and move to transition/selection"""
    session_id = session.get('session_id')
    
    if session_id != admin_session_id:
        emit('error', {'message': 'Only admin can end round early'})
        return
    
    # Only allow ending round if currently playing
    if game_state['status'] != 'playing':
        emit('error', {'message': 'Round is not in playing state'})
        return
    
    print(f"[ADMIN] Admin ending round {game_state['current_round']} early")
    # Force transition to selection screen
    start_transition_to_selection()

@socketio.on('restart_game')
def handle_restart_game():
    """Admin-only: Restart game for everyone"""
    global admin_session_id
    session_id = session.get('session_id')
    
    # Check if player is admin
    if session_id != admin_session_id:
        emit('error', {'message': 'Only admin can restart game'})
        return
    
    # Reset game state
    game_state['status'] = 'lobby'
    game_state['current_round'] = 0
    game_state['round_start_time'] = None
    game_state['round_end_time'] = None
    game_state['game_id'] = None
    game_state['round_id'] = None

    # Reset all players
    for player in players.values():
        player['score'] = 0
        player['round_scores'] = [0, 0, 0]
        player['images'] = {1: [], 2: [], 3: []}
        player['selected_images'] = {}
        player['has_confirmed_selection'] = {1: False, 2: False, 3: False}
        player['votes_received'] = {1: 0, 2: 0, 3: 0}
        player['has_voted'] = {1: False, 2: False, 3: False}
        player['prompt_count'] = 0
        player['has_successful_prompt'] = {1: False, 2: False, 3: False}
        player['conversation_history'] = {1: [], 2: [], 3: []}
        player['current_image'] = {1: None, 2: None, 3: None}
        player['image_generation_errors'] = []  # Reset error tracking
        # Reset team assignments (except admin)
        if not player['is_admin']:
            player['team'] = None
            player['character'] = None

    emit('game_restarted', broadcast=True)
    print("Game restarted by admin")

@socketio.on('back_to_home')
def handle_back_to_home():
    """Non-admin: Return to lobby/homepage (individual action)"""
    session_id = session.get('session_id')
    if session_id not in players:
        return
    
    player = players[session_id]
    
    # Only allow non-admin players
    if player['is_admin']:
        emit('error', {'message': 'Admin cannot use Back to Home - use Restart Game instead'})
        return
    
    # Send player back to lobby
    emit('return_to_lobby', {
        'message': 'Returned to lobby'
    })
    print(f"Player {player['name']} returned to lobby")

@socketio.on('clear_lobby')
def handle_clear_lobby():
    """Admin-only: Remove all non-admin players from the lobby"""
    session_id = session.get('session_id')
    
    # Check if player is admin
    if session_id != admin_session_id:
        emit('error', {'message': 'Only admin can clear lobby'})
        return
    
    # Only clear if game is in lobby or game_over (after final leaderboard)
    if game_state['status'] not in ['lobby', 'game_over']:
        emit('error', {'message': 'Can only clear lobby when game is in lobby or game over state'})
        return
    
    # Remove all non-admin players
    players_to_remove = []
    for sess_id, player in list(players.items()):
        if not player['is_admin']:
            players_to_remove.append(sess_id)
            # Remove from player_sessions mapping
            socket_ids_to_remove = [sid for sid, p_sess_id in player_sessions.items() if p_sess_id == sess_id]
            for sid in socket_ids_to_remove:
                if sid in player_sessions:
                    del player_sessions[sid]
            # Disconnect their socket if connected
            if player.get('socket_id'):
                emit('error', {'message': 'You have been removed from the lobby by admin'}, room=player['socket_id'])
                emit('return_to_lobby', {'message': 'Removed from lobby'}, room=player['socket_id'])
    
    # Remove players from dictionary
    for sess_id in players_to_remove:
        if sess_id in players:
            del players[sess_id]
    
    # Broadcast updated lobby
    lobby_players = [{'name': p.get('display_name', p['name']), 'team': p['team'], 'is_admin': p['is_admin'], 'is_connected': p.get('socket_id') is not None} for p in players.values()]
    emit('lobby_players_update', {'players': lobby_players}, broadcast=True)
    
    # Update admin view
    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        emit('player_status_update', {
            'players': [{
                'name': p.get('display_name', p['name']),
                'team': p['team'],
                'is_admin': p['is_admin'],
                'is_connected': p.get('socket_id') is not None,
                'session_id': p['session_id']
            } for p in players.values()]
        }, room=players[admin_session_id]['socket_id'])
    
    print(f"Lobby cleared by admin - removed {len(players_to_remove)} players")

@socketio.on('remove_player')
def handle_remove_player(data):
    """Admin-only: Remove a specific player from the lobby"""
    session_id = session.get('session_id')
    
    # Check if player is admin
    if session_id != admin_session_id:
        emit('error', {'message': 'Only admin can remove players'})
        return
    
    # Only remove if game is in lobby
    if game_state['status'] != 'lobby':
        emit('error', {'message': 'Can only remove players when game is in lobby state'})
        return
    
    target_session_id = data.get('session_id')
    if not target_session_id:
        emit('error', {'message': 'No player session_id provided'})
        return
    
    # Don't allow removing admin
    if target_session_id == admin_session_id:
        emit('error', {'message': 'Cannot remove admin'})
        return
    
    # Check if player exists
    if target_session_id not in players:
        emit('error', {'message': 'Player not found'})
        return
    
    player = players[target_session_id]
    player_name = player.get('display_name', player['name'])
    
    # Remove from player_sessions mapping
    socket_ids_to_remove = [sid for sid, p_sess_id in player_sessions.items() if p_sess_id == target_session_id]
    for sid in socket_ids_to_remove:
        if sid in player_sessions:
            del player_sessions[sid]
    
    # Notify player they've been removed
    if player.get('socket_id'):
        emit('error', {'message': 'You have been removed from the lobby by admin'}, room=player['socket_id'])
        emit('return_to_lobby', {'message': 'Removed from lobby'}, room=player['socket_id'])
    
    # Remove player from dictionary
    del players[target_session_id]
    
    # Broadcast updated lobby
    lobby_players = [{'name': p.get('display_name', p['name']), 'team': p['team'], 'is_admin': p['is_admin'], 'is_connected': p.get('socket_id') is not None} for p in players.values()]
    emit('lobby_players_update', {'players': lobby_players}, broadcast=True)
    
    # Update admin view
    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        emit('player_status_update', {
            'players': [{
                'name': p.get('display_name', p['name']),
                'team': p['team'],
                'is_admin': p['is_admin'],
                'is_connected': p.get('socket_id') is not None,
                'session_id': p['session_id']
            } for p in players.values()]
        }, room=players[admin_session_id]['socket_id'])
    
    print(f"Player {player_name} (session: {target_session_id}) removed by admin")

if __name__ == '__main__':
    # Get port from environment variable (for Railway/deployment) or default to 8000
    port = int(os.environ.get('PORT', 8000))
    # Disable debug mode in production
    debug = os.environ.get('FLASK_ENV') != 'production'
    
    print(f"Starting PromptCraft server on http://0.0.0.0:{port}")
    print("Make sure to set GEMINI_API_KEY in .env file")
    if os.getenv('ADMIN_CODE'):
        print(f"Admin code is configured (hidden for security)")
    else:
        print("⚠️  WARNING: ADMIN_CODE not set - first player will become admin")
    print("\n📊 Analytics endpoints:")
    print(f"   - http://localhost:{port}/analytics/errors - View image generation error tracking")
    print()
    socketio.run(app, host='0.0.0.0', port=port, debug=debug, allow_unsafe_werkzeug=debug)
