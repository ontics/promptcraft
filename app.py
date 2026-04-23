from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import google.generativeai as genai
import google.genai as google_genai
import os
import random
import time
import base64
import gc
import json
import threading
import resource
import concurrent.futures
import socket
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv
import io
from PIL import Image

# Load environment variables BEFORE importing db
load_dotenv()

import db  # Database helper module
import heuristics as heur_mod
from voting_fixtures import get_fixture_rounds, TOTAL_VOTING_ROUNDS, NUM_HARDCODED_VOTING_ROUNDS

# Allocation rounds 1–9: fixture JSON groups (target Oski / Tree / slug). See story per-player-randomized-allocation-fixture-order-1-9.
_ALLOC_FIXTURE_GROUP_A = (1, 2, 3)
_ALLOC_FIXTURE_GROUP_B = (4, 5, 6)
_ALLOC_FIXTURE_GROUP_C = (7, 8, 9)
_ALLOC_FIXTURE_GROUPS = (_ALLOC_FIXTURE_GROUP_A, _ALLOC_FIXTURE_GROUP_B, _ALLOC_FIXTURE_GROUP_C)


def build_allocation_fixture_order(rng=None):
    """
    Per player: a permutation of fixture indices 1..9 such that consecutive ordinals never share a group.
    Random cycle order of the three groups; each group has a random anchor then shuffled remainder.
    """
    r = rng or random
    cycle = list(_ALLOC_FIXTURE_GROUPS)
    r.shuffle(cycle)
    queues = {}
    for G in _ALLOC_FIXTURE_GROUPS:
        anchor = r.choice(G)
        rest = [x for x in G if x != anchor]
        r.shuffle(rest)
        queues[G] = [anchor] + rest
    seq = []
    for i in range(NUM_HARDCODED_VOTING_ROUNDS):
        G = cycle[i % 3]
        seq.append(queues[G].pop(0))
    return seq


ALLOCATION_FINAL_SUBMIT_KEY = '__allocation_final__'
# Rounds 1–9 allocation: ballot heuristic_snapshot may include this key (text-box identity when decoupled from image column). See stories/allocation-voting-decoupled-column-shuffles.md
ALLOCATION_HEURISTIC_SOURCE_FIXTURE_KEY = '_allocation_heuristic_source_fixture_id'

from ballot_balancer import assign_final_ballots

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
# Use threading instead of eventlet for Python 3.12 compatibility
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Configure Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# --- Lightweight instrumentation + generation backpressure ---
_GEN_METRICS_LOCK = threading.Lock()
_GEN_IN_FLIGHT = 0

_GEN_EXECUTOR_LOCK = threading.Lock()
_GEN_EXECUTOR: Optional[concurrent.futures.ThreadPoolExecutor] = None

_PLAYER_GEN_LOCK = threading.Lock()
_PLAYER_GEN_INFLIGHT: dict[str, int] = {}

_GEN_SEMAPHORE_LOCK = threading.Lock()
_GEN_SEMAPHORE: Optional[threading.Semaphore] = None


def _max_concurrent_generations() -> int:
    try:
        v = int(os.getenv("PROMPTCRAFT_MAX_CONCURRENT_GENERATIONS", "6") or "6")
        return max(1, min(32, v))
    except Exception:
        return 6


def _max_inflight_per_player() -> int:
    try:
        v = int(os.getenv("PROMPTCRAFT_MAX_INFLIGHT_PER_PLAYER", "2") or "2")
        return max(1, min(10, v))
    except Exception:
        return 2


def _get_gen_executor() -> concurrent.futures.ThreadPoolExecutor:
    global _GEN_EXECUTOR
    with _GEN_EXECUTOR_LOCK:
        if _GEN_EXECUTOR is None:
            _GEN_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
                max_workers=_max_concurrent_generations(),
                thread_name_prefix="promptcraft-gen",
            )
        return _GEN_EXECUTOR


def _get_gen_semaphore() -> threading.Semaphore:
    """Global concurrency cap for slow generation work."""
    global _GEN_SEMAPHORE
    with _GEN_SEMAPHORE_LOCK:
        if _GEN_SEMAPHORE is None:
            _GEN_SEMAPHORE = threading.Semaphore(_max_concurrent_generations())
        return _GEN_SEMAPHORE


def _metrics_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def log_metric(event: str, **fields) -> None:
    row = {"ts": _metrics_now_iso_z(), "event": event, **fields}
    try:
        print("[METRIC] " + json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        print(f"[METRIC] {event} (unserializable fields)")


def _process_rss_mb_best_effort() -> Optional[float]:
    try:
        ru = resource.getrusage(resource.RUSAGE_SELF)
        maxrss = float(getattr(ru, "ru_maxrss", 0.0))
        if maxrss <= 0:
            return None
        if maxrss > 10_000_000:  # likely bytes (macOS)
            return maxrss / (1024.0 * 1024.0)
        return maxrss / 1024.0  # KB -> MB (Linux)
    except Exception:
        return None


def _metrics_heartbeat_loop(interval_sec: float) -> None:
    while True:
        try:
            with _GEN_METRICS_LOCK:
                inflight = _GEN_IN_FLIGHT
            log_metric(
                "process.heartbeat",
                pid=os.getpid(),
                host=socket.gethostname(),
                game_status=game_state.get("status"),
                game_id=game_state.get("game_id"),
                round_id=game_state.get("round_id"),
                inflight_generations=inflight,
                stub_image_gen=os.getenv("PROMPTCRAFT_STUB_IMAGE_GEN"),
                rss_mb=_process_rss_mb_best_effort(),
                gc_counts=list(gc.get_count()),
            )
        except Exception:
            pass
        time.sleep(interval_sec)


def start_metrics_heartbeat_if_enabled() -> None:
    interval = float(os.getenv("PROMPTCRAFT_METRICS_HEARTBEAT_SEC", "15") or "15")
    if interval <= 0:
        return
    t = threading.Thread(
        target=_metrics_heartbeat_loop,
        args=(interval,),
        daemon=True,
        name="promptcraft-metrics-heartbeat",
    )
    t.start()

# Reuse one google.genai Client for all prompts — constructing a Client per request adds measurable latency.
_genai_sdk_client: Optional[object] = None


def get_google_genai_client():
    global _genai_sdk_client
    if _genai_sdk_client is None:
        key = os.getenv('GEMINI_API_KEY')
        if not key:
            return None
        _genai_sdk_client = google_genai.Client(api_key=key)
    return _genai_sdk_client

# Practice onboarding prompting window (server sync); cleared when leaving prompting or onboarding.
ONBOARDING_PROMPTING_DURATION_SEC = 180

# After R1/R2 image selection; players see transition until Gamemaster clicks Next Round.
NEXT_ROUND_SOON_MESSAGE = (
    'Next round will start soon. Please wait for the Gamemaster to continue.'
)

# After R3 image selection; players wait until Gamemaster starts voting.
READY_TO_VOTE_MESSAGE = 'Voting will start soon. Please wait for the Gamemaster to continue.'

# Game state
game_state = {
    'status': 'lobby',  # lobby, onboarding, playing, transitioning, voting, awaiting_next_prompting, awaiting_voting_start, voting_prep, allocation_voting, round_results, game_over
    'current_round': 0,
    'round_start_time': None,
    'round_end_time': None,
    'voting_start_time': None,
    'voting_active_players': [],  # Track players active when voting started
    'game_id': None,  # Database game_id
    'round_id': None,  # Current round's database round_id
    'target_images': [
        {'id': 1, 'url': '/static/images/target1.jpg'},
        {'id': 2, 'url': '/static/images/target2.jpg'},
        {'id': 3, 'url': '/static/images/target3.jpg'}
    ],
    'current_target': None,
    # Practice prompting before scored rounds (see start_onboarding)
    'onboarding_target': {'id': 0, 'url': '/static/images/onboarding-target.png'},
    # Sub-phase when status == 'onboarding': 'prompting' | 'practice_voting'
    'onboarding_phase': 'prompting',
    # Unix time when onboarding practice prompting ends (no auto-advance; display only).
    'onboarding_prompting_end_time': None,
    # Post-game survey: opens automatically when voting is fully completed.
    'post_survey_active': False,
    'last_game_over_payload': None,
    # Point-allocation voting (9 fixture rounds + 1 final); each player advances independently
    # DB: one voting_rounds row per vignette per game (fixture_set_key), not per display order.
    'allocation_vignette_vrids': {},  # fixture_set_key -> voting_round_id (shared across voters)
    'allocation_final_vrid': None,  # shared voting_round_id for kind=final (round 10)
    'allocation_vignette_submitters': {},  # fixture_set_key | '__allocation_final__' -> set(session_id)
    'allocation_emit_vrid': {},  # (session_id, display_ordinal_1_to_10) -> voting_round_id used for that emit
    'allocation_round_submitters': {},  # display_ordinal -> set(session_id) submitted that step (admin / legacy)
    'allocation_points_recorded': set(),  # (voter_session_id, display_ordinal) with saved points
    'allocation_ballot_map': {},  # (voter_session_id, display_ordinal) -> ballot_id
    'allocation_slot_owners': {},  # (voter_session_id, display_ordinal) -> [owner_sid x3]
    'final_allocation_plan': None,  # voter -> [owner_sid x3] for round 10
    # No visible countdown; value only caps auto-advance if clients stop polling (see round_timer_check).
    'allocation_duration': 86400.0,
    'allocation_session_started_at': None,  # time.time() when allocation phase begins
    'allocation_experiment_finalized': False,
    '_synthetic_ballot_seq': 0,
    '_synthetic_prompt_seq': 0,  # negative prompt_ids when DB insert fails (in-memory selection only)
}

players = {}  # session_id: player_data
player_sessions = {}  # socket_id: session_id
admin_session_id = None  # Track the admin player

# Start periodic process heartbeat metrics (default every 15s).
start_metrics_heartbeat_if_enabled()

ANIMAL_ALIASES = [
    'Wildcat', 'Shark', 'Bear', 'Fox', 'Otter', 'Hawk', 'Wolf', 'Tiger', 'Panda', 'Koala',
    'Dolphin', 'Eagle', 'Badger', 'Raven', 'Cobra', 'Jaguar', 'Moose', 'Falcon', 'Lynx', 'Orca',
    'Leopard', 'Giraffe', 'Rhino', 'Hippo', 'Bison', 'Cheetah', 'Panther', 'Wombat', 'Gecko', 'Mantis',
    'Buffalo', 'Camel', 'Caribou', 'Chameleon', 'Crane', 'Crocodile', 'Ferret', 'Flamingo', 'Gazelle', 'Heron',
    'Ibis', 'Iguana', 'Jackal', 'Kangaroo', 'Kingfisher', 'Lemur', 'Lobster', 'Magpie', 'Narwhal', 'Ocelot',
    'Pelican', 'Quokka', 'Raccoon', 'Salamander', 'Sea Lion', 'Sparrow', 'Stoat', 'Tapir', 'Viper', 'Walrus'
]

def get_unique_animal_alias() -> str:
    existing_names = {
        p.get('display_name', p.get('name'))
        for p in players.values()
        if not p.get('is_admin')
    }
    existing_names = {n for n in existing_names if n}

    candidates = ANIMAL_ALIASES[:]
    random.shuffle(candidates)
    for alias in candidates:
        if alias not in existing_names:
            return alias

    base = random.choice(ANIMAL_ALIASES) if ANIMAL_ALIASES else 'Player'
    suffix = 2
    while f"{base} {suffix}" in existing_names:
        suffix += 1
    return f"{base} {suffix}"


def use_stub_image_generation():
    """Use local placeholder images instead of Gemini (no API key, or PROMPTCRAFT_STUB_IMAGE_GEN=1)."""
    flag = os.getenv('PROMPTCRAFT_STUB_IMAGE_GEN', '').strip().lower()
    if flag in ('1', 'true', 'yes', 'on'):
        return True
    key = os.getenv('GEMINI_API_KEY')
    return not (key and str(key).strip())


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
    "The cooling water for your prompt could've kept a small houseplant alive for a day.",
    "By now, you've used enough power to toast a slice of bread.",
    "You've emitted as much CO2 as driving half a mile!",
    "That's a full bottle of fresh water consumed. I was gonna drink that!",
    "You've used more energy this round than charging your phone 8 times over!",
    "Humans need 8 glasses of water a day. Your prompting just used them up. Feeling thirsty?",
    "The power used in this session could've kept the house lights on for 3 days. Gone in minutes for… this?",
    "You're making the trees work overtime! My leaves are drying up…",
    "You've used enough power to run a microwave for 3 hours. It's getting toasty in here!",
    "The cooling water for this image could've filled 551 fish tanks.",
    "Eleven images. Data centers consume 1% of global electricity. And you just added to it…",
    "Did you know 20,000 trees have been burned to clear land for new data center construction?",
    "You would need 12 earths to sustain your current levels of natural resource consumption!",
    "Your carbon footprint is among the highest 1% of individuals. Is it lonely at the top?",
    "OK, fifteen images? That's the same emissions as flying three times around the world.",
    "This is terrible for the environment. How are you still going?"
]

# Spud error message
SPUDDY_ERROR_MESSAGE = "That prompt didn't go through. You could try again... or call it an accidental act of sustainability?"

def generate_session_id():
    return os.urandom(16).hex()

# Four study groups (stored in DB `condition` and shown in admin). C_* = control; T_* = treatment.
PLAYER_GROUPS = ('C_NA', 'C_HU', 'T_NA', 'T_HU')

# Study arms that see bullet context under images during live play (empty = hidden for everyone).
IMAGE_CONTEXT_BULLET_TEAMS = frozenset()


def player_gets_image_context_bullets(player):
    """True when this player should see gameplay bullet slots under target / gallery images (not onboarding)."""
    if not player or player.get('is_admin'):
        return False
    return player.get('condition') in IMAGE_CONTEXT_BULLET_TEAMS


def is_control_group(team):
    """Control groups see Buddy/Bud; treatment groups see Spuddy/Spud. Legacy Green/Orange still supported."""
    if team in ('C_NA', 'C_HU', 'Green'):
        return True
    if team in ('T_NA', 'T_HU', 'Orange'):
        return False
    return False  # None / unknown: same as old non-Green (treatment)


def assign_team():
    """Random single-group pick (e.g. for tests); lobby assignment uses split_into_player_groups."""
    return random.choice(PLAYER_GROUPS)


def get_character(team):
    return 'Buddy' if is_control_group(team) else 'Spuddy'


def get_character_for_round(player, current_round):
    """
    Determine which character a player sees based on round number.
    Round 1: All players see Bud (control)
    Rounds 2-3: C_NA / C_HU (and legacy Green) see Bud; T_NA / T_HU (and legacy Orange) see Spud (treatment)
    """
    if current_round == 1:
        return 'Bud'
    return 'Bud' if is_control_group(player.get('condition')) else 'Spud'


def game_started_aggregate_heuristic_fields(player: dict) -> dict:
    """
    T_NA / T_HU only: rounds 2–3 show under-target aggregate heuristics immediately (zeros)
    before the first prompt; round 1 keeps panel hidden until the first image_generated.
    """
    r = int(game_state.get('current_round') or 1)
    if r < 2 or r > 3 or not heur_mod.show_prompting_heuristics(player.get('condition')):
        return {
            'show_aggregate_heuristics_immediate': False,
            'aggregate_heuristic_preview': [],
        }
    agg_zero = heur_mod.aggregate_snapshot_for_round(total_prompts=0, total_words=0)
    return {
        'show_aggregate_heuristics_immediate': True,
        'aggregate_heuristic_preview': heur_mod.format_aggregate_for_ui(agg_zero),
    }


def split_into_player_groups(shuffled_players, group_labels=PLAYER_GROUPS):
    """
    Split a shuffled list across len(group_labels) groups.

    Each label gets floor(n/k) players from consecutive slices of the shuffled list (order of labels
    is fixed only for slicing, not for absorbing overflow). Each remaining player (n % k) is assigned
    with a uniform random choice among labels that have not yet received a remainder slot in this
    split (k-way die, then (k-1)-way, etc.)—so remainder players never stack on the same label.
    """
    n = len(shuffled_players)
    k = len(group_labels)
    if k == 0:
        return []
    base = n // k
    remainder = n % k
    buckets = {label: [] for label in group_labels}
    idx = 0
    for label in group_labels:
        buckets[label].extend(shuffled_players[idx : idx + base])
        idx += base
    remainder_labels_used = set()
    for p in shuffled_players[idx : idx + remainder]:
        eligible = [L for L in group_labels if L not in remainder_labels_used]
        pick = random.choice(eligible)
        buckets[pick].append(p)
        remainder_labels_used.add(pick)
    return [(label, buckets[label]) for label in group_labels]


# Pre-lobby survey (proficiency, frequency, free response)
VALID_SURVEY_PROFICIENCY = frozenset({'novice', 'beginner', 'intermediate', 'advanced'})
VALID_SURVEY_FREQUENCY = frozenset({'never', 'rarely', 'sometimes', 'often', 'very_often'})
SURVEY_SKILLS_MAX_LEN = 2000
POST_SURVEY_TEXT_MAX_LEN = 2000
VALID_POST_SURVEY_LIKERT = frozenset(
    {'strongly_disagree', 'disagree', 'neutral', 'agree', 'strongly_agree'}
)
VALID_POST_SURVEY_MATRIX1 = frozenset({'far_less', 'somewhat_less', 'same', 'somewhat_more', 'far_more'})
POST_SURVEY_M1_STEMS = ('longer', 'more', 'time', 'vocab')
POST_SURVEY_M1_ROWS = ('creative', 'precise', 'skilled', 'efficient')
POST_SURVEY_M2_KEYS = (
    'visual_similarity',
    'considers_prompt_count',
    'considers_word_count',
    'considers_time_spent',
    'value_not_easily_created',
    'few_prompts_better_understands',
    'dozens_poor_engineering',
)


def ensure_survey_fields(player):
    player.setdefault('survey_completed', False)
    player.setdefault('survey_proficiency', None)
    player.setdefault('survey_frequency', None)
    player.setdefault('survey_skills_text', None)


def ensure_post_survey_fields(player):
    player.setdefault('post_survey_completed', False)


def parse_post_survey_extended(data):
    payload = data or {}
    matrix1 = payload.get('matrix1') or {}
    matrix2 = payload.get('matrix2') or {}
    if not isinstance(matrix1, dict) or not isinstance(matrix2, dict):
        return None, 'Please answer every question before submitting.'
    for stem in POST_SURVEY_M1_STEMS:
        stem_block = matrix1.get(stem)
        if not isinstance(stem_block, dict):
            return None, 'Please answer every question before submitting.'
        for row in POST_SURVEY_M1_ROWS:
            if stem_block.get(row) not in VALID_POST_SURVEY_MATRIX1:
                return None, 'Please answer every question before submitting.'
    for key in POST_SURVEY_M2_KEYS:
        if matrix2.get(key) not in VALID_POST_SURVEY_LIKERT:
            return None, 'Please answer every question before submitting.'
    return {'matrix1': matrix1, 'matrix2': matrix2}, None


def build_post_survey_behavior_snapshot(player):
    """Attach compact gameplay behavior for UID-linked analysis with survey responses."""
    images = player.get('images') or {}
    per_round_prompt_counts = {}
    prompt_count_total = 0
    for round_num in (1, 2, 3):
        cnt = len(images.get(round_num, []))
        per_round_prompt_counts[str(round_num)] = cnt
        prompt_count_total += cnt
    return {
        'player_id': player.get('session_id'),
        'game_id': game_state.get('game_id'),
        'condition': player.get('condition'),
        'prompt_count_total': prompt_count_total,
        'prompt_count_by_round': per_round_prompt_counts,
        'selected_prompt_ids_by_round': {
            str(round_num): (player.get('selected_images', {}).get(round_num, {}) or {}).get('prompt_id')
            for round_num in (1, 2, 3)
        },
        'votes_received_by_round': {
            str(round_num): int((player.get('votes_received', {}) or {}).get(round_num, 0))
            for round_num in (1, 2, 3)
        },
        'round_scores': list(player.get('round_scores', []) or []),
        'total_score': player.get('score'),
        'incentive_points': player.get('incentive_points', 0),
    }


def open_post_survey_after_game_over(game_over_payload):
    """Auto-open post survey for non-admins and hold results until submission."""
    game_state['post_survey_active'] = True
    game_state['last_game_over_payload'] = game_over_payload
    for p in players.values():
        if p.get('is_admin'):
            continue
        ensure_post_survey_fields(p)
        hydrate_post_survey_from_db(p)
        sock = p.get('socket_id')
        if not sock:
            continue
        if p.get('post_survey_completed'):
            socketio.emit('game_over', game_over_payload, room=sock)
        else:
            socketio.emit('post_survey_started', {'game_over': game_over_payload}, room=sock)
    notify_admin_player_list()


def open_post_survey_for_player(player):
    """Open post survey immediately for one non-admin player once they finish voting."""
    if not player or player.get('is_admin'):
        return
    ensure_post_survey_fields(player)
    hydrate_post_survey_from_db(player)
    sock = player.get('socket_id')
    if not sock:
        return
    if player.get('post_survey_completed'):
        payload = game_state.get('last_game_over_payload')
        if payload:
            socketio.emit('game_over', payload, room=sock)
        return
    socketio.emit('post_survey_started', {'game_over': game_state.get('last_game_over_payload')}, room=sock)


def hydrate_post_survey_from_db(player):
    """If this player already submitted post-survey for current game, set completed flag."""
    if not db.is_configured():
        return
    gid = game_state.get('game_id')
    sid = player.get('session_id')
    if not gid or not sid:
        return
    if db.player_has_completed_post_survey(gid, sid):
        player['post_survey_completed'] = True


def emit_post_survey_if_pending(player):
    """Tell client to open post-survey UI when session is active and they have not finished."""
    if player.get('is_admin'):
        return
    ensure_post_survey_fields(player)
    hydrate_post_survey_from_db(player)
    sock = player.get('socket_id')
    if not sock:
        return
    if game_state.get('post_survey_active') and not player.get('post_survey_completed'):
        payload = game_state.get('last_game_over_payload')
        if payload:
            socketio.emit('post_survey_started', {'game_over': payload}, room=sock)
        else:
            socketio.emit('post_survey_started', {}, room=sock)


def game_joined_player_snapshot(player):
    ensure_survey_fields(player)
    ensure_post_survey_fields(player)
    hydrate_post_survey_from_db(player)
    snapshot = {
        'name': player.get('display_name', player['name']),
        'condition': player.get('condition') or player.get('team'),
        'character': player['character'],
        'score': player['score'],
        'is_admin': player['is_admin'],
        'survey_completed': bool(player.get('survey_completed')),
        'post_survey_completed': bool(player.get('post_survey_completed')),
        'post_survey_active': bool(game_state.get('post_survey_active')),
    }
    if (
        not player.get('is_admin')
        and player.get('post_survey_completed')
        and game_state.get('last_game_over_payload')
    ):
        snapshot['post_survey_game_over'] = game_state.get('last_game_over_payload')
    return snapshot


def lobby_player_row(p, use_socket_id_key=False):
    """Single entry for lobby_players_update / game_joined lobby list."""
    ensure_survey_fields(p)
    row = {
        'name': p.get('display_name', p['name']),
        'condition': p['condition'],
        'is_admin': p['is_admin'],
    }
    if use_socket_id_key:
        row['socket_id'] = p.get('socket_id') is not None
    else:
        row['is_connected'] = p.get('socket_id') is not None
    if not p.get('is_admin'):
        row['survey_completed'] = bool(p.get('survey_completed'))
    return row


def admin_lobby_player_row(p):
    """Admin dashboard player row in lobby (includes session_id and survey status)."""
    ensure_survey_fields(p)
    d = {
        'name': p.get('display_name', p['name']),
        'condition': p['condition'],
        'is_admin': p['is_admin'],
        'is_connected': p.get('socket_id') is not None,
        'session_id': p['session_id'],
    }
    if not p.get('is_admin'):
        ensure_post_survey_fields(p)
        d['survey_completed'] = bool(p.get('survey_completed'))
        d['post_survey_completed'] = bool(p.get('post_survey_completed'))
        sn = p.get('seat_number')
        if sn is not None and sn != '':
            try:
                d['seat_number'] = int(sn)
            except (TypeError, ValueError):
                d['seat_number'] = None
        else:
            d['seat_number'] = None
    return d


def admin_seat_number_for_payload(p):
    """Normalize seat_number for admin-only JSON (int or None). Caller should pass non-admin players."""
    sn = p.get('seat_number')
    if sn is not None and sn != '':
        try:
            return int(sn)
        except (TypeError, ValueError):
            return None
    return None


def gamemaster_can_start_post_survey():
    """Post-survey is auto-opened after voting completion; no lobby start action."""
    return False


def admin_joined_payload():
    return {
        'is_admin': True,
        'players': [admin_player_status_row_with_round(p) for p in players.values()],
        'post_survey_active': bool(game_state.get('post_survey_active')),
        'can_start_post_survey': gamemaster_can_start_post_survey(),
        'game_status': game_state['status'],
        'current_round': game_state.get('current_round', 0),
        'onboarding_phase': game_state.get('onboarding_phase') if game_state['status'] == 'onboarding' else None,
        'game_id': game_state.get('game_id'),
    }


def admin_player_status_payload():
    return {
        'players': [admin_player_status_row_with_round(p) for p in players.values()],
        'post_survey_active': bool(game_state.get('post_survey_active')),
        'can_start_post_survey': gamemaster_can_start_post_survey(),
        'game_status': game_state['status'],
        'current_round': game_state.get('current_round', 0),
        'onboarding_phase': game_state.get('onboarding_phase') if game_state['status'] == 'onboarding' else None,
        'game_id': game_state.get('game_id'),
    }


def admin_player_status_row_with_round(p):
    """Gamemaster status row: lobby fields plus round prompts/selection/vote flags."""
    ensure_survey_fields(p)
    cr = game_state.get('current_round', 0)
    st = game_state['status']
    if st == 'onboarding':
        phase = game_state.get('onboarding_phase', 'prompting')
        row = {
            **admin_lobby_player_row(p),
            'prompts_submitted': len(p.get('onboarding_images', [])),
            'has_selected': None,
            'has_voted': None,
        }
        if phase == 'practice_voting':
            row['practice_vote_submitted'] = bool(p.get('onboarding_practice_submitted'))
        return row
    include_game_state = st != 'lobby' and cr > 0
    row = {
        **admin_lobby_player_row(p),
        'prompts_submitted': len(p['images'].get(cr, [])) if include_game_state else 0,
        'round10_points': int(p.get('incentive_points', 0) or 0),
        'has_selected': (
            (cr in p['selected_images'])
            if include_game_state and st in ['voting', 'voting_images', 'awaiting_next_prompting', 'awaiting_voting_start']
            else None
        ),
        'has_voted': (
            p['has_voted'].get(cr, False)
            if include_game_state and st == 'voting_images'
            else None
        ),
    }
    if st == 'allocation_voting' and not p.get('is_admin'):
        row['allocation_voting_round'] = p.get('allocation_player_round')
        row['allocation_voting_total'] = TOTAL_VOTING_ROUNDS
    return row


def notify_admin_player_list():
    """Push full player rows to the Gamemaster dashboard when the roster changes."""
    if admin_session_id not in players:
        return
    adm_sock = players[admin_session_id].get('socket_id')
    if not adm_sock:
        return
    socketio.emit('player_status_update', admin_player_status_payload(), room=adm_sock)


def ensure_onboarding_player_fields(player):
    """Scratch state for practice prompting (not scored, not persisted as round prompts)."""
    player.setdefault('onboarding_images', [])
    player.setdefault('onboarding_conversation', [])
    player.setdefault('onboarding_current_image', None)
    player.setdefault('onboarding_prompt_count', 0)
    player.setdefault('onboarding_has_successful', False)
    player.setdefault('onboarding_practice_submitted', False)
    player.setdefault('onboarding_practice_points', None)


def onboarding_practice_voting_option_slots():
    """Fixed option images for onboarding practice distribution (same paths as templates/index.html)."""
    return [
        {'slot': 1, 'label': 'Option 1', 'url': '/static/images/onboarding-practice-option-1.png'},
        {'slot': 2, 'label': 'Option 2', 'url': '/static/images/onboarding-practice-option-2.png'},
        {'slot': 3, 'label': 'Option 3', 'url': '/static/images/onboarding-practice-option-3.png'},
    ]


def emit_onboarding_practice_voting_to_player(player, socket_room):
    """Send practice voting UI payload to one connected non-admin player."""
    target = game_state.get('onboarding_target') or {'id': 0, 'url': '/static/images/onboarding-target.png'}
    payload = {
        'target': target,
        'option_images': onboarding_practice_voting_option_slots(),
        'existing_points': player.get('onboarding_practice_points'),
        'already_submitted': bool(player.get('onboarding_practice_submitted')),
        'show_voting_heuristics': heur_mod.show_voting_heuristics(player.get('condition')),
    }
    socketio.emit('onboarding_practice_voting_started', payload, room=socket_room)


def broadcast_onboarding_practice_voting():
    """Switch onboarding to practice voting and notify players + Gamemaster."""
    game_state['onboarding_prompting_end_time'] = None
    game_state['onboarding_phase'] = 'practice_voting'
    for p in players.values():
        if p['is_admin']:
            continue
        p['onboarding_practice_points'] = None
        p['onboarding_practice_submitted'] = False
        sid = p.get('socket_id')
        if sid:
            emit_onboarding_practice_voting_to_player(p, sid)
    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        adm = players[admin_session_id]['socket_id']
        socketio.emit(
            'admin_onboarding_practice_voting',
            {
                'phase': 'practice_voting',
                'target': game_state.get('onboarding_target') or {'id': 0, 'url': '/static/images/onboarding-target.png'},
            },
            room=adm,
        )
    notify_admin_player_list()


def onboarding_buddy_progress_message(onboarding_prompt_index):
    """Buddy line after each practice prompt; onboarding_prompt_index is 1-based."""
    if onboarding_prompt_index <= 0:
        return None
    if onboarding_prompt_index <= len(BUDDY_MESSAGES):
        return BUDDY_MESSAGES[onboarding_prompt_index - 1]
    return BUDDY_MESSAGES[-1]


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
            socketio.emit('player_left', {'player_name': player.get('display_name', player['name']), 'session_id': session_id})
            # Update admin view with connection status
            if admin_session_id in players and players[admin_session_id].get('socket_id'):
                notify_admin_player_list()
        print(f"Player {player['name']} disconnected")

    if request.sid in player_sessions:
        del player_sessions[request.sid]


@socketio.on('resume_session')
def handle_resume_session(_data=None):
    """Allow clients to refresh and rehydrate state without pressing Join Game again."""
    session_id = session.get('session_id')
    if not session_id or session_id not in players:
        return
    player = players[session_id]
    if player.get('socket_id') != request.sid:
        player['socket_id'] = request.sid
    # Reuse existing reconnection path (send state + images if mid-game, or lobby snapshot if in lobby).
    handle_join_game({})

@socketio.on('join_game')
def handle_join_game(data):
    global admin_session_id
    
    session_id = session.get('session_id')
    data = data or {}
    raw_name = data.get('name')
    provided_name = raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else None
    player_name = provided_name  # may remain None (auto-alias for new players)
    
    # Check if player name matches admin code
    required_admin_code = os.getenv('ADMIN_CODE', '').strip()
    is_admin_code = bool(required_admin_code and player_name == required_admin_code)
    
    # Display name for admin (obscure the code)
    display_name = 'Gamemaster' if is_admin_code else player_name

    # Check if player already exists (reconnection)
    if session_id in players:
        player = players[session_id]
        ensure_survey_fields(player)
        player['socket_id'] = request.sid  # Update socket_id on reconnection
        
        # If reconnecting with admin code, check if we should become/remain admin
        if is_admin_code and required_admin_code:
            # Check if current admin is disconnected (no socket_id)
            current_admin_disconnected = (admin_session_id is not None and 
                                        admin_session_id in players and 
                                        players[admin_session_id].get('socket_id') is None)
            
            if admin_session_id is None or current_admin_disconnected:
                # No admin exists or old admin is disconnected - become admin
                if admin_session_id is not None and current_admin_disconnected:
                    # Remove admin status from old admin
                    old_admin = players[admin_session_id]
                    old_admin['is_admin'] = False
                    print(f"Admin {old_admin.get('display_name', old_admin['name'])} disconnected, transferring admin to {player_name}")
                admin_session_id = session_id
                player['is_admin'] = True
                player['name'] = player_name  # Store actual name (code)
                player['display_name'] = 'Gamemaster'  # Always show as Gamemaster
                print(f"Player {player_name} reconnected as ADMIN (code verified)")
            elif player['is_admin'] and session_id == admin_session_id:
                # Admin reconnecting with admin code - ensure display_name is correct
                player['name'] = player_name  # Update internal name (code)
                player['display_name'] = 'Gamemaster'  # Always show as Gamemaster
        elif provided_name:
            # Update name only if a name was explicitly provided (UI join uses no name)
            if player['is_admin']:
                # Already admin - keep display_name as Gamemaster
                player['name'] = provided_name  # Update internal name (code) if changed
                player['display_name'] = 'Gamemaster'  # Always show as Gamemaster
            else:
                player['name'] = provided_name
                player['display_name'] = provided_name
        
        # Send reconnection update to admin
        notify_admin_player_list()

        # If game is in progress, restore player's game state
        if game_state['status'] != 'lobby':
            if player['is_admin']:
                # Admin reconnection - send admin view
                if game_state['status'] == 'playing':
                    socketio.emit('admin_game_started', {
                        'round': game_state['current_round'],
                        'target': game_state['current_target'],
                        'game_id': game_state.get('game_id'),
                        'players': [{
                            'name': p.get('display_name', p['name']),
                            'condition': p['condition'],
                            'is_connected': p.get('socket_id') is not None,
                            'session_id': p['session_id'],
                            'seat_number': admin_seat_number_for_payload(p),
                            'prompts_submitted': len(p['images'].get(game_state['current_round'], []))
                        } for p in players.values() if not p['is_admin']]
                    }, room=player['socket_id'])
                elif game_state['status'] == 'onboarding':
                    ob_phase = game_state.get('onboarding_phase', 'prompting')
                    _adm_ob = {
                        'target': game_state.get('onboarding_target'),
                        'onboarding_phase': ob_phase,
                        'players': [{
                            'name': p.get('display_name', p['name']),
                            'condition': p['condition'],
                            'is_connected': p.get('socket_id') is not None,
                            'session_id': p['session_id'],
                            'seat_number': admin_seat_number_for_payload(p),
                            'prompts_submitted': len(p.get('onboarding_images', [])),
                            'practice_vote_submitted': bool(p.get('onboarding_practice_submitted')) if ob_phase == 'practice_voting' else None,
                        } for p in players.values() if not p['is_admin']],
                    }
                    if ob_phase == 'prompting' and game_state.get('onboarding_prompting_end_time'):
                        _adm_ob['end_time'] = game_state['onboarding_prompting_end_time']
                    socketio.emit('admin_onboarding_started', _adm_ob, room=player['socket_id'])
                    if ob_phase == 'practice_voting':
                        socketio.emit(
                            'admin_onboarding_practice_voting',
                            {
                                'phase': 'practice_voting',
                                'target': game_state.get('onboarding_target') or {'id': 0, 'url': '/static/images/onboarding-target.png'},
                            },
                            room=player['socket_id'],
                        )
                elif game_state['status'] == 'awaiting_next_prompting':
                    socketio.emit(
                        'admin_awaiting_next_prompting',
                        {
                            'current_round': game_state['current_round'],
                            'game_status': 'awaiting_next_prompting',
                        },
                        room=player['socket_id'],
                    )
                elif game_state['status'] == 'awaiting_voting_start':
                    socketio.emit(
                        'admin_awaiting_voting_start',
                        {
                            'current_round': game_state['current_round'],
                            'game_status': 'awaiting_voting_start',
                        },
                        room=player['socket_id'],
                    )
                elif game_state['status'] == 'allocation_voting':
                    socketio.emit(
                        'admin_allocation_started',
                        {'allocation_async': True, 'total': TOTAL_VOTING_ROUNDS},
                        room=player['socket_id'],
                    )
                elif game_state['status'] in ['voting', 'voting_images', 'round_results']:
                    # Send current admin status
                    handle_admin_get_status()
            else:
                # Regular player reconnection - restore their game state
                current_round = game_state['current_round']
                if game_state['status'] == 'onboarding':
                    ensure_onboarding_player_fields(player)
                    if game_state.get('onboarding_phase') == 'practice_voting':
                        emit_onboarding_practice_voting_to_player(player, player['socket_id'])
                    else:
                        welcome = get_welcome_message(player, 1)
                        char_payload = {
                            'character': 'Bud',
                            'animation_state': get_bud_animation_state(),
                            'round': 1,
                        }
                        if welcome:
                            char_payload['message'] = welcome
                        _ob_pl = {
                            'target': game_state.get('onboarding_target'),
                            'character': char_payload,
                            'max_prompts': 3,
                        }
                        if game_state.get('onboarding_prompting_end_time'):
                            _ob_pl['end_time'] = game_state['onboarding_prompting_end_time']
                        socketio.emit('onboarding_started', _ob_pl, room=player['socket_id'])
                        for img_data in player.get('onboarding_images', []):
                            image_url = img_data.get('image_url')
                            _ob_idx = player['onboarding_images'].index(img_data)
                            socketio.emit('image_generated', {
                                'image_data': img_data.get('image_data', '') if not image_url else '',
                                'image_url': image_url,
                                'ai_response': img_data.get('ai_response', ''),
                                'prompt': img_data.get('prompt', ''),
                                'image_index': _ob_idx,
                                'prompt_index': img_data.get('prompt_index') or (_ob_idx + 1),
                                'prompt_id': img_data.get('prompt_id'),
                                'error_type': img_data.get('error_type'),
                                'file_size_kb': img_data.get('file_size_kb'),
                                'onboarding': True,
                            }, room=player['socket_id'])
                elif game_state['status'] == 'playing':
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
                    
                    _gs = {
                        'round': current_round,
                        'target': game_state['current_target'],
                        'end_time': game_state['round_end_time'],
                        'character': character_data,
                        'image_context_bullets': player_gets_image_context_bullets(player),
                    }
                    _gs.update(game_started_aggregate_heuristic_fields(player))
                    socketio.emit('game_started', _gs, room=player['socket_id'])
                    # Restore their generated images
                    if player['images'].get(current_round):
                        for img_data in player['images'][current_round]:
                            # Prefer image_url over image_data to reduce memory usage
                            image_url = img_data.get('image_url')
                            if not image_url and img_data.get('prompt_id') and db.is_configured():
                                # Try to fetch from database if not in memory
                                try:
                                    result = db.supabase.table('prompts').select('image_url').eq('prompt_id', img_data.get('prompt_id')).execute()
                                    if result.data and result.data[0].get('image_url'):
                                        image_url = result.data[0]['image_url']
                                except Exception as e:
                                    print(f"[RECONNECT] Could not fetch image_url from database for prompt_id {img_data.get('prompt_id')}: {e}")
                            
                            _snap_r = img_data.get('heuristic_snapshot')
                            socketio.emit('image_generated', {
                                'image_data': img_data.get('image_data', '') if not image_url else '',  # Only send base64 if no URL
                                'image_url': image_url,  # Prefer URL over base64
                                'ai_response': img_data.get('ai_response', ''),
                                'prompt': img_data.get('prompt', ''),
                                'image_index': player['images'][current_round].index(img_data),
                                'prompt_index': img_data.get('prompt_index'),
                                'prompt_id': img_data.get('prompt_id'),
                                'error_type': img_data.get('error_type'),  # Include error info for filtering
                                'file_size_kb': img_data.get('file_size_kb'),
                                'show_prompting_heuristics': heur_mod.show_prompting_heuristics(player.get('condition')),
                                'per_image_heuristic_display': (
                                    heur_mod.format_snapshot_for_ui(_snap_r) if _snap_r else []
                                ),
                                'aggregate_heuristic_display': [],
                            }, room=player['socket_id'])
                elif game_state['status'] in ['playing', 'voting']:
                    # Restore their generated images for both playing and voting states
                    # This ensures reconnected players get their images restored properly
                    if player['images'].get(current_round):
                        restored_count = 0
                        for img_data in player['images'][current_round]:
                            # Only restore images that have valid data (not just placeholders)
                            if img_data.get('image_data') or img_data.get('prompt_id'):
                                # Prefer image_url over image_data to reduce memory usage
                                image_url = img_data.get('image_url')
                                if not image_url and img_data.get('prompt_id') and db.is_configured():
                                    # Try to fetch from database if not in memory
                                    try:
                                        result = db.supabase.table('prompts').select('image_url').eq('prompt_id', img_data.get('prompt_id')).execute()
                                        if result.data and result.data[0].get('image_url'):
                                            image_url = result.data[0]['image_url']
                                    except Exception as e:
                                        print(f"[RECONNECT] Could not fetch image_url from database for prompt_id {img_data.get('prompt_id')}: {e}")
                                
                                _snap_v = img_data.get('heuristic_snapshot')
                                socketio.emit('image_generated', {
                                    'image_data': img_data.get('image_data', '') if not image_url else '',  # Only send base64 if no URL
                                    'image_url': image_url,  # Prefer URL over base64
                                    'ai_response': img_data.get('ai_response', ''),
                                    'prompt': img_data.get('prompt', ''),
                                    'image_index': player['images'][current_round].index(img_data),
                                    'prompt_index': img_data.get('prompt_index'),
                                    'prompt_id': img_data.get('prompt_id'),
                                    'error_type': img_data.get('error_type'),  # Include error info for filtering
                                    'file_size_kb': img_data.get('file_size_kb'),
                                    'show_prompting_heuristics': heur_mod.show_prompting_heuristics(player.get('condition')),
                                    'per_image_heuristic_display': (
                                        heur_mod.format_snapshot_for_ui(_snap_v) if _snap_v else []
                                    ),
                                    'aggregate_heuristic_display': [],
                                }, room=player['socket_id'])
                                restored_count += 1
                        print(f"[RECONNECT] Restored {restored_count} images for player {player.get('display_name', player['name'])} in round {current_round} (status: {game_state['status']})")
                    
                    # If in voting state, also send voting_started event
                    if game_state['status'] == 'voting':
                        # Include synchronized start time for timer synchronization
                        selection_start_time = game_state.get('voting_start_time', time.time())
                        socketio.emit('voting_started', {
                            'round': current_round,
                            'duration': game_state.get('voting_duration', 30),
                            'start_time': selection_start_time,  # Synchronized start time
                            'default_selected': current_round in player['selected_images'],
                            'image_context_bullets': player_gets_image_context_bullets(player),
                        }, room=player['socket_id'])
                elif game_state['status'] == 'awaiting_next_prompting':
                    socketio.emit(
                        'show_transition_screen',
                        {
                            'message': NEXT_ROUND_SOON_MESSAGE,
                            'wait_for_admin': True,
                        },
                        room=player['socket_id'],
                    )
                elif game_state['status'] == 'awaiting_voting_start':
                    socketio.emit(
                        'show_transition_screen',
                        {
                            'message': READY_TO_VOTE_MESSAGE,
                            'wait_for_admin': True,
                        },
                        room=player['socket_id'],
                    )
                elif game_state['status'] == 'allocation_voting':
                    cached = player.get('allocation_last_payload')
                    if cached and player.get('socket_id'):
                        socketio.emit('allocation_vote_started', cached, room=player['socket_id'])
                elif game_state['status'] == 'voting_images':
                    # Send voting screen
                    selected_images = []
                    for s_id, p in players.items():
                        if not p['is_admin'] and current_round in p['selected_images']:
                            selected_image = p['selected_images'][current_round]
                            prompt_id = selected_image.get('prompt_id')
                            
                            # Prefer image_url, fallback to image_data if URL not available
                            image_url = selected_image.get('image_url')
                            if not image_url and prompt_id and db.is_configured():
                                # Try to fetch from database if not in memory
                                try:
                                    result = db.supabase.table('prompts').select('image_url').eq('prompt_id', prompt_id).execute()
                                    if result.data and result.data[0].get('image_url'):
                                        image_url = result.data[0]['image_url']
                                except Exception as e:
                                    print(f"[RECONNECT] Could not fetch image_url from database for prompt_id {prompt_id}: {e}")
                            
                            # Use URL if available, otherwise fallback to base64
                            image_data = image_url if image_url else selected_image.get('image_data', '')
                            
                            selected_images.append({
                                'session_id': s_id,
                                'player_name': p.get('display_name', p['name']),
                                'image': {
                                    'image_url': image_url,
                                    'image_data': selected_image.get('image_data', '') if not image_url else '',
                                    'has_url': bool(image_url)
                                },
                                'prompt_id': prompt_id
                            })
                    target_image = game_state.get('current_target', {})
                    socketio.emit('vote_on_images', {
                        'images': selected_images,
                        'round': current_round,
                        'my_session_id': session_id,
                        'target_image': {'url': target_image.get('url', '')},
                        'image_context_bullets': player_gets_image_context_bullets(player),
                    }, room=player['socket_id'])
                elif game_state['status'] == 'round_results':
                    # Show round results - this will broadcast to all connected players
                    # Don't call show_round_results() here as it will be called when admin advances
                    # Just send the current results to this reconnecting player
                    current_round = game_state['current_round']
                    results = []
                    for s_id, p in players.items():
                        if not p['is_admin']:
                            votes = p['votes_received'].get(current_round, 0)
                            # Use image_url with fallback to image_data
                            selected_img = p['selected_images'].get(current_round, {})
                            image_url = selected_img.get('image_url')
                            if not image_url:
                                prompt_id = selected_img.get('prompt_id')
                                if prompt_id and db.is_configured():
                                    try:
                                        result = db.supabase.table('prompts').select('image_url').eq('prompt_id', prompt_id).execute()
                                        if result.data and result.data[0].get('image_url'):
                                            image_url = result.data[0]['image_url']
                                    except Exception as e:
                                        print(f"[RECONNECT] Could not fetch image_url for round_results: {e}")
                            image_display = image_url if image_url else selected_img.get('image_data', '')
                            results.append({
                                'player_name': p.get('display_name', p['name']),
                                'votes': votes,
                                'total_score': p['score'],
                                'image': image_display
                            })
                    results.sort(key=lambda x: x['votes'], reverse=True)
                    socketio.emit('round_results', {
                        'round': current_round,
                        'results': results
                    }, room=player['socket_id'])
                elif game_state['status'] == 'game_over':
                    # Show game over - send current final results to this reconnecting player
                    final_results = []
                    for s_id, p in players.items():
                        if not p['is_admin']:
                            final_results.append({
                                'player_name': p.get('display_name', p['name']),
                                'total_score': p['score'],
                                'round_scores': p['round_scores'],
                                'condition': p['condition'],
                                'character': p['character'],
                                'prompt_count': p['prompt_count']
                            })
                    final_results.sort(key=lambda x: x['total_score'], reverse=True)
                    socketio.emit('game_over', {
                        'results': final_results
                    }, room=player['socket_id'])

        # Update player_sessions mapping
        player_sessions[request.sid] = session_id

        # Send lobby update if in lobby, otherwise skip (already sent game state above)
        if game_state['status'] == 'lobby':
            lobby_players = [lobby_player_row(p) for p in players.values()]
            if player['is_admin']:
                socketio.emit('admin_joined', admin_joined_payload(), room=player['socket_id'])
            else:
                socketio.emit('game_joined', {
                    'player': game_joined_player_snapshot(player),
                    'game_state': {
                        'status': game_state['status'],
                        'current_round': game_state['current_round'],
                        'current_target': game_state['current_target'],
                        'players_count': len([p for p in players.values() if not p['is_admin']])
                    },
                    'lobby_players': lobby_players
                }, room=player['socket_id'])
                emit_post_survey_if_pending(player)
            socketio.emit('lobby_players_update', {'players': lobby_players})
            notify_admin_player_list()
        elif not player['is_admin']:
            ensure_post_survey_fields(player)
            hydrate_post_survey_from_db(player)
            emit_post_survey_if_pending(player)

        print(f"Player {player.get('display_name', player_name)} reconnected (Admin: {player['is_admin']})")
        return
    else:
        if not is_admin_code and not player_name:
            player_name = get_unique_animal_alias()
            display_name = player_name

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
            # Admin code used but admin already exists - check if old admin is disconnected
            current_admin_disconnected = (admin_session_id in players and 
                                        players[admin_session_id].get('socket_id') is None)
            if current_admin_disconnected:
                # Old admin is disconnected - allow takeover
                old_admin = players[admin_session_id]
                old_admin['is_admin'] = False
                admin_session_id = session_id
                is_new_admin = True
                final_display_name = 'Gamemaster'
                print(f"Admin {old_admin.get('display_name', old_admin['name'])} disconnected, new admin {player_name} taking over")
            else:
                # Admin already exists and is connected
                emit('error', {'message': 'Admin already exists. Please use a different name.'})
                return
        elif admin_session_id is None and not required_admin_code:
            # Fallback: first player becomes admin if no code configured
            admin_session_id = session_id
            is_new_admin = True
            final_display_name = 'Gamemaster'  # Show as Gamemaster even in fallback
            print(f"Player {player_name} joined as ADMIN (first player, no code configured)")

        seat_number = None
        if not is_new_admin:
            seat_raw = data.get('seat_number')
            if seat_raw is None or (isinstance(seat_raw, str) and seat_raw.strip() == ''):
                emit('error', {'message': 'Seat number is required. Use digits only.'})
                return
            seat_str = str(seat_raw).strip()
            if len(seat_str) > 40:
                emit('error', {'message': 'Seat number may be at most 40 digits.'})
                return
            if not seat_str.isdigit():
                emit('error', {'message': 'Seat number must contain digits only.'})
                return
            seat_number = int(seat_str)
        
        # Check if this player exists in the database for the current game (reconnection with lost session)
        # Uses case-insensitive matching
        team = None
        character = None
        restored_player_id = None
        
        if not is_new_admin and game_state.get('game_id') and db.is_configured():
            existing_player = db.get_player_by_name_and_game(player_name, game_state['game_id'])
            if existing_player:
                # Player exists in database - restore their team assignment
                restored_player_id = existing_player.get('player_id')
                team = existing_player.get('condition') or existing_player.get('team')
                character = existing_player.get('character')
                print(f"🔄 Restored player {player_name} from database: team={team}, old_id={restored_player_id}, new_id={session_id}")
                
                # Update database to use new session_id
                db.create_player(
                    game_id=game_state['game_id'],
                    player_id=session_id,
                    player_name=player_name,
                    condition=team,
                    character=character
                )

        player = {
            'session_id': session_id,
            'socket_id': request.sid,
            'name': player_name,  # Internal name (may be admin code)
            'display_name': final_display_name,  # Display name (Gamemaster for admin)
            'condition': team,
            'character': character,
            'score': 0,
            'round_scores': [0, 0, 0],
            'images': {1: [], 2: [], 3: []},  # Round number -> list of generated images
            'selected_images': {},  # Round number -> selected image
            'has_confirmed_selection': {1: False, 2: False, 3: False},  # Track if player has confirmed their selection (not just default)
            'votes_received': {1: 0, 2: 0, 3: 0},
            'has_voted': {1: False, 2: False, 3: False},
            'incentive_points': 0,
            'prompt_count': 0,
            'has_successful_prompt': {1: False, 2: False, 3: False},  # Track if player has had at least one successful prompt per round
            'conversation_history': {1: [], 2: [], 3: []},  # Round number -> conversation
            'current_image': {1: None, 2: None, 3: None},  # Current image for refinement per round
            'image_generation_errors': [],  # Track failed image generations
            'is_admin': is_new_admin,
            'survey_completed': False,
            'survey_proficiency': None,
            'survey_frequency': None,
            'survey_skills_text': None,
            'post_survey_completed': False,
            'seat_number': seat_number,
        }
        players[session_id] = player

    player_sessions[request.sid] = session_id

    # Send updated lobby players to all clients (only if in lobby)
    lobby_players = None
    if game_state['status'] == 'lobby':
        # Use display_name for lobby (obscures admin code)
        lobby_players = [lobby_player_row(p) for p in players.values()]
    
    # Send game state to player
    # Admin gets different view - they don't play
    if player['is_admin']:
        socketio.emit('admin_joined', admin_joined_payload(), room=player['socket_id'])
    else:
        ensure_survey_fields(player)
        ensure_post_survey_fields(player)
        socketio.emit('game_joined', {
            'player': game_joined_player_snapshot(player),
            'game_state': {
                'status': game_state['status'],
                'current_round': game_state['current_round'],
                'current_target': game_state['current_target'],
                'players_count': len([p for p in players.values() if not p['is_admin']])
            },
            'lobby_players': lobby_players if lobby_players else []
        }, room=player['socket_id'])

        if game_state['status'] == 'onboarding':
            ensure_onboarding_player_fields(player)
            if game_state.get('onboarding_phase') == 'practice_voting':
                player['onboarding_practice_points'] = None
                player['onboarding_practice_submitted'] = False
                emit_onboarding_practice_voting_to_player(player, player['socket_id'])
            else:
                welcome = get_welcome_message(player, 1)
                char_payload = {
                    'character': 'Bud',
                    'animation_state': get_bud_animation_state(),
                    'round': 1,
                }
                if welcome:
                    char_payload['message'] = welcome
                socketio.emit('onboarding_started', {
                    'target': game_state.get('onboarding_target'),
                    'character': char_payload,
                    'max_prompts': 3,
                }, room=player['socket_id'])

        hydrate_post_survey_from_db(player)
        emit_post_survey_if_pending(player)

    # Broadcast player list update to all (only if in lobby)
    if game_state['status'] == 'lobby' and lobby_players is not None:
        print(f"[LOBBY] Broadcasting lobby_players_update to all clients: {len(lobby_players)} players")
        socketio.emit('lobby_players_update', {'players': lobby_players})
        notify_admin_player_list()
    elif game_state['status'] == 'onboarding':
        # No public lobby broadcast during onboarding; still sync Gamemaster dashboard
        notify_admin_player_list()


@socketio.on('submit_pre_survey')
def handle_submit_pre_survey(data):
    """Non-admin lobby players submit the three-question pre-survey once."""
    session_id = session.get('session_id')
    if not session_id or session_id not in players:
        emit('error', {'message': 'Not in game'})
        return
    player = players[session_id]
    ensure_survey_fields(player)
    if player.get('is_admin'):
        emit('error', {'message': 'Gamemaster does not complete this survey'})
        return
    if game_state['status'] != 'lobby':
        emit('error', {'message': 'Survey is only available in the lobby'})
        return
    if player.get('survey_completed'):
        emit('error', {'message': 'Survey already submitted'})
        return
    data = data or {}
    prof = data.get('proficiency')
    freq = data.get('frequency')
    skills = (data.get('skills_text') or '').strip()
    if prof not in VALID_SURVEY_PROFICIENCY or freq not in VALID_SURVEY_FREQUENCY:
        emit('error', {'message': 'Please answer all multiple-choice questions'})
        return
    if len(skills) < 1:
        emit('error', {'message': 'Please enter an answer for the open-ended question'})
        return
    if len(skills) > SURVEY_SKILLS_MAX_LEN:
        emit('error', {'message': f'Answer is too long (max {SURVEY_SKILLS_MAX_LEN} characters)'})
        return
    player['survey_completed'] = True
    player['survey_proficiency'] = prof
    player['survey_frequency'] = freq
    player['survey_skills_text'] = skills
    if db.is_configured():
        gid = game_state.get('game_id')
        db.upsert_experiment_pre_survey(session_id, prof, freq, skills, game_id=gid)
        if gid:
            db.update_player_pre_survey(gid, session_id, prof, freq, skills)
        else:
            db.save_pre_survey_pending(session_id, prof, freq, skills)
    emit('survey_submitted', {'success': True})
    lobby_players = [lobby_player_row(p) for p in players.values()]
    socketio.emit('lobby_players_update', {'players': lobby_players})
    notify_admin_player_list()


def _likert_label(slug: str) -> str:
    return {
        'strongly_disagree': 'Strongly Disagree',
        'disagree': 'Disagree',
        'neutral': 'Neutral',
        'agree': 'Agree',
        'strongly_agree': 'Strongly Agree',
    }.get(slug, slug)


@socketio.on('admin_start_post_survey')
def handle_admin_start_post_survey():
    """Deprecated: post-game survey now opens automatically after voting."""
    session_id = session.get('session_id')
    if session_id != admin_session_id:
        emit('error', {'message': 'Only the Gamemaster can use this action'})
        return
    emit('error', {'message': 'Post-game survey opens automatically after voting completes.'})


@socketio.on('submit_post_game_survey')
def handle_submit_post_game_survey(data):
    """Non-admin: required post-game survey fields, persisted to Supabase."""
    session_id = session.get('session_id')
    if not session_id or session_id not in players:
        emit('error', {'message': 'Not in game'})
        return
    player = players[session_id]
    ensure_post_survey_fields(player)
    if player.get('is_admin'):
        emit('error', {'message': 'Gamemaster does not complete this survey'})
        return
    if not game_state.get('post_survey_active'):
        emit('error', {'message': 'Post-game survey is not open yet'})
        return
    if player.get('post_survey_completed'):
        emit('error', {'message': 'Survey already submitted'})
        return
    gid = game_state.get('game_id')
    if not gid:
        emit('error', {'message': 'No game session in progress'})
        return
    data = data or {}
    fq = [(data.get(f'free_q{i}') or '').strip() for i in range(1, 5)]
    for i, text in enumerate(fq, start=1):
        if len(text) < 1:
            emit('error', {'message': f'Please answer question {i}'})
            return
        if len(text) > POST_SURVEY_TEXT_MAX_LEN:
            emit('error', {'message': f'Answer {i} is too long (max {POST_SURVEY_TEXT_MAX_LEN} characters)'})
            return
    l1 = data.get('likert_best_work')
    l2 = data.get('likert_effort')
    if l1 not in VALID_POST_SURVEY_LIKERT or l2 not in VALID_POST_SURVEY_LIKERT:
        emit('error', {'message': 'Please select an answer for both rating questions'})
        return
    extended, extended_err = parse_post_survey_extended(data)
    if extended_err:
        emit('error', {'message': extended_err})
        return
    extended['behavior_snapshot'] = build_post_survey_behavior_snapshot(player)
    if db.is_configured():
        ok = db.update_player_post_survey(
            gid,
            session_id,
            fq[0],
            fq[1],
            fq[2],
            fq[3],
            _likert_label(l1),
            _likert_label(l2),
            extended,
        )
        if not ok:
            emit('error', {'message': 'Could not save survey. Try again.'})
            return
    else:
        print('⚠️ Post-game survey accepted in memory only (Supabase not configured)')
    player['post_survey_completed'] = True
    emit('post_game_survey_saved', {'success': True, 'game_over': game_state.get('last_game_over_payload')})
    notify_admin_player_list()


@socketio.on('admin_login')
def handle_admin_login(data):
    """Allow a user to become admin by entering the admin code (and join lobby as Gamemaster if needed)."""
    global admin_session_id

    session_id = session.get('session_id')
    if not session_id:
        emit('error', {'message': 'Session not initialized. Please refresh and try again.'})
        return

    required_admin_code = os.getenv('ADMIN_CODE', '').strip()
    entered_code = (data or {}).get('code', '').strip()

    if not required_admin_code:
        emit('error', {'message': 'Admin password is not configured for this game.'})
        return

    # Allow admin login from any game phase so a stuck session can recover (ADMIN_CODE still required).
    # If an admin already exists, disconnect them (remove from game) rather than demote to player.
    old_admin_socket = None
    if admin_session_id in players:
        old_admin = players[admin_session_id]
        old_admin_socket = old_admin.get('socket_id')
        del players[admin_session_id]
        if old_admin_socket and old_admin_socket in player_sessions:
            del player_sessions[old_admin_socket]
        admin_session_id = None

    if entered_code != required_admin_code:
        emit('error', {'message': 'Incorrect admin password.'})
        return

    # Ensure this session has a player in the lobby; create one if needed
    player = players.get(session_id)
    if not player:
        player = {
            'session_id': session_id,
            'socket_id': request.sid,
            'name': required_admin_code,  # Internal name (code)
            'display_name': 'Gamemaster',
            'condition': None,
            'character': None,
            'score': 0,
            'round_scores': [0, 0, 0],
            'images': {1: [], 2: [], 3: []},
            'selected_images': {},
            'has_confirmed_selection': {1: False, 2: False, 3: False},
            'votes_received': {1: 0, 2: 0, 3: 0},
            'has_voted': {1: False, 2: False, 3: False},
            'incentive_points': 0,
            'prompt_count': 0,
            'has_successful_prompt': {1: False, 2: False, 3: False},
            'conversation_history': {1: [], 2: [], 3: []},
            'current_image': {1: None, 2: None, 3: None},
            'image_generation_errors': [],
            'is_admin': True,
            'survey_completed': False,
            'survey_proficiency': None,
            'survey_frequency': None,
            'survey_skills_text': None,
            'post_survey_completed': False,
            'seat_number': None,
        }
        players[session_id] = player
    else:
        # Promote existing lobby player to admin
        player['is_admin'] = True
        player['display_name'] = 'Gamemaster'
        player['socket_id'] = request.sid
        player['seat_number'] = None

    admin_session_id = session_id

    print(f"Player {player.get('name')} became ADMIN via footer login")

    # Send admin view to this player
    socketio.emit('admin_joined', admin_joined_payload(), room=player['socket_id'])

    # Update lobby players for everyone (use display_name to hide code)
    lobby_players = [lobby_player_row(p) for p in players.values()]
    socketio.emit('lobby_players_update', {'players': lobby_players})

    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        admin_socket_id = players[admin_session_id]['socket_id']
        print(f"[LOBBY] Sending player_status_update to admin (socket_id: {admin_socket_id}): {len(players)} total players")
    notify_admin_player_list()

    # If there was a previous connected admin, notify them they were replaced and are disconnected from the game
    if old_admin_socket and old_admin_socket != player['socket_id']:
        socketio.emit('admin_replaced', {'message': 'You were replaced as Gamemaster. Please rejoin the game.'}, room=old_admin_socket)

@socketio.on('assign_teams')
def handle_assign_teams():
    session_id = session.get('session_id')
    
    # Check if player is admin
    if session_id != admin_session_id:
        emit('error', {'message': 'Only admin can assign teams'})
        return

    if game_state['status'] == 'onboarding':
        emit('error', {'message': 'Cannot assign groups during onboarding. Start the game first.'})
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
            player['condition'] = None
            player['character'] = None
    
    # Shuffle connected players for random assignment, then split into four balanced groups
    random.shuffle(connected_players)
    group_chunks = split_into_player_groups(connected_players)
    group_sizes = []
    for group_label, members in group_chunks:
        group_sizes.append(len(members))
        for player in members:
            player['condition'] = group_label
            player['character'] = get_character(group_label)
    
    # Update players in database if game has started
    if game_state.get('game_id') and db.is_configured():
        # Update all players (including disconnected ones - they keep their team assignment if they had one)
        for player in players.values():
            if not player['is_admin']:
                db.create_player(
                    game_id=game_state['game_id'],
                    player_id=player['session_id'],
                    player_name=player['name'],
                    condition=player['condition'],
                    character=player['character']
                )
    
    # Broadcast updated lobby players
    lobby_players = [lobby_player_row(p, use_socket_id_key=True) for p in players.values()]
    socketio.emit('lobby_players_update', {'players': lobby_players})
    
    # Update admin dashboard to show new team assignments
    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        player_list = [admin_player_status_row_with_round(p) for p in players.values()]
        print(f"[ASSIGN TEAMS] Sending player_status_update to admin with teams: {[(p['name'], p['condition']) for p in player_list if not p['is_admin']]}")
        notify_admin_player_list()
        # Also update admin status if game is in progress
        if game_state['status'] != 'lobby':
            handle_admin_get_status()
    
    print(f"Groups assigned by admin: {dict(zip(PLAYER_GROUPS, group_sizes))}")

@socketio.on('start_game')
def handle_start_game():
    session_id = session.get('session_id')
    
    # Check if player is admin
    if session_id != admin_session_id:
        emit('error', {'message': 'Only admin can start the game'})
        return
    
    # Get non-admin players only
    non_admin_players = [p for p in players.values() if not p['is_admin']]
    
    if game_state['status'] in ('lobby', 'onboarding') and len(non_admin_players) >= 1:
        # Make sure teams are assigned
        players_without_teams = [p for p in non_admin_players if p['condition'] is None]
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
                        condition=player['condition'],
                        character=player['character']
                    )
        
        game_state['status'] = 'playing'
        game_state['onboarding_phase'] = 'prompting'
        game_state['onboarding_prompting_end_time'] = None
        game_state['post_survey_active'] = False
        game_state['last_game_over_payload'] = None
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
                p['onboarding_images'] = []
                p['onboarding_conversation'] = []
                p['onboarding_current_image'] = None
                p['onboarding_prompt_count'] = 0
                p['onboarding_has_successful'] = False
                p['onboarding_practice_points'] = None
                p['onboarding_practice_submitted'] = False
                p['post_survey_completed'] = False
                print(f"[DEBUG] Reset current_image, prompt_count, and has_successful_prompt for player {p['name']}, round 1")

        # Send game started to players only (not admin) - must check socket_id, None defaults to current request context
        for p in players.values():
            if not p['is_admin']:
                socket_id = p.get('socket_id')
                if socket_id:  # Only send if player is connected
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
                    
                    # Add welcome message for round start
                    welcome_message = get_welcome_message(p, 1)
                    if welcome_message:
                        character_data['message'] = welcome_message

                    _gs = {
                        'round': 1,
                        'target': game_state['current_target'],
                        'end_time': game_state['round_end_time'],
                        'character': character_data,
                        'image_context_bullets': player_gets_image_context_bullets(p),
                    }
                    _gs.update(game_started_aggregate_heuristic_fields(p))
                    socketio.emit('game_started', _gs, room=socket_id)
        
        # Send admin game started event with player status
        if admin_session_id in players and players[admin_session_id].get('socket_id'):
            time_remaining = game_state['round_end_time'] - time.time() if game_state.get('round_end_time') else None
            socketio.emit('admin_game_started', {
                'round': 1,
                'target': game_state['current_target'],
                'time_remaining': time_remaining,
                'round_end_time': game_state.get('round_end_time'),  # Include end time for client calculation
                'game_id': game_state.get('game_id'),
                'players': [{
                    'name': p.get('display_name', p['name']),
                    'condition': p['condition'],
                    'is_connected': p.get('socket_id') is not None,
                    'session_id': p['session_id'],
                    'seat_number': admin_seat_number_for_payload(p),
                    'prompts_submitted': len(p['images'].get(1, []))
                } for p in players.values() if not p['is_admin']]
            }, room=players[admin_session_id]['socket_id'])

        print("Game started!")
    else:
        if len(non_admin_players) < 1:
            emit('error', {'message': 'Need at least one player to start the game.'})
        else:
            emit('error', {'message': 'Game can only be started from the lobby.'})
        return


@socketio.on('start_onboarding')
def handle_start_onboarding():
    """Gamemaster: practice prompting phase (fixed target, max 3 prompts, 3 min synced timer; no auto-advance)."""
    session_id = session.get('session_id')
    if session_id != admin_session_id:
        emit('error', {'message': 'Only the Gamemaster can start onboarding'})
        return

    if game_state['status'] != 'lobby':
        emit('error', {'message': 'Onboarding can only start from the lobby'})
        return

    non_admin_players = [p for p in players.values() if not p['is_admin']]
    if len(non_admin_players) < 1:
        emit('error', {'message': 'Need at least one player to start onboarding'})
        return

    players_without_teams = [p for p in non_admin_players if p['condition'] is None]
    if players_without_teams:
        emit('error', {'message': 'Please assign groups first'})
        return

    game_state['status'] = 'onboarding'
    game_state['onboarding_phase'] = 'prompting'
    game_state['current_round'] = 0
    game_state['round_start_time'] = None
    game_state['round_end_time'] = None
    _ob_end = time.time() + ONBOARDING_PROMPTING_DURATION_SEC
    game_state['onboarding_prompting_end_time'] = _ob_end
    target = game_state.get('onboarding_target') or {'id': 0, 'url': '/static/images/onboarding-target.png'}

    for p in players.values():
        if p['is_admin']:
            continue
        p['onboarding_images'] = []
        p['onboarding_conversation'] = []
        p['onboarding_current_image'] = None
        p['onboarding_prompt_count'] = 0
        p['onboarding_has_successful'] = False
        p['onboarding_practice_points'] = None
        p['onboarding_practice_submitted'] = False

    for p in players.values():
        if p['is_admin'] or not p.get('socket_id'):
            continue
        welcome = get_welcome_message(p, 1)
        char_payload = {
            'character': 'Bud',
            'animation_state': get_bud_animation_state(),
            'round': 1,
        }
        if welcome:
            char_payload['message'] = welcome
        socketio.emit(
            'onboarding_started',
            {
                'target': target,
                'character': char_payload,
                'max_prompts': 3,
                'end_time': _ob_end,
            },
            room=p['socket_id'],
        )

    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        socketio.emit(
            'admin_onboarding_started',
            {
                'target': target,
                'onboarding_phase': 'prompting',
                'end_time': _ob_end,
                'players': [
                    {
                        'name': p.get('display_name', p['name']),
                        'condition': p['condition'],
                        'is_connected': p.get('socket_id') is not None,
                        'session_id': p['session_id'],
                        'seat_number': admin_seat_number_for_payload(p),
                        'prompts_submitted': len(p.get('onboarding_images', [])),
                    }
                    for p in players.values()
                    if not p['is_admin']
                ],
            },
            room=players[admin_session_id]['socket_id'],
        )

    print('[ONBOARDING] Practice phase started')


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
    
    data = data or {}
    prompt = data.get('prompt', '')
    current_round = game_state['current_round']
    is_onboarding = game_state['status'] == 'onboarding'

    if is_onboarding:
        ensure_onboarding_player_fields(player)
        if game_state.get('onboarding_phase') == 'practice_voting':
            emit('error', {'message': 'Practice voting is in progress — prompts are closed.'})
            return
        if len(player['onboarding_images']) >= 3:
            emit('error', {'message': 'Practice limit reached.'})
            return
    elif game_state['status'] != 'playing':
        emit('error', {'message': 'Game is not in playing state'})
        return

    if not is_onboarding:
        ensure_round_id_for_current_game_if_needed()

    if not is_onboarding:
        buffer_time = 5
        if time.time() > game_state['round_end_time'] + buffer_time:
            emit('error', {'message': 'Round has ended'})
            return

    # Per-player backpressure.
    with _PLAYER_GEN_LOCK:
        inflight_for_player = _PLAYER_GEN_INFLIGHT.get(session_id, 0)
        if inflight_for_player >= _max_inflight_per_player():
            log_metric(
                "prompt.rejected",
                session_id=session_id,
                player_name=player.get("display_name", player.get("name")),
                onboarding=is_onboarding,
                round=1 if is_onboarding else current_round,
                prompt_len=(len(prompt) if isinstance(prompt, str) else None),
                reason="player_inflight_limit",
                inflight_for_player=inflight_for_player,
                max_inflight_for_player=_max_inflight_per_player(),
            )
            emit('error', {'message': 'Please wait for your current image to finish generating.'})
            return
        _PLAYER_GEN_INFLIGHT[session_id] = inflight_for_player + 1

    if is_onboarding:
        player['onboarding_prompt_count'] = player.get('onboarding_prompt_count', 0) + 1
        opc = player['onboarding_prompt_count']
    else:
        player['prompt_count'] += 1
        opc = player['prompt_count']

    # Used for analytics: prompt send time vs image_generated_at gives generation latency.
    prompt_sent_ts = time.time()
    prompt_len = len(prompt) if isinstance(prompt, str) else None
    emit(
        'prompt_sent',
        {
            'prompt': prompt,
            'prompt_index': opc,
            'onboarding': is_onboarding,
        },
    )
    log_metric(
        "prompt.received",
        session_id=session_id,
        player_name=player.get("display_name", player.get("name")),
        onboarding=is_onboarding,
        round=1 if is_onboarding else current_round,
        prompt_index=opc,
        prompt_len=prompt_len,
        game_status=game_state.get("status"),
        game_id=game_state.get("game_id"),
        round_id=game_state.get("round_id"),
    )

    ph_round = 1 if is_onboarding else current_round

    if is_onboarding:
        character_message = onboarding_buddy_progress_message(opc)
        character_data = {
            'character': 'Bud',
            'message': character_message,
            'round': 1,
            'animation_state': get_bud_animation_state(),
        }
    else:
        character = get_character_for_round(player, current_round)
        character_message = get_character_message(player, current_round)
        character_data = {
            'character': character,
            'message': character_message,
            'round': current_round,
        }
        prompt_count = player.get('prompt_count', 0)
        has_successful_prompt = player.get('has_successful_prompt', {}).get(current_round, False)
        if character == 'Bud':
            character_data['animation_state'] = get_bud_animation_state()
        elif character == 'Spud':
            prev_prompt_count = max(0, prompt_count - 1)
            plant_state = get_spud_plant_state(prev_prompt_count, has_successful_prompt)
            character_data['plant_state'] = plant_state
            character_data['animation_state'] = get_spud_animation_state(
                prev_prompt_count, plant_state, is_error=False, has_successful_prompt=has_successful_prompt
            )
            character_data['prompt_count'] = prompt_count

    if is_onboarding:
        emit('character_message', character_data)

    # Global generation concurrency cap.
    sem = _get_gen_semaphore()
    sem.acquire()
    with _GEN_METRICS_LOCK:
        global _GEN_IN_FLIGHT
        _GEN_IN_FLIGHT += 1
        inflight_now = _GEN_IN_FLIGHT

    # Generate image via Gemini when configured, else local placeholder (see use_stub_image_generation).
    try:
        if is_onboarding:
            conversation = player['onboarding_conversation']
            current_image_obj = player.get('onboarding_current_image')
        else:
            conversation = player['conversation_history'][current_round]
            current_image_obj = player['current_image'][current_round]

        skip_api = use_stub_image_generation()
        gen_req_id = f"{session_id[:8]}-{ph_round}-{opc}-{int(prompt_sent_ts * 1000)}"
        log_metric(
            "generation.start",
            gen_req_id=gen_req_id,
            session_id=session_id,
            player_name=player.get("display_name", player.get("name")),
            onboarding=is_onboarding,
            round=ph_round,
            prompt_index=opc,
            prompt_len=prompt_len,
            refinement=bool(current_image_obj),
            skip_api=skip_api,
            inflight_generations=inflight_now,
            rss_mb=_process_rss_mb_best_effort(),
        )

        if skip_api:
            if game_state['status'] not in ['playing', 'transitioning', 'voting', 'onboarding']:
                print(f"[WARNING] Stub image discarded — game status {game_state['status']}")
                return
            if session_id not in players:
                return
            # Stub must work without Supabase: DB writes are gated later; do not return here.
            if not is_onboarding and (not game_state.get('game_id') or not game_state.get('round_id')):
                print('[STUB] No game_id/round_id — emitting in-memory placeholder (DB save skipped)')
            print(f"[STUB] Placeholder for {player['name']}, r{ph_round}, onboarding={is_onboarding}")
            image_data = create_placeholder_image(prompt, ph_round)
            _, b64part = image_data.split(',', 1)
            image_bytes = base64.b64decode(b64part)
            file_size_kb = get_file_size_kb(image_bytes)
            error_type = None
            error_message = None
            finish_reason = None
            safety_ratings = None
            ai_response = (
                'Placeholder image (stub: no GEMINI_API_KEY, or PROMPTCRAFT_STUB_IMAGE_GEN=1).'
            )
            pil_img = Image.open(io.BytesIO(image_bytes))
            if is_onboarding:
                player['onboarding_current_image'] = pil_img
                player['onboarding_has_successful'] = True
            else:
                player['current_image'][current_round] = pil_img
                player['has_successful_prompt'][current_round] = True
        else:
            client = get_google_genai_client()
            print(
                f"[DEBUG] Player: {player['name']}, Session: {session_id[:8]}..., Round: {ph_round}, "
                f"onboarding={is_onboarding}, Has current_image: {current_image_obj is not None}"
            )
        
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
                print(
                    f"[LATENCY] pre-Gemini elapsed {time.time() - prompt_sent_ts:.3f}s since prompt_sent "
                    f"(player={session_id[:8]} round={ph_round} prompt_index={opc})"
                )
                t_api_start = time.time()
                response = client.models.generate_content(
                    model="gemini-2.5-flash-image",
                    contents=contents
                )
                t_api_end = time.time()
                log_metric(
                    "generation.api_done",
                    gen_req_id=gen_req_id,
                    session_id=session_id,
                    onboarding=is_onboarding,
                    round=ph_round,
                    prompt_index=opc,
                    refinement=bool(current_image_obj),
                    api_seconds=round(t_api_end - t_api_start, 3),
                    inflight_generations=inflight_now,
                )
                print(
                    f"[LATENCY] Gemini generate_content took {t_api_end - t_api_start:.2f}s "
                    f"player={session_id[:8]} round={ph_round} prompt_index={opc}"
                )
            
                # Validate game state and player still exist (in case game was restarted during API call)
                # Allow processing during 'playing', 'transitioning', and 'voting' states since:
                # - Prompt was submitted during valid 'playing' state (or buffer period)
                # - Image should still be included in selection gallery even if it arrives late
                # - We're still in the same round (not a new round or game restart)
                if game_state['status'] not in ['playing', 'transitioning', 'voting', 'onboarding']:
                    print(f"[WARNING] API response received but game is in invalid state (status: {game_state['status']}). Discarding response.")
                    return
            
                if session_id not in players:
                    print(f"[WARNING] API response received but player {session_id[:8]}... no longer exists. Discarding response.")
                    return
            
                if not is_onboarding and (not game_state.get('game_id') or not game_state.get('round_id')):
                    print("[WARNING] API response but game_id or round_id is None — emitting image; DB save will be skipped")

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
                                pil_img = Image.open(io.BytesIO(image_bytes))
                                if is_onboarding:
                                    player['onboarding_current_image'] = pil_img
                                    player['onboarding_has_successful'] = True
                                else:
                                    player['current_image'][current_round] = pil_img
                                    player['has_successful_prompt'][current_round] = True
                                print(f"[DEBUG] Stored new image for player {player['name']} (session: {session_id[:8]}...), round {ph_round}, successful prompt")
                            else:
                                if is_onboarding:
                                    player['onboarding_current_image'] = None
                                else:
                                    player['current_image'][current_round] = None
                                print(f"[DEBUG] Not storing image for refinement due to error: {error_type}")
                        
                            break
            
                # Handle cases where no image was returned
                if image_data is None:
                    if not error_type:
                        error_type = 'no_image_in_response'
                        error_message = 'API returned success but no image data'
                    print(f"[ERROR] No image in response for player {player['name']}, error_type: {error_type}")
                    image_data = create_placeholder_image(prompt, ph_round)
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
                
                    cr_msg = 1 if is_onboarding else current_round
                    character_error_message = get_character_error_message(player, cr_msg)
                    character = 'Bud' if is_onboarding else get_character_for_round(player, current_round)

                    character_data = {
                        'character': character,
                        'message': character_error_message,
                        'round': 1 if is_onboarding else current_round,
                    }

                    prompt_count_err = opc if is_onboarding else player.get('prompt_count', 0)
                    has_successful_prompt = (
                        player.get('onboarding_has_successful', False)
                        if is_onboarding
                        else player.get('has_successful_prompt', {}).get(current_round, False)
                    )

                    if character == 'Bud':
                        character_data['animation_state'] = get_bud_animation_state()
                    elif character == 'Spud':
                        plant_state = get_spud_plant_state(prompt_count_err, has_successful_prompt)
                        character_data['plant_state'] = plant_state
                        character_data['animation_state'] = get_spud_animation_state(
                            prompt_count_err, plant_state, is_error=True, has_successful_prompt=has_successful_prompt
                        )
                        character_data['prompt_count'] = prompt_count_err

                    if is_onboarding:
                        socketio.emit('character_message', character_data, room=player['socket_id'])

                    socketio.emit('image_generation_error', {
                        'message': character_error_message,
                        'error_type': error_type,
                        'suggest_retry': True
                    }, room=player['socket_id'])

                    error_entry = {
                        'round': 0 if is_onboarding else current_round,
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

            except Exception as img_error:
                print(f"Image generation error: {img_error}")
                error_type = 'exception'
                error_message = str(img_error)
                error_entry = {
                    'round': 0 if is_onboarding else current_round,
                    'timestamp': time.time(),
                    'error_type': error_type,
                    'prompt': prompt,
                    'error_message': error_message
                }
                player['image_generation_errors'].append(error_entry)
                print(f"[ERROR TRACKING] Player {player['name']}: Exception in round {ph_round}: {img_error}")
                image_data = create_placeholder_image(prompt, ph_round)
                file_size_kb = None
                finish_reason = None
                safety_ratings = None
                ai_response = "Image generation encountered an error. Please try again."

                cr_msg = 1 if is_onboarding else current_round
                character_error_message = get_character_error_message(player, cr_msg)
                character = 'Bud' if is_onboarding else get_character_for_round(player, current_round)

                character_data = {
                    'character': character,
                    'message': character_error_message,
                    'round': 1 if is_onboarding else current_round,
                }

                prompt_count = opc if is_onboarding else player.get('prompt_count', 0)
                has_successful_prompt = (
                    player.get('onboarding_has_successful', False)
                    if is_onboarding
                    else player.get('has_successful_prompt', {}).get(current_round, False)
                )

                if character == 'Bud':
                    character_data['animation_state'] = get_bud_animation_state()
                elif character == 'Spud':
                    plant_state = get_spud_plant_state(prompt_count, has_successful_prompt)
                    character_data['plant_state'] = plant_state
                    character_data['animation_state'] = get_spud_animation_state(
                        prompt_count, plant_state, is_error=True, has_successful_prompt=has_successful_prompt
                    )
                    character_data['prompt_count'] = prompt_count

                if is_onboarding:
                    socketio.emit('character_message', character_data, room=player['socket_id'])
                socketio.emit('image_generation_error', {
                    'message': character_error_message,
                    'error_type': error_type,
                    'suggest_retry': True
                }, room=player['socket_id'])

        # Store conversation
        conversation.append({'role': 'user', 'content': prompt})
        conversation.append({'role': 'assistant', 'content': ai_response})

        if is_onboarding:
            image_bucket = player['onboarding_images']
        else:
            image_bucket = player['images'][current_round]

        # IMPORTANT: prompt_index must reflect SEND order, not completion order.
        # Otherwise, if prompt B returns before prompt A, the UI placeholders can be filled in swapped order.
        prompt_index = int(opc)

        # Timestamp heuristic should reflect when the player submitted the prompt (not when the image returned).
        prompt_elapsed = 0
        if not is_onboarding:
            rs = game_state.get('round_start_time')
            if rs:
                prompt_elapsed = int(max(0, min(300, prompt_sent_ts - rs)))

        image_entry = {
            'prompt': prompt,
            'image_data': image_data,
            'timestamp': time.time(),
            'ai_response': ai_response,
            'prompt_id': None,
            'prompt_index': prompt_index,
            'error_type': error_type,
            'file_size_kb': file_size_kb,
            'prompt_sent_elapsed_seconds': prompt_elapsed,
        }
        image_bucket.append(image_entry)

        snap = None
        agg = None
        if not is_onboarding:
            # Per-image word count = cumulative words in this round (same as aggregate "Total words" at that moment)
            cumulative_wc_line = heur_mod.show_prompting_heuristics(player.get('condition'))
            snap = heur_mod.snapshot_for_image_entry(
                prompt_index=prompt_index,
                prompt_text=prompt,
                images_before_and_including=image_bucket,
                prompt_elapsed_seconds=prompt_elapsed,
                cumulative_word_count_for_prompt_line=cumulative_wc_line,
            )
            image_entry['heuristic_snapshot'] = snap
            valid_for_agg = [im for im in image_bucket if not im.get('error_type')]
            tw = sum(heur_mod.word_count(im.get('prompt', '')) for im in valid_for_agg)
            agg = heur_mod.aggregate_snapshot_for_round(
                total_prompts=len(valid_for_agg),
                total_words=tw,
            )

        # Emit image to client immediately so UI is not blocked on Supabase insert/upload.
        # When DB is used, prompt_id is filled in a background task and sent via `image_prompt_binding`.
        ig_payload = {
            'image_data': image_data,
            'image_url': image_entry.get('image_url'),
            'ai_response': ai_response,
            'prompt': prompt,
            # Keep for backward compatibility; selection routing now prefers prompt_id/prompt_index.
            'image_index': max(0, prompt_index - 1),
            'prompt_index': prompt_index,
            'prompt_id': image_entry.get('prompt_id'),
            'error_type': error_type,
            'file_size_kb': file_size_kb,
            'onboarding': is_onboarding,
        }
        if not is_onboarding:
            ig_payload['show_prompting_heuristics'] = heur_mod.show_prompting_heuristics(player.get('condition'))
            ig_payload['per_image_heuristic_display'] = (
                heur_mod.format_snapshot_for_ui(snap) if snap else []
            )
            ig_payload['aggregate_heuristic_display'] = (
                heur_mod.format_aggregate_for_ui(agg) if agg else []
            )
        socketio.emit('image_generated', ig_payload, room=player['socket_id'])

        if not is_onboarding and db.is_configured() and game_state.get('game_id') and game_state.get('round_id'):
            submitted_at = datetime.fromtimestamp(prompt_sent_ts)
            image_generated_at = datetime.fromtimestamp(time.time())
            wc = heur_mod.word_count(prompt)
            gid = game_state['game_id']
            rid = game_state['round_id']
            img_data_for_upload = image_data
            player_name_for_upload = player['name']

            def _persist_prompt_row_async():
                try:
                    prompt_id_local = db.save_prompt_sync(
                        game_id=gid,
                        round_id=rid,
                        player_id=session_id,
                        prompt_index=prompt_index,
                        prompt_text=prompt,
                        image_url=None,
                        ai_response=ai_response,
                        submitted_at=submitted_at,
                        image_generated_at=image_generated_at,
                        error_type=error_type,
                        error_message=error_message,
                        finish_reason=finish_reason,
                        file_size_kb=file_size_kb,
                        safety_ratings=safety_ratings,
                        word_count=wc,
                        prompt_sent_elapsed_seconds=prompt_elapsed,
                    )
                    if session_id not in players:
                        return
                    pl = players[session_id]
                    if prompt_id_local:
                        image_entry['prompt_id'] = prompt_id_local
                        if os.getenv("PROMPTCRAFT_DROP_BASE64_AFTER_EMIT", "1") == "1":
                            image_entry.pop("image_data", None)

                        def clear_base64_after_upload(image_url, uploaded_prompt_id):
                            if session_id not in players:
                                return
                            pobj = players[session_id]
                            for img_ent in pobj['images'].get(current_round, []):
                                if img_ent.get('prompt_id') == uploaded_prompt_id:
                                    img_ent['image_url'] = image_url
                                    print(
                                        f"[MEMORY] Cleared base64 data for prompt_id {uploaded_prompt_id}, using URL: {image_url[:50]}..."
                                    )
                                    if pobj.get('socket_id'):
                                        socketio.emit(
                                            'image_url_updated',
                                            {'prompt_id': uploaded_prompt_id, 'image_url': image_url},
                                            room=pobj['socket_id'],
                                        )
                                    break

                        db.upload_image_async(
                            image_data=img_data_for_upload,
                            game_id=gid,
                            player_id=session_id,
                            round_id=rid,
                            prompt_id=prompt_id_local,
                            prompt_index=prompt_index,
                            player_name=player_name_for_upload,
                            round_number=current_round,
                            callback=clear_base64_after_upload,
                        )
                    else:
                        game_state['_synthetic_prompt_seq'] = game_state.get('_synthetic_prompt_seq', 0) + 1
                        image_entry['prompt_id'] = -game_state['_synthetic_prompt_seq']
                        print(
                            f"[WARN] Assigned synthetic prompt_id={image_entry['prompt_id']} "
                            "(no prompts row — check SUPABASE_URL / SUPABASE_KEY, round_id, and DB errors)"
                        )
                    sock = pl.get('socket_id')
                    if sock and image_entry.get('prompt_id') is not None:
                        socketio.emit(
                            'image_prompt_binding',
                            {
                                'prompt_index': prompt_index,
                                'prompt_id': image_entry['prompt_id'],
                            },
                            room=sock,
                        )
                except Exception as ex:
                    print(f"❌ Error in async prompt persist: {ex}")
                    if session_id in players and image_entry.get('prompt_id') is None:
                        game_state['_synthetic_prompt_seq'] = game_state.get('_synthetic_prompt_seq', 0) + 1
                        image_entry['prompt_id'] = -game_state['_synthetic_prompt_seq']
                        pl2 = players[session_id]
                        if pl2.get('socket_id'):
                            socketio.emit(
                                'image_prompt_binding',
                                {
                                    'prompt_index': prompt_index,
                                    'prompt_id': image_entry['prompt_id'],
                                },
                                room=pl2['socket_id'],
                            )

            socketio.start_background_task(_persist_prompt_row_async)
        elif not is_onboarding and not image_entry.get('prompt_id'):
            game_state['_synthetic_prompt_seq'] = game_state.get('_synthetic_prompt_seq', 0) + 1
            image_entry['prompt_id'] = -game_state['_synthetic_prompt_seq']
            print(
                f"[WARN] Assigned synthetic prompt_id={image_entry['prompt_id']} "
                "(no prompts row — check SUPABASE_URL / SUPABASE_KEY, round_id, and DB errors)"
            )
            socketio.emit(
                'image_prompt_binding',
                {
                    'prompt_index': prompt_index,
                    'prompt_id': image_entry['prompt_id'],
                },
                room=player['socket_id'],
            )

        if admin_session_id in players and players[admin_session_id].get('socket_id'):
            socketio.emit('player_prompt_updated', {
                'session_id': session_id,
                'player_name': player.get('display_name', player['name']),
                'prompts_submitted': len(image_bucket),
            }, room=players[admin_session_id]['socket_id'])

    except Exception as e:
        print(f"Error generating image: {e}")
        error_type = 'outer_exception'
        error_message = str(e)
        error_entry = {
            'round': 0 if is_onboarding else current_round,
            'timestamp': time.time(),
            'error_type': error_type,
            'prompt': prompt,
            'error_message': error_message
        }
        player['image_generation_errors'].append(error_entry)
        print(f"[ERROR TRACKING] Player {player['name']}: Outer exception in round {ph_round}: {e}")

        cr_msg = 1 if is_onboarding else current_round
        character_error_message = get_character_error_message(player, cr_msg)
        character = 'Bud' if is_onboarding else get_character_for_round(player, current_round)

        character_data = {
            'character': character,
            'message': character_error_message,
            'round': 1 if is_onboarding else current_round,
        }

        prompt_count = opc if is_onboarding else player.get('prompt_count', 0)
        has_successful_prompt = (
            player.get('onboarding_has_successful', False)
            if is_onboarding
            else player.get('has_successful_prompt', {}).get(current_round, False)
        )

        if character == 'Bud':
            character_data['animation_state'] = get_bud_animation_state()
        elif character == 'Spud':
            plant_state = get_spud_plant_state(prompt_count, has_successful_prompt)
            character_data['plant_state'] = plant_state
            character_data['animation_state'] = get_spud_animation_state(
                prompt_count, plant_state, is_error=True, has_successful_prompt=has_successful_prompt
            )
            character_data['prompt_count'] = prompt_count

        if is_onboarding:
            socketio.emit('character_message', character_data, room=player['socket_id'])
        
        # Also emit error for logging/analytics
        socketio.emit('image_generation_error', {
            'message': character_error_message,
            'error_type': error_type,
            'suggest_retry': True
        }, room=player['socket_id'])

    finally:
        try:
            log_metric(
                "generation.done",
                gen_req_id=locals().get("gen_req_id"),
                session_id=session_id,
                player_name=player.get("display_name", player.get("name")),
                onboarding=is_onboarding,
                round=ph_round,
                prompt_index=opc,
                prompt_len=locals().get("prompt_len"),
                refinement=locals().get("current_image_obj") is not None,
                skip_api=locals().get("skip_api"),
                total_seconds=round(time.time() - prompt_sent_ts, 3),
                prompt_to_done_seconds=round(time.time() - prompt_sent_ts, 3),
                error_type=locals().get("error_type"),
                finish_reason=locals().get("finish_reason"),
                file_size_kb=locals().get("file_size_kb"),
                inflight_generations=locals().get("inflight_now"),
                rss_mb=_process_rss_mb_best_effort(),
            )
        except Exception:
            pass
        with _GEN_METRICS_LOCK:
            if _GEN_IN_FLIGHT > 0:
                _GEN_IN_FLIGHT -= 1
        sem.release()
        with _PLAYER_GEN_LOCK:
            _PLAYER_GEN_INFLIGHT[session_id] = max(0, _PLAYER_GEN_INFLIGHT.get(session_id, 1) - 1)

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

def get_welcome_message(player, current_round):
    """
    Get welcome message when player first lands on the round screen.
    Round 1: Bud says "Let's go!"
    Rounds 2 and 3: Bud/Spud says "Back for more? Prompt wisely..."
    """
    if current_round == 1:
        # Round 1: Only Bud says welcome message
        character = get_character_for_round(player, current_round)
        if character == 'Bud':
            return "Let's go!"
    else:
        # Rounds 2 and 3: Both Bud and Spud say welcome message
        return "Back for more? Prompt wisely..."
    
    return None

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

DEFAULT_POINT_SPLIT = (4, 3, 3)  # must sum to 10


def ensure_round_id_for_current_game_if_needed():
    """If Supabase is on and we have a game but no round row, create one for the current round."""
    if not db.is_configured() or not game_state.get('game_id'):
        return
    if game_state.get('round_id'):
        return
    cr = game_state.get('current_round') or 1
    if cr < 1 or cr > 3:
        return
    rid = db.create_round(game_id=game_state['game_id'], round_number=cr)
    if rid:
        game_state['round_id'] = rid
        print(f"[DB] ensure_round_id: created round_id={rid} for round {cr}")


def _next_synthetic_ballot_id():
    game_state['_synthetic_ballot_seq'] += 1
    return game_state['_synthetic_ballot_seq']


def enter_awaiting_next_prompting_after_selection():
    """R1/R2: selection is done; show interstitial until Gamemaster uses Next Round."""
    if game_state['status'] != 'voting':
        return
    if game_state['current_round'] >= 3:
        return
    game_state['status'] = 'awaiting_next_prompting'
    print(f"[SELECTION] Entering awaiting_next_prompting after round {game_state['current_round']} selection")
    for p in players.values():
        if p['is_admin']:
            continue
        sid = p.get('socket_id')
        if not sid:
            continue
        socketio.emit(
            'show_transition_screen',
            {
                'message': NEXT_ROUND_SOON_MESSAGE,
                'wait_for_admin': True,
            },
            room=sid,
        )
    notify_admin_player_list()


def enter_awaiting_voting_start_after_round_three_selection():
    """R3: selection is done; show interstitial until Gamemaster uses Start Voting."""
    if game_state['status'] != 'voting':
        return
    if game_state['current_round'] != 3:
        return
    game_state['status'] = 'awaiting_voting_start'
    print("[SELECTION] Entering awaiting_voting_start after round 3 selection")
    for p in players.values():
        if p['is_admin']:
            continue
        sid = p.get('socket_id')
        if not sid:
            continue
        socketio.emit(
            'show_transition_screen',
            {
                'message': READY_TO_VOTE_MESSAGE,
                'wait_for_admin': True,
            },
            room=sid,
        )
    notify_admin_player_list()


def advance_to_next_prompting_round_after_selection():
    """After selection phase of round 1 or 2, start the next 5-minute prompting round."""
    if game_state['current_round'] >= 3:
        return
    game_state['current_round'] += 1
    game_state['status'] = 'playing'
    game_state['current_target'] = game_state['target_images'][game_state['current_round'] - 1]
    game_state['round_start_time'] = time.time()
    game_state['round_end_time'] = game_state['round_start_time'] + 300
    if db.is_configured() and game_state.get('game_id'):
        round_id = db.create_round(game_id=game_state['game_id'], round_number=game_state['current_round'])
        if round_id:
            game_state['round_id'] = round_id
    round_num = game_state['current_round']
    for p in players.values():
        if not p['is_admin']:
            p['current_image'][round_num] = None
            p['prompt_count'] = 0
            p['has_successful_prompt'][round_num] = False
    for p in players.values():
        if not p['is_admin']:
            sid = p.get('socket_id')
            if not sid:
                continue
            character = get_character_for_round(p, game_state['current_round'])
            character_data = {'character': character, 'round': game_state['current_round']}
            if character == 'Bud':
                character_data['animation_state'] = get_bud_animation_state()
            elif character == 'Spud':
                character_data['plant_state'] = 'base'
                character_data['animation_state'] = 'smiling'
                character_data['prompt_count'] = 0
            welcome_message = get_welcome_message(p, game_state['current_round'])
            if welcome_message:
                character_data['message'] = welcome_message
            _gs = {
                'round': game_state['current_round'],
                'target': game_state['current_target'],
                'end_time': game_state['round_end_time'],
                'character': character_data,
                'image_context_bullets': player_gets_image_context_bullets(p),
            }
            _gs.update(game_started_aggregate_heuristic_fields(p))
            socketio.emit('game_started', _gs, room=sid)
    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        cr = game_state['current_round']
        socketio.emit('admin_game_started', {
            'round': cr,
            'target': game_state['current_target'],
            'time_remaining': game_state['round_end_time'] - time.time(),
            'round_end_time': game_state.get('round_end_time'),
            'game_id': game_state.get('game_id'),
            'players': [{
                'name': x.get('display_name', x['name']),
                'condition': x['condition'],
                'is_connected': x.get('socket_id') is not None,
                'session_id': x['session_id'],
                'seat_number': admin_seat_number_for_payload(x),
                'prompts_submitted': len(x['images'].get(cr, [])),
            } for x in players.values() if not x['is_admin']],
        }, room=players[admin_session_id]['socket_id'])


def start_post_round_three_voting_buffer():
    """Buffer before 10-round point allocation voting."""
    game_state['status'] = 'voting_prep'
    game_state['transition_start_time'] = time.time()
    for p in players.values():
        if not p['is_admin'] and p.get('socket_id'):
            socketio.emit('show_transition_screen', {
                'message': 'Pulling in images for voting...',
                'max_wait': 10,
            }, room=p['socket_id'])
    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        socketio.emit('admin_status_update', {'status': 'voting_prep', 'round': 3}, room=players[admin_session_id]['socket_id'])

    def kickoff():
        time.sleep(5.0)
        if game_state.get('status') == 'voting_prep':
            start_allocation_voting_phase()

    socketio.start_background_task(kickoff)


def _heuristic_snapshot_from_selected(player, prompt_round=3):
    sel = player.get('selected_images', {}).get(prompt_round) or {}
    imgs = player.get('images', {}).get(prompt_round, [])
    prompt_index = sel.get('prompt_index') or 1
    prompt_text = sel.get('prompt') or ''
    elapsed = int(sel.get('prompt_sent_elapsed_seconds') or 0)
    cond_sel = (player.get('condition') or '').strip().upper()
    return heur_mod.snapshot_for_image_entry(
        prompt_index=prompt_index,
        prompt_text=prompt_text,
        images_before_and_including=imgs,
        prompt_elapsed_seconds=elapsed,
        cumulative_word_count_for_prompt_line=cond_sel in ('C_HU', 'T_HU'),
    )


def _allocation_fixture_submit_key_for_ordinal(voter_sid: str, display_ordinal: int) -> Optional[str]:
    """Map display step to DB grouping key: fixture_set_key (1–9) or ALLOCATION_FINAL_SUBMIT_KEY (10)."""
    if display_ordinal == TOTAL_VOTING_ROUNDS:
        return ALLOCATION_FINAL_SUBMIT_KEY
    pl = players.get(voter_sid)
    if not pl:
        return None
    order = pl.get('allocation_fixture_order')
    if not order or len(order) != NUM_HARDCODED_VOTING_ROUNDS:
        return None
    fixture_num = order[display_ordinal - 1]
    fix = get_fixture_rounds()[fixture_num - 1]
    return fix['fixture_set_key']


def _maybe_finalize_shared_allocation_round(submit_key: str) -> None:
    """End voting_rounds row when every active allocation player has submitted for this vignette (or final)."""
    expected = set(game_state.get('voting_active_players') or [])
    if not expected:
        return
    subs = game_state.setdefault('allocation_vignette_submitters', {}).get(submit_key) or set()
    if not subs >= expected:
        return
    if submit_key == ALLOCATION_FINAL_SUBMIT_KEY:
        vid = game_state.get('allocation_final_vrid')
    else:
        vid = game_state.get('allocation_vignette_vrids', {}).get(submit_key)
    if vid:
        db.end_voting_round_row(vid)


def _all_players_finished_allocation() -> bool:
    expected = set(game_state.get('voting_active_players') or [])
    if not expected:
        return False
    for sid in expected:
        if players.get(sid, {}).get('allocation_player_round', 0) <= TOTAL_VOTING_ROUNDS:
            return False
    return True


def start_allocation_voting_phase() -> None:
    """Each non-admin starts at allocation round 1 and advances independently after each submit."""
    game_state['status'] = 'allocation_voting'
    game_state['allocation_session_started_at'] = time.time()
    game_state['allocation_experiment_finalized'] = False
    game_state['allocation_duration'] = 86400.0
    game_state['allocation_vignette_vrids'] = {}
    game_state['allocation_final_vrid'] = None
    game_state['allocation_vignette_submitters'] = {}
    game_state['allocation_emit_vrid'] = {}
    game_state['allocation_round_submitters'] = {}
    game_state['allocation_points_recorded'] = set()
    game_state['allocation_ballot_map'] = {}
    game_state['allocation_slot_owners'] = {}
    non_admin = [p for p in players.values() if not p['is_admin']]
    game_state['voting_active_players'] = [p['session_id'] for p in non_admin if p.get('socket_id')]
    owners = [p['session_id'] for p in non_admin if p.get('selected_images', {}).get(3)]
    plan: dict = {}
    try:
        plan = assign_final_ballots(
            list(game_state['voting_active_players']), owners, seed=int(time.time()) % 100000
        )
    except Exception as e:
        print(f"[ALLOC] Final ballot plan precompute failed: {e}")
    game_state['final_allocation_plan'] = plan

    for p in non_admin:
        p['allocation_fixture_order'] = build_allocation_fixture_order(
            random.Random(int.from_bytes(os.urandom(8), 'big'))
        )

    for p in non_admin:
        p['allocation_player_round'] = 1
    for p in non_admin:
        if not p.get('socket_id'):
            continue
        emit_allocation_round_for_player(p['session_id'], 1)

    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        socketio.emit(
            'admin_allocation_started',
            {'allocation_async': True, 'total': TOTAL_VOTING_ROUNDS},
            room=players[admin_session_id]['socket_id'],
        )
    notify_admin_player_list()


def emit_allocation_round_for_player(voter_sid: str, round_index: int) -> None:
    """Build ballot + options for one player for one round and emit allocation_vote_started."""
    if round_index < 1 or round_index > TOTAL_VOTING_ROUNDS:
        return
    p = players.get(voter_sid)
    if not p or p.get('is_admin') or not p.get('socket_id'):
        return
    gid = game_state.get('game_id')
    is_final = round_index == TOTAL_VOTING_ROUNDS

    if is_final:
        kind = 'final'
        fixture_key = None
        target_url = game_state['target_images'][2]['url']
        plan = game_state.get('final_allocation_plan') or {}
        triple = plan.get(voter_sid) or []
        if len(triple) < 3:
            socketio.emit(
                'error',
                {
                    'message': (
                        'Could not build the final voting ballot (missing peer targets). '
                        'Ensure every player has a round-3 image selection, then try again.'
                    ),
                },
                room=p['socket_id'],
            )
            return
    else:
        kind = 'hardcoded'
        order = p.get('allocation_fixture_order')
        if not order or len(order) != NUM_HARDCODED_VOTING_ROUNDS:
            print('[ALLOC] missing allocation_fixture_order; generating fallback')
            p['allocation_fixture_order'] = build_allocation_fixture_order()
            order = p['allocation_fixture_order']
        fixture_num = order[round_index - 1]
        fix = get_fixture_rounds()[fixture_num - 1]
        fixture_key = fix['fixture_set_key']
        target_url = fix['target_image_url']

    show_h = heur_mod.show_voting_heuristics(p.get('condition'))

    # Shared voting_rounds rows keyed by vignette (fixture_set_key), not display order.
    vrid = None
    if db.is_configured() and gid:
        if is_final:
            vrid = game_state.get('allocation_final_vrid')
            if vrid is None:
                vrid = db.find_voting_round_id_final(gid)
                if vrid is None:
                    vrid = db.create_voting_round_row(
                        game_id=gid,
                        voting_round_index=TOTAL_VOTING_ROUNDS,
                        kind=kind,
                        fixture_set_key=None,
                        target_image_url=target_url,
                    )
                if vrid is None:
                    vrid = db.find_voting_round_id_final(gid)
                if vrid:
                    game_state['allocation_final_vrid'] = vrid
        else:
            cache = game_state.setdefault('allocation_vignette_vrids', {})
            vrid = cache.get(fixture_key)
            if vrid is None:
                vrid = db.find_voting_round_id_by_game_fixture_key(gid, fixture_key)
            if vrid is None:
                vrid = db.create_voting_round_row(
                    game_id=gid,
                    voting_round_index=fixture_num,
                    kind=kind,
                    fixture_set_key=fixture_key,
                    target_image_url=target_url,
                )
            if vrid is None:
                vrid = db.find_voting_round_id_by_game_fixture_key(gid, fixture_key)
            if vrid:
                cache[fixture_key] = vrid

    key = (voter_sid, round_index)
    opts = []
    slot_owners = []
    if not is_final:
        # Decoupled column shuffles (rounds 1–9 only): image order and text-box order are each one uniform random
        # permutation of [0,1,2], sampled independently per player per emit (no resampling or rejection).
        cands = fix['candidates']
        rng = random.Random(int.from_bytes(os.urandom(8), 'big'))
        perm_img = [0, 1, 2]
        perm_text = [0, 1, 2]
        rng.shuffle(perm_img)
        rng.shuffle(perm_text)
        for display_col in range(3):
            img_c = cands[perm_img[display_col]]
            txt_c = cands[perm_text[display_col]]
            hs = dict(txt_c.get('heuristics') or {})
            hs[ALLOCATION_HEURISTIC_SOURCE_FIXTURE_KEY] = txt_c['fixture_image_id']
            opts.append({
                'slot_index': display_col + 1,
                'source': 'fixture',
                'fixture_image_id': img_c['fixture_image_id'],
                'image_url': img_c['image_url'],
                'owner_player_id': None,
                'prompt_id': None,
                'heuristic_snapshot': hs,
            })
            slot_owners.append(None)
    else:
        plan = game_state.get('final_allocation_plan') or {}
        triple = plan.get(voter_sid) or []
        for i, owner_sid in enumerate(triple, start=1):
            op = players.get(owner_sid)
            sel = op.get('selected_images', {}).get(3, {}) if op else {}
            url = sel.get('image_url') or ''
            pid = sel.get('prompt_id')
            if not url and pid and db.is_configured():
                try:
                    r = db.supabase.table('prompts').select('image_url').eq('prompt_id', pid).execute()
                    if r.data and r.data[0].get('image_url'):
                        url = r.data[0]['image_url']
                except Exception as ex:
                    print(f"[ALLOC] Could not load image_url for prompt {pid}: {ex}")
            hs = _heuristic_snapshot_from_selected(op, 3) if op else {}
            opts.append({
                'slot_index': i,
                'source': 'player_submission',
                'fixture_image_id': None,
                'image_url': url,
                'owner_player_id': owner_sid,
                'prompt_id': pid,
                'heuristic_snapshot': hs,
            })
            slot_owners.append(owner_sid)

    ballot_id = None
    if db.is_configured() and gid and vrid:
        ballot_id = db.create_ballot_with_options(gid, vrid, voter_sid, opts)
    if ballot_id is None:
        ballot_id = _next_synthetic_ballot_id()
    game_state['allocation_ballot_map'][key] = ballot_id
    game_state['allocation_slot_owners'][key] = slot_owners
    if vrid is not None:
        game_state.setdefault('allocation_emit_vrid', {})[key] = vrid

    ui_opts = []
    for o in opts:
        ui_opts.append({
            'image_url': o['image_url'],
            'heuristic_display': heur_mod.format_snapshot_for_ui(o['heuristic_snapshot'] or {}) if show_h else [],
        })

    p['allocation_player_round'] = round_index
    p['allocation_round_t0'] = time.time()

    _av_payload = {
        'voting_round_index': round_index,
        'total_voting_rounds': TOTAL_VOTING_ROUNDS,
        'target_image_url': target_url,
        'options': ui_opts,
        'show_voting_heuristics': show_h,
    }
    p['allocation_last_payload'] = dict(_av_payload)
    socketio.emit('allocation_vote_started', _av_payload, room=p['socket_id'])


def _apply_missing_allocations_default() -> None:
    """Admin / day-timeout: default-split every remaining round for each player until all finish."""
    for sid in list(game_state.get('voting_active_players', [])):
        if sid not in players:
            continue
        pl = players[sid]
        while pl.get('allocation_player_round', 99) <= TOTAL_VOTING_ROUNDS:
            r = pl['allocation_player_round']
            if (sid, r) in game_state.get('allocation_points_recorded', set()):
                pl['allocation_player_round'] = r + 1
                continue
            _record_point_allocation(sid, list(DEFAULT_POINT_SPLIT), r)
            _after_allocation_submit_emit(sid, r)
    if _all_players_finished_allocation():
        finish_experiment_final_ranking()


def _record_point_allocation(voter_sid: str, triple: list, round_index: int) -> None:
    """Persist one round's allocation; idempotent per (voter, round)."""
    key = (voter_sid, round_index)
    if key in game_state.setdefault('allocation_points_recorded', set()):
        return
    if len(triple) != 3 or sum(triple) != 10:
        return
    pl = players.get(voter_sid)
    if not pl or pl.get('allocation_player_round') != round_index:
        print(f"[ALLOC] skip save voter={voter_sid[:8]}... round mismatch want {round_index} have {pl and pl.get('allocation_player_round')}")
        return
    ballot_id = game_state.get('allocation_ballot_map', {}).get(key)
    vrid = game_state.get('allocation_emit_vrid', {}).get(key)
    gid = game_state.get('game_id')
    if ballot_id and db.is_configured() and gid and vrid:
        now = time.time()
        sess0 = game_state.get('allocation_session_started_at')
        round0 = pl.get('allocation_round_t0')
        sec_sess = (now - sess0) if sess0 else None
        sec_round = (now - round0) if round0 else None
        db.save_point_allocation(
            ballot_id, gid, vrid, voter_sid,
            int(triple[0]), int(triple[1]), int(triple[2]),
            seconds_since_session_start=sec_sess,
            seconds_since_round_start=sec_round,
        )
        ss = f"{sec_sess:.2f}s" if sec_sess is not None else "n/a"
        sr = f"{sec_round:.2f}s" if sec_round is not None else "n/a"
        print(
            f"[ALLOC] points voter={voter_sid[:8]}... round={round_index} session_elapsed={ss} "
            f"round_elapsed={sr} pts={triple[0]}/{triple[1]}/{triple[2]}"
        )
    owners = game_state.get('allocation_slot_owners', {}).get(key) or []
    if round_index == TOTAL_VOTING_ROUNDS:
        for pts, own in zip(triple, owners):
            if own and own in players:
                players[own]['incentive_points'] = players[own].get('incentive_points', 0) + int(pts)
    game_state['allocation_points_recorded'].add(key)
    game_state.setdefault('allocation_round_submitters', {}).setdefault(round_index, set()).add(voter_sid)
    sk = _allocation_fixture_submit_key_for_ordinal(voter_sid, round_index)
    if sk:
        game_state.setdefault('allocation_vignette_submitters', {}).setdefault(sk, set()).add(voter_sid)
        _maybe_finalize_shared_allocation_round(sk)


def _after_allocation_submit_emit(voter_sid: str, completed_round: int) -> None:
    """Emit saved ack, then next round UI or mark session complete and maybe end experiment."""
    pl = players.get(voter_sid)
    if not pl:
        return
    sock = pl.get('socket_id')
    if completed_round < TOTAL_VOTING_ROUNDS:
        if sock:
            socketio.emit('allocation_saved', {'success': True, 'completed_round': completed_round}, room=sock)
        emit_allocation_round_for_player(voter_sid, completed_round + 1)
    else:
        pl['allocation_player_round'] = TOTAL_VOTING_ROUNDS + 1
        game_state['post_survey_active'] = True
        if sock:
            socketio.emit(
                'allocation_saved',
                {
                    'success': True,
                    'completed_round': completed_round,
                    'session_complete': True,
                    'waiting_for_others': not _all_players_finished_allocation(),
                },
                room=sock,
            )
        open_post_survey_for_player(pl)
        if _all_players_finished_allocation():
            finish_experiment_final_ranking()


def finish_experiment_final_ranking():
    """Rank by incentive_points only; random tie-break; no scores shown to players."""
    if game_state.get('allocation_experiment_finalized'):
        return
    if game_state.get('status') != 'allocation_voting':
        return
    game_state['allocation_experiment_finalized'] = True
    non_admin = [p for p in players.values() if not p['is_admin']]
    ranked = list(non_admin)
    rng = random.Random(int(time.time() * 1000) % (2 ** 32))
    rng.shuffle(ranked)
    ranked.sort(key=lambda p: p.get('incentive_points', 0), reverse=True)
    results = []
    for i, p in enumerate(ranked, start=1):
        results.append({
            'rank': i,
            'player_name': p.get('display_name', p['name']),
        })
    game_state['status'] = 'game_over'
    if db.is_configured() and game_state.get('game_id'):
        db.end_game(game_id=game_state['game_id'], rounds_completed=3)
    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        socketio.emit('admin_game_over', {
            'results': results,
            'experiment': True,
            'players': [{
                'name': x.get('display_name', x['name']),
                'incentive_points': x.get('incentive_points', 0),
                'session_id': x['session_id'],
                'seat_number': admin_seat_number_for_payload(x),
            } for x in non_admin],
        }, room=players[admin_session_id]['socket_id'])
    open_post_survey_after_game_over({'results': results, 'experiment': True})
    game_state['status'] = 'lobby'
    game_state['onboarding_prompting_end_time'] = None
    print('[GAME] Experiment complete — final ranking sent')


@socketio.on('round_timer_check')
def handle_round_timer_check():
    # Don't process timer checks if we're showing results or game is over
    # Players should stay on results screen until admin progresses
    if game_state['status'] in ['round_results', 'game_over']:
        return

    if game_state['status'] == 'awaiting_next_prompting':
        return
    if game_state['status'] == 'awaiting_voting_start':
        return

    if game_state['status'] == 'onboarding':
        return
    
    if game_state['status'] == 'playing':
        time_remaining = game_state['round_end_time'] - time.time()

        if time_remaining <= 0:
            # Round ended - show transition screen
            if game_state['status'] == 'playing':  # Only if still in playing state
                start_transition_to_selection()
        else:
            socketio.emit('timer_update', {'time_remaining': time_remaining})
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
    elif game_state['status'] == 'voting':
        # Periodically check selection status during voting phase
        # This ensures auto-selection works for bots and handles cases where
        # real players' client-side timers don't fire (network issues, etc.)
        # Check every 5 seconds to avoid excessive calls while still being responsive
        time_elapsed = time.time() - game_state.get('voting_start_time', time.time())
        duration = game_state.get('voting_duration', 30)
        
        # Only check if we're close to or past the duration (check every 5 seconds near the end)
        # This prevents excessive checking while still catching timer expiration
        if time_elapsed >= (duration - 5) or time_elapsed >= duration:
            # Call check_all_selected which will auto-select for players who haven't confirmed
            # and advance to voting screen if all are ready or time has elapsed
            check_all_selected()
    elif game_state['status'] == 'allocation_voting':
        elapsed = time.time() - game_state.get('allocation_session_started_at', time.time())
        dur = game_state.get('allocation_duration', 86400.0)
        if elapsed >= (dur - 2) or elapsed >= dur:
            _apply_missing_allocations_default()

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
    
    # Aggressive memory clearing during transition (before selection screen)
    # Clear base64 image data for current round - only keep if URL exists (upload completed)
    current_round = game_state['current_round']
    cleared_count = 0
    kept_count = 0
    
    for p in players.values():
        if not p['is_admin']:
            if current_round in p['images']:
                for img in p['images'][current_round]:
                    # Only clear if image_url exists (upload completed) - safe to clear base64
                    if img.get('image_url') and 'image_data' in img:
                        del img['image_data']
                        cleared_count += 1
                    elif 'image_data' in img:
                        # Keep base64 for images still uploading (fallback for selection screen)
                        kept_count += 1
            
            # Also clear completed rounds aggressively
            for round_num in [1, 2, 3]:
                if round_num < current_round:
                    # Force clear all image_data from completed rounds
                    if round_num in p['images']:
                        for img in p['images'][round_num]:
                            if 'image_data' in img:
                                del img['image_data']
                                cleared_count += 1
                    if round_num in p['selected_images']:
                        selected = p['selected_images'][round_num]
                        if 'image_data' in selected:
                            del selected['image_data']
                            cleared_count += 1
    
    print(f"[MEMORY] Transition clearing: {cleared_count} images cleared, {kept_count} kept (still uploading)")
    
    # Force garbage collection to free memory immediately
    gc.collect()
    print(f"[MEMORY] Garbage collection completed after transition clearing")
    
    # Show transition screen to all players (non-admin) with timer info
    for p in players.values():
        if not p['is_admin']:
            socket_id = p.get('socket_id')
            if socket_id:  # Only send if player is connected
                socketio.emit('show_transition_screen', {
                    'message': "Now you'll get to choose the best image that you created.",
                    'max_wait': 10  # Max 10 seconds before auto-progress
                }, room=socket_id)
    
    # Notify admin that transition started
    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        socketio.emit('admin_status_update', {
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
    game_state['voting_duration'] = 90  # 90 seconds to select best image
    
    # Track which players were active when voting started (for voting completion check)
    # This ensures we wait for all players who were present at voting start, even if they disconnect
    game_state['voting_active_players'] = [p['session_id'] for p in players.values() 
                                          if not p.get('is_admin') and p.get('socket_id')]
    print(f"[VOTING] Tracked {len(game_state['voting_active_players'])} active players at voting start: {game_state['voting_active_players']}")
    
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
    # Broadcast voting_started to all non-admin players - must check socket_id, None defaults to current request context
    for p in players.values():
        if not p['is_admin']:
            socket_id = p.get('socket_id')
            if socket_id:  # Only send if player is connected
                player_count += 1
                print(f"[VOTING] Emitting voting_started to player {p['name']} (socket: {socket_id})")
                socketio.emit('voting_started', {
                    'round': current_round,
                    'duration': selection_duration,
                    'start_time': selection_start_time,  # Synchronized start time
                    'default_selected': False,  # Always False - default is UI-only until timer expires
                    'image_context_bullets': player_gets_image_context_bullets(p),
                }, room=socket_id)
    print(f"[VOTING] Emitted voting_started to {player_count} connected players with synchronized start time")
    
    # Notify admin
    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        socketio.emit('admin_voting_started', {
            'round': current_round,
            'voting_start_time': game_state['voting_start_time'],  # Include start time for client calculation
            'voting_duration': game_state['voting_duration'],  # Include duration for client calculation
            'players': [{
                'name': p.get('display_name', p['name']),
                'condition': p['condition'],
                'is_connected': p.get('socket_id') is not None,
                'has_selected': current_round in p['selected_images'] and p.get('has_confirmed_selection', False),
                'prompts_submitted': len(p['images'].get(current_round, [])),
                'session_id': p['session_id'],
                'seat_number': admin_seat_number_for_payload(p),
            } for p in players.values() if not p['is_admin']]
        }, room=players[admin_session_id]['socket_id'])

    print(f"Voting phase started for round {current_round}")


def _persist_image_selection_row(player, current_round: int, selected_img: dict) -> None:
    """Write image_selections with heuristic snapshot and selection-vs-latest offset."""
    if not db.is_configured() or not game_state.get('game_id') or not game_state.get('round_id'):
        return
    prompt_id = selected_img.get('prompt_id')
    if not prompt_id:
        return
    if isinstance(prompt_id, (int, float)) and prompt_id < 0:
        return
    imgs = player['images'].get(current_round, [])
    pi = selected_img.get('prompt_index', 1)
    elapsed = int(selected_img.get('prompt_sent_elapsed_seconds') or 0)
    cond_sel = (player.get('condition') or '').strip().upper()
    sel_snap = heur_mod.snapshot_for_image_entry(
        prompt_index=pi,
        prompt_text=selected_img.get('prompt', ''),
        images_before_and_including=imgs,
        prompt_elapsed_seconds=elapsed,
        cumulative_word_count_for_prompt_line=cond_sel in ('C_HU', 'T_HU'),
    )
    cum = heur_mod.cumulative_word_count_for_round(imgs, pi)
    idxs = [
        im.get('prompt_index')
        for im in imgs
        if not im.get('error_type') and im.get('prompt_id')
    ]
    max_idx = max(idxs) if idxs else pi
    steps_back = (max_idx - pi) if max_idx is not None and pi is not None else None
    db.save_image_selection(
        player_id=player['session_id'],
        round_id=game_state['round_id'],
        game_id=game_state['game_id'],
        prompt_id=prompt_id,
        prompt_index_at_selection=pi,
        cumulative_word_count=cum,
        max_prompt_index_at_selection=max_idx,
        selection_steps_back_from_latest=steps_back,
        heuristic_snapshot=sel_snap,
    )


@socketio.on('select_image')
def handle_select_image(data):
    session_id = session.get('session_id')
    if session_id not in players:
        return

    player = players[session_id]
    if game_state['status'] != 'voting':
        # Idempotent ack: server may have already finished selection (e.g. timer) before this packet arrives.
        cr = game_state['current_round']
        if (
            game_state['status'] == 'awaiting_next_prompting'
            and cr in player.get('selected_images', {})
            and player.get('has_confirmed_selection', {}).get(cr)
        ):
            emit('image_selected', {'success': True})
            return
        emit('image_selected', {'success': False, 'error': 'Selection is not open right now.'})
        return

    prompt_id = data.get('prompt_id')
    prompt_index_sel = data.get('prompt_index')
    image_index = data.get('image_index')  # Keep for backward compatibility/validation
    current_round = game_state['current_round']

    # Prefer prompt_id if available (more reliable than index due to error image filtering mismatch)
    selected_image = None
    if prompt_id:
        # Find image by prompt_id (avoids index mismatch between client filtered array and server unfiltered array)
        for img in player['images'][current_round]:
            if img.get('prompt_id') == prompt_id:
                selected_image = img
                break
        
        if not selected_image:
            print(f"❌ ERROR: Player {player.get('display_name', player['name'])} selected image with prompt_id {prompt_id} but it wasn't found in their images for round {current_round}")
            emit('image_selected', {'success': False, 'error': 'Selected image not found. Please try selecting again.'})
            return
    elif prompt_index_sel is not None:
        try:
            pi = int(prompt_index_sel)
        except (TypeError, ValueError):
            pi = None
        if pi is not None:
            for img in player['images'][current_round]:
                if int(img.get('prompt_index') or -1) == pi:
                    selected_image = img
                    break
        if not selected_image:
            print(
                f"❌ ERROR: Player {player.get('display_name', player['name'])} selected prompt_index {prompt_index_sel} "
                f"but it wasn't found in their images for round {current_round}"
            )
            emit('image_selected', {'success': False, 'error': 'Selected image not found. Please try selecting again.'})
            return
    elif image_index is not None and image_index < len(player['images'][current_round]):
        # Fallback to index-based lookup (backward compatibility)
        selected_image = player['images'][current_round][image_index]
        print(f"⚠️ WARNING: Using index-based selection (backward compatibility). Player {player.get('display_name', player['name'])} selected index {image_index}")
    else:
        print(f"❌ ERROR: Player {player.get('display_name', player['name'])} sent invalid selection (no prompt_id or invalid image_index)")
        emit('image_selected', {'success': False, 'error': 'Invalid image selection. Please try selecting again.'})
        return
    
    # Server-side validation: Prevent selecting error images
    if selected_image.get('error_type'):
        print(f"❌ ERROR: Player {player.get('display_name', player['name'])} attempted to select error image (error_type: {selected_image.get('error_type')}) in round {current_round}. Rejecting selection.")
        emit('image_selected', {'success': False, 'error': 'Cannot select error image. Please choose a valid image.'})
        return
    
    # Server-side validation: Prevent selecting images without prompt_id (may lag briefly while DB row saves)
    final_prompt_id = selected_image.get('prompt_id')
    if not final_prompt_id:
        print(
            f"❌ ERROR: Player {player.get('display_name', player['name'])} attempted to select image without prompt_id "
            f"yet (round {current_round}, prompt_index={selected_image.get('prompt_index')})."
        )
        emit(
            'image_selected',
            {
                'success': False,
                'error': 'Image is still saving. Please wait a second and tap Confirm again.',
            },
        )
        return
    
    player['selected_images'][current_round] = selected_image
    player['has_confirmed_selection'][current_round] = True  # Mark as confirmed
    
    _persist_image_selection_row(player, current_round, selected_image)
    if db.is_configured() and game_state.get('game_id') and game_state.get('round_id'):
        print(f"✅ Saved image selection for player {player.get('display_name', player['name'])} in round {current_round}, prompt_id={final_prompt_id}")
    else:
        print(f"⚠️ WARNING: Cannot save image selection - database not configured or missing game_id/round_id")
    
    emit('image_selected', {'success': True})

    # Notify admin that player has selected an image
    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        socketio.emit('player_selected_image', {
            'session_id': session_id,
            'player_name': player.get('display_name', player['name']),
            'round': current_round,
            'has_selected': True
        }, room=players[admin_session_id]['socket_id'])

    # Check if all players have selected
    check_all_selected()


def force_finish_image_selection_phase():
    """
    Admin / console: leave the image-selection screen and follow the normal experiment path:
    rounds 1–2 → next 5-minute prompting round; round 3 → post-round-3 buffer then point-allocation voting.
    Does not use legacy per-round `vote_on_images` (that reused #voting-screen and broke allocation UI).
    """
    if game_state['status'] != 'voting':
        return False
    current_round = game_state['current_round']
    non_admin_players = [p for p in players.values() if not p.get('is_admin')]
    active_players = [p for p in non_admin_players if p.get('socket_id') is not None]

    for player in active_players:
        if current_round not in player.get('selected_images', {}) and player.get('images', {}).get(current_round):
            valid_images = [
                img for img in player['images'][current_round]
                if not img.get('error_type') and img.get('prompt_id') is not None
            ]
            if valid_images:
                last_valid_image = valid_images[-1]
                player['selected_images'][current_round] = last_valid_image
                player.setdefault('has_confirmed_selection', {1: False, 2: False, 3: False})
                player['has_confirmed_selection'][current_round] = True
                if db.is_configured() and game_state.get('game_id') and game_state.get('round_id'):
                    _persist_image_selection_row(player, current_round, last_valid_image)
        elif current_round in player.get('selected_images', {}):
            player.setdefault('has_confirmed_selection', {1: False, 2: False, 3: False})
            if not player['has_confirmed_selection'].get(current_round):
                player['has_confirmed_selection'][current_round] = True
                if db.is_configured() and game_state.get('game_id') and game_state.get('round_id'):
                    _persist_image_selection_row(player, current_round, player['selected_images'][current_round])

    if current_round < 3:
        print(f"[ADMIN] Forcing selection complete — awaiting Gamemaster for prompting round {current_round + 1}")
        enter_awaiting_next_prompting_after_selection()
    else:
        print('[ADMIN] Forcing selection complete — awaiting Gamemaster to start voting')
        enter_awaiting_voting_start_after_round_three_selection()
    return True


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
                # Find the last valid (non-error) image with a valid prompt_id
                valid_images = [img for img in player['images'][current_round] 
                              if not img.get('error_type') and img.get('prompt_id') is not None]
                if valid_images:
                    last_valid_image = valid_images[-1]
                    player['selected_images'][current_round] = last_valid_image
                    player['has_confirmed_selection'][current_round] = True
                    
                    # Save to database
                    if db.is_configured() and game_state.get('game_id') and game_state.get('round_id'):
                        prompt_id = last_valid_image.get('prompt_id')
                        _persist_image_selection_row(player, current_round, last_valid_image)
                        print(f"[SELECTION] Auto-selected valid image (prompt_id={prompt_id}) for player {player['name']}")
                    else:
                        print(f"[SELECTION] Auto-selected valid image for player {player['name']} (database save skipped - not configured)")
                else:
                    # No valid images available - log error and don't auto-select
                    print(f"❌ ERROR: Player {player['name']} has no valid images (no error_type and prompt_id) to auto-select in round {current_round}. Total images: {len(player['images'][current_round])}")
                    # Don't mark as confirmed - let admin handle this edge case
                    # The game will be stuck, but this is better than selecting an error image
    
    # Check if all players have now confirmed their selection (either manually or via timer expiry)
    all_selected = all(
        player.get('has_confirmed_selection', {}).get(current_round, False)
        for player in active_players
    )
    
    # Emit waiting status to all players (only if time hasn't elapsed)
    if time_elapsed < duration:
        waiting_count = len([p for p in active_players if not p.get('has_confirmed_selection', {}).get(current_round, False)])
        if waiting_count > 0:
            socketio.emit('selection_waiting', {'waiting_count': waiting_count, 'total_players': len(active_players)})

    # Advance: R1/R2 image selection → admin gate; legacy voting_images → keep auto advance; R3 → allocation prep
    if all_selected or (time_elapsed >= duration):
        if game_state['current_round'] < 3:
            if game_state['status'] == 'voting':
                print(f"[SELECTION] Selection complete for round {game_state['current_round']} — awaiting Gamemaster for next prompting round")
                enter_awaiting_next_prompting_after_selection()
            elif game_state['status'] == 'voting_images':
                # Legacy path only — never treat other statuses (e.g. awaiting_next_prompting) as "auto-advance"
                print(f"[SELECTION] voting_images complete for round {game_state['current_round']} — advancing to next prompting (legacy)")
                advance_to_next_prompting_round_after_selection()
            else:
                print(
                    f"[SELECTION] Selection completion ignored — status already {game_state['status']} "
                    f"(likely another request entered the Gamemaster gate first)"
                )
        else:
            print("[SELECTION] Round 3 selection complete — awaiting Gamemaster to start voting")
            enter_awaiting_voting_start_after_round_three_selection()

@socketio.on('check_selection_status')
def handle_check_selection_status():
    """Client requests to check selection status (called when timer expires)"""
    if game_state['status'] == 'voting':
        # Check if all players have selected or time has elapsed (will auto-select and advance)
        check_all_selected()

def start_voting_on_images():
    """Start the voting phase where players vote on each other's selected images"""
    try:
        game_state['status'] = 'voting_images'
        current_round = game_state['current_round']
        
        # Track which players were active when voting on images started
        # This ensures we wait for all players who were present at voting start, even if they disconnect
        if not game_state.get('voting_active_players'):
            # Only set if not already set (from selection phase)
            game_state['voting_active_players'] = [p['session_id'] for p in players.values() 
                                                  if not p.get('is_admin') and p.get('socket_id')]
            print(f"[VOTING] Tracked {len(game_state['voting_active_players'])} active players at voting start: {game_state['voting_active_players']}")
        
        # Log current state for debugging
        connected_players = [p for p in players.values() if not p.get('is_admin') and p.get('socket_id')]
        print(f"[VOTING] Starting voting phase: round={current_round}, connected_players={len(connected_players)}, total_players={len([p for p in players.values() if not p.get('is_admin')])}")
        
        # CRITICAL: Auto-select for any players who haven't selected yet
        # This ensures all players have selections even if timer didn't fire or admin skipped
        non_admin_players = [p for p in players.values() if not p.get('is_admin')]
        active_players = [p for p in non_admin_players if p.get('socket_id') is not None]
        
        auto_selected_count = 0
        for player in active_players:
            if current_round not in player['selected_images'] and player['images'].get(current_round):
                # Find the last valid (non-error) image with a valid prompt_id
                valid_images = [img for img in player['images'][current_round] 
                              if not img.get('error_type') and img.get('prompt_id') is not None]
                if valid_images:
                    last_valid_image = valid_images[-1]
                    player['selected_images'][current_round] = last_valid_image
                    player['has_confirmed_selection'][current_round] = True
                    
                    # Save to database
                    if db.is_configured() and game_state.get('game_id') and game_state.get('round_id'):
                        prompt_id = last_valid_image.get('prompt_id')
                        _persist_image_selection_row(player, current_round, last_valid_image)
                        print(f"[VOTING] Auto-selected valid image (prompt_id={prompt_id}) for player {player['name']} before voting")
                        auto_selected_count += 1
                    else:
                        print(f"[VOTING] Auto-selected valid image for player {player['name']} before voting (database save skipped - not configured)")
                        auto_selected_count += 1
                else:
                    # No valid images available - log error
                    print(f"❌ ERROR: Player {player['name']} has no valid images to auto-select in round {current_round}. Total images: {len(player['images'][current_round])}")
        
        if auto_selected_count > 0:
            print(f"[VOTING] Auto-selected images for {auto_selected_count} player(s) before starting voting phase")
        
        # Additional memory clearing when voting starts (clear any remaining base64)
        # Most should already be cleared during transition, but clear any stragglers
        for p in players.values():
            if not p['is_admin']:
                if current_round in p['images']:
                    selected_prompt_id = p['selected_images'].get(current_round, {}).get('prompt_id')
                    for img in p['images'][current_round]:
                        # Keep base64 only for selected image if URL not ready yet
                        if img.get('prompt_id') != selected_prompt_id and 'image_data' in img:
                            del img['image_data']
                        # Also clear selected image base64 if URL exists
                        elif img.get('prompt_id') == selected_prompt_id and img.get('image_url') and 'image_data' in img:
                            del img['image_data']
        print(f"[MEMORY] Cleared remaining image_data from current round when voting started")

        # Gather all selected images with prompt_id (exclude admin)
        # Use image_url instead of base64 to reduce memory usage
        selected_images = []
        for session_id, player in players.items():
            if not player['is_admin'] and current_round in player['selected_images']:
                selected_image = player['selected_images'][current_round]
                prompt_id = selected_image.get('prompt_id')
                
                # Prefer image_url, fallback to image_data if URL not available
                image_url = selected_image.get('image_url')
                if not image_url and prompt_id and db.is_configured():
                    # Try to fetch from database if not in memory
                    try:
                        result = db.supabase.table('prompts').select('image_url').eq('prompt_id', prompt_id).execute()
                        if result.data and result.data[0].get('image_url'):
                            image_url = result.data[0]['image_url']
                    except Exception as e:
                        print(f"[VOTING] Could not fetch image_url from database for prompt_id {prompt_id}: {e}")
                
                # Use URL if available, otherwise fallback to base64 (for backward compatibility)
                image_data = image_url if image_url else selected_image.get('image_data', '')
                
                selected_images.append({
                    'session_id': session_id,
                    'player_name': player.get('display_name', player['name']),
                    'image': {
                        'image_url': image_url,  # URL from Supabase
                        'image_data': selected_image.get('image_data', '') if not image_url else '',  # Fallback base64 only if no URL
                        'has_url': bool(image_url)  # Flag for client
                    },
                    'prompt_id': prompt_id
                })

        # Get target image for this round
        target_image = game_state.get('current_target', {})

        # Send images to each player with their own session_id for filtering (non-admin only)
        # Must check socket_id, None defaults to current request context
        for target_session_id in players.keys():
            player = players[target_session_id]
            if not player['is_admin']:
                socket_id = player.get('socket_id')
                if socket_id:  # Only send if player is connected
                    socketio.emit('vote_on_images', {
                        'images': selected_images,
                        'round': current_round,
                        'my_session_id': target_session_id,
                        'target_image': {
                            'url': target_image.get('url', '')
                        },
                        'image_context_bullets': player_gets_image_context_bullets(player),
                    }, room=socket_id)

        print("Players now voting on images")
    except Exception as e:
        print(f"❌ ERROR in start_voting_on_images(): {e}")
        import traceback
        traceback.print_exc()
        # Try to recover by logging state
        print(f"[ERROR] Game state: status={game_state.get('status')}, round={game_state.get('current_round')}, players={len(players)}")

@socketio.on('submit_point_allocation')
def handle_submit_point_allocation(data):
    session_id = session.get('session_id')
    if session_id not in players or game_state['status'] != 'allocation_voting':
        emit('error', {'message': 'Not in voting phase'})
        return
    pts = data or {}
    try:
        a, b, c = int(pts.get('points_slot_1')), int(pts.get('points_slot_2')), int(pts.get('points_slot_3'))
    except (TypeError, ValueError):
        emit('error', {'message': 'Invalid points'})
        return
    if a + b + c != 10 or min(a, b, c) < 0 or max(a, b, c) > 10:
        emit('error', {'message': 'Points must be integers from 0 to 10 summing to 10'})
        return
    voter = players[session_id]
    ri = voter.get('allocation_player_round')
    if ri is None or ri < 1 or ri > TOTAL_VOTING_ROUNDS:
        emit('error', {'message': 'Invalid allocation state'})
        return
    cr = pts.get('voting_round_index')
    if cr is not None:
        try:
            if int(cr) != ri:
                emit('error', {'message': 'Round mismatch; refresh the voting screen.'})
                return
        except (TypeError, ValueError):
            emit('error', {'message': 'Invalid voting round.'})
            return
    _record_point_allocation(session_id, [a, b, c], ri)
    _after_allocation_submit_emit(session_id, ri)
    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        socketio.emit('player_allocation_submitted', {
            'session_id': session_id,
            'player_name': players[session_id].get('display_name', players[session_id]['name']),
            'round': ri,
        }, room=players[admin_session_id]['socket_id'])
    notify_admin_player_list()


@socketio.on('cast_vote')
def handle_cast_vote(data):
    session_id = session.get('session_id')
    if session_id not in players:
        return
    if game_state['status'] == 'allocation_voting':
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

        # Notify admin that player has voted
        if admin_session_id in players and players[admin_session_id].get('socket_id'):
            socketio.emit('player_voted', {
                'session_id': session_id,
                'player_name': voter.get('display_name', voter['name']),
                'round': current_round,
                'has_voted': True
            }, room=players[admin_session_id]['socket_id'])

        # Check if voting is complete
        check_voting_complete()

def check_voting_complete():
    current_round = game_state['current_round']
    
    # Use the list of players who were active when voting started
    # This ensures we wait for all players who were present at voting start, even if they disconnect
    voting_start_players = game_state.get('voting_active_players', [])
    
    if not voting_start_players:
        # Fallback: if voting_active_players wasn't set, use current active players
        voting_start_players = [p['session_id'] for p in players.values() 
                               if not p.get('is_admin') and p.get('socket_id')]
        print(f"[VOTING] WARNING: voting_active_players not set, using current active players: {voting_start_players}")
    
    # Count votes from players who were active at voting start
    votes_cast = 0
    for session_id in voting_start_players:
        if session_id in players:
            player = players[session_id]
            if player['has_voted'].get(current_round, False):
                votes_cast += 1
    
    total_expected = len(voting_start_players)
    
    print(f"[VOTING] Progress: {votes_cast}/{total_expected} players have voted (from voting start list)")

    # Require 100% of players who were active at voting start to vote before progressing
    if total_expected > 0 and votes_cast == total_expected:
        print(f"[VOTING] All {total_expected} players have voted, showing results")
        show_round_results()

def show_round_results():
    game_state['status'] = 'round_results'
    current_round = game_state['current_round']
    
    # Clear voting_active_players when round results are shown
    game_state['voting_active_players'] = []

    # Calculate scores (exclude admin)
    results = []
    for session_id, player in players.items():
        if not player['is_admin']:  # Exclude admin from results
            votes = player['votes_received'][current_round]
            player['round_scores'][current_round - 1] = votes
            player['score'] += votes

            # Use image_url with fallback to image_data for round results
            selected_img = player['selected_images'].get(current_round, {})
            image_url = selected_img.get('image_url')
            if not image_url:
                # Try to fetch from database if not in memory
                prompt_id = selected_img.get('prompt_id')
                if prompt_id and db.is_configured():
                    try:
                        result = db.supabase.table('prompts').select('image_url').eq('prompt_id', prompt_id).execute()
                        if result.data and result.data[0].get('image_url'):
                            image_url = result.data[0]['image_url']
                    except Exception as e:
                        print(f"[RESULTS] Could not fetch image_url from database for prompt_id {prompt_id}: {e}")
            
            # Use URL if available, otherwise fallback to base64
            image_display = image_url if image_url else selected_img.get('image_data', '')
            
            results.append({
                'player_name': player.get('display_name', player['name']),
                'votes': votes,
                'total_score': player['score'],
                'image': image_display
            })

    # Sort by votes received in this round (not total score)
    results.sort(key=lambda x: x['votes'], reverse=True)
    
    # Clear old round data after round completes (memory optimization)
    # Force clear image_data from completed rounds, even if image_url doesn't exist yet
    for p in players.values():
        if not p['is_admin']:
            for round_num in [1, 2, 3]:
                if round_num < current_round:
                    # Force clear image_data from all images in completed rounds (even without URL)
                    if round_num in p['images']:
                        for img in p['images'][round_num]:
                            if 'image_data' in img:
                                del img['image_data']  # Force clear, even if URL not ready
                    # Also clear image_data from selected_images for completed rounds
                    if round_num in p['selected_images']:
                        selected = p['selected_images'][round_num]
                        if 'image_data' in selected:
                            del selected['image_data']  # Force clear
    print(f"[MEMORY] Force cleared image_data from completed rounds (rounds < {current_round})")
    
    # Clear base64 from current round's selected image after results are shown
    for p in players.values():
        if not p['is_admin']:
            if current_round in p['selected_images']:
                selected = p['selected_images'][current_round]
                if 'image_data' in selected:
                    del selected['image_data']  # Force clear, URL should be available by now
    print(f"[MEMORY] Cleared image_data from current round's selected images")
    
    # Force garbage collection after round results
    gc.collect()
    print(f"[MEMORY] Garbage collection completed after round results")

    # Send to players only (not admin) - must check socket_id, None defaults to current request context
    for p in players.values():
        if not p['is_admin']:
            socket_id = p.get('socket_id')
            if socket_id:  # Only send if player is connected
                socketio.emit('round_results', {
                    'round': current_round,
                    'results': results
                }, room=socket_id)
    
    # Send admin view
    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        socketio.emit('admin_round_results', {
            'round': current_round,
            'results': results,
            'players': [{
                'name': p.get('display_name', p['name']),
                'condition': p['condition'],
                'is_connected': p.get('socket_id') is not None,
                'session_id': p['session_id'],
                'seat_number': admin_seat_number_for_payload(p),
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

    if game_state['status'] == 'awaiting_next_prompting':
        advance_to_next_prompting_round_after_selection()
        notify_admin_player_list()
        return

    if game_state['status'] == 'awaiting_voting_start':
        emit('error', {'message': 'Use Start Voting to begin voting.'})
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
                
                # Note: Memory clearing for completed rounds is already done in show_round_results()
                # No need to clear again here to avoid redundant operations

        # Send game started to players only (not admin) - must check socket_id, None defaults to current request context
        for p in players.values():
            if not p['is_admin']:
                socket_id = p.get('socket_id')
                if socket_id:  # Only send if player is connected
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
                    
                    # Add welcome message for round start
                    welcome_message = get_welcome_message(p, game_state['current_round'])
                    if welcome_message:
                        character_data['message'] = welcome_message

                    _gs = {
                        'round': game_state['current_round'],
                        'target': game_state['current_target'],
                        'end_time': game_state['round_end_time'],
                        'character': character_data,
                        'image_context_bullets': player_gets_image_context_bullets(p),
                    }
                    _gs.update(game_started_aggregate_heuristic_fields(p))
                    socketio.emit('game_started', _gs, room=socket_id)
        
        # Send admin game started event with player status
        if admin_session_id in players and players[admin_session_id].get('socket_id'):
            current_round_num = game_state['current_round']
            time_remaining = game_state['round_end_time'] - time.time() if game_state.get('round_end_time') else None
            socketio.emit('admin_game_started', {
                'round': current_round_num,
                'target': game_state['current_target'],
                'time_remaining': time_remaining,
                'round_end_time': game_state.get('round_end_time'),  # Include end time for client calculation
                'game_id': game_state.get('game_id'),
                'players': [{
                    'name': p.get('display_name', p['name']),
                    'condition': p['condition'],
                    'is_connected': p.get('socket_id') is not None,
                    'session_id': p['session_id'],
                    'seat_number': admin_seat_number_for_payload(p),
                    'prompts_submitted': len(p['images'].get(current_round_num, []))
                } for p in players.values() if not p['is_admin']]
            }, room=players[admin_session_id]['socket_id'])

        print(f"Round {game_state['current_round']} started")
    else:
        # Prompting ends after round 3; selection and allocation voting advance automatically.
        msg = (
            'Round 3 is the last prompting round. Do not use Next round — the game continues '
            'with image selection, then point voting. Use admin controls for allocation rounds if needed.'
        )
        emit('error', {'message': msg})
        print(f'[ADMIN] next_round ignored after prompting: {msg}')


@socketio.on('start_voting')
def handle_start_voting():
    """Admin-only: after R3 selection, start the allocation voting flow."""
    session_id = session.get('session_id')
    if session_id != admin_session_id:
        emit('error', {'message': 'Only admin can start voting'})
        return
    if game_state.get('current_round') != 3 or game_state.get('status') != 'awaiting_voting_start':
        emit('error', {'message': 'Not ready to start voting'})
        return
    start_post_round_three_voting_buffer()
    notify_admin_player_list()

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
                'condition': player['condition'],
                'character': player['character'],
                'prompt_count': player['prompt_count']
            })

    final_results.sort(key=lambda x: x['total_score'], reverse=True)

    # Send admin view
    if admin_session_id in players and players[admin_session_id].get('socket_id'):
        socketio.emit('admin_game_over', {
            'results': final_results,
            'players': [{
                'name': p.get('display_name', p['name']),
                'condition': p['condition'],
                'is_connected': p.get('socket_id') is not None,
                'session_id': p['session_id'],
                'seat_number': admin_seat_number_for_payload(p),
                'score': p['score'],
                'prompts_submitted': sum(len(p['images'].get(r, [])) for r in [1, 2, 3])
            } for p in players.values() if not p['is_admin']]
        }, room=players[admin_session_id]['socket_id'])
    open_post_survey_after_game_over({'results': final_results})

    print("Game over!")
    
    # Set game state to 'lobby' after showing final leaderboard
    # This allows admin to clear players after the game is done
    # Players will still see the leaderboard on their screen, but server state is reset
    game_state['status'] = 'lobby'
    game_state['onboarding_phase'] = 'prompting'
    game_state['onboarding_prompting_end_time'] = None
    notify_admin_player_list()

@socketio.on('skip_voting')
def handle_skip_voting():
    """Admin-only: Context-dependent skip (selection → next prompting or R3 allocation prep; legacy image voting → results; allocation → force advance)."""
    session_id = session.get('session_id')
    
    # Check if player is admin
    if session_id != admin_session_id:
        emit('error', {'message': 'Only admin can skip voting'})
        return
    
    if game_state['status'] == 'allocation_voting':
        _apply_missing_allocations_default()
        return

    # Only allow skipping if we're in voting phase
    if game_state['status'] in ['voting', 'voting_images']:
        if game_state['status'] == 'voting':
            # Image selection: same outcome as everyone finishing — next prompting (R1–2) or allocation prep (R3).
            force_finish_image_selection_phase()
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
    
    # Get admin's socket_id to ensure we send to the right place
    if admin_session_id not in players or not players[admin_session_id].get('socket_id'):
        return
    
    admin_socket_id = players[admin_session_id]['socket_id']
    
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
            if status == 'onboarding':
                prompts_submitted = len(p.get('onboarding_images', []))
                has_selected = None
                has_voted = None
            else:
                prompts_submitted = len(p['images'].get(current_round, [])) if current_round > 0 else 0
                has_selected = (
                    current_round in p['selected_images']
                    if status in ['voting', 'voting_images', 'awaiting_next_prompting']
                    else None
                )
                has_voted = p['has_voted'].get(current_round, False) if status == 'voting_images' else None

            player_status.append({
                'name': p.get('display_name', p['name']),
                'condition': p['condition'],
                'is_connected': p.get('socket_id') is not None,
                'prompts_submitted': prompts_submitted,
                'has_selected': has_selected,
                'has_voted': has_voted,
                'session_id': p['session_id'],
                'seat_number': admin_seat_number_for_payload(p),
                'score': p['score']
            })
    
    socketio.emit('admin_status', {
        'status': status,
        'round': current_round,
        'time_remaining': time_remaining,
        'players': player_status,
        'target': game_state.get('current_target')
    }, room=admin_socket_id)

@socketio.on('admin_end_round')
def handle_admin_end_round():
    """Admin-only: End playing round early, or during onboarding start practice voting."""
    session_id = session.get('session_id')
    
    if session_id != admin_session_id:
        emit('error', {'message': 'Only admin can end round early'})
        return

    if game_state['status'] == 'onboarding':
        if game_state.get('onboarding_phase', 'prompting') != 'prompting':
            emit('error', {'message': 'Practice voting is already in progress.'})
            return
        print('[ONBOARDING] Admin ended practice prompting → practice voting')
        broadcast_onboarding_practice_voting()
        return
    
    # Only allow ending round if currently playing
    if game_state['status'] != 'playing':
        emit('error', {'message': 'Round is not in playing state'})
        return
    
    print(f"[ADMIN] Admin ending round {game_state['current_round']} early")
    # Force transition to selection screen
    start_transition_to_selection()


@socketio.on('submit_onboarding_practice_points')
def handle_submit_onboarding_practice_points(data):
    """Non-admin: submit exactly 10 points across three onboarding practice slots; persisted per player."""
    session_id = session.get('session_id')
    if not session_id or session_id not in players:
        return
    player = players[session_id]
    if player.get('is_admin'):
        emit('error', {'message': 'Gamemaster does not submit practice points.'})
        return
    if game_state['status'] != 'onboarding' or game_state.get('onboarding_phase') != 'practice_voting':
        emit('error', {'message': 'Practice voting is not active.'})
        return
    if player.get('onboarding_practice_submitted'):
        emit('error', {'message': 'You already submitted your practice points.'})
        return
    pts = (data or {}).get('points')
    if not isinstance(pts, list) or len(pts) != 3:
        emit('error', {'message': 'Send exactly three point values.'})
        return
    try:
        nums = [int(pts[i]) for i in range(3)]
    except (TypeError, ValueError):
        emit('error', {'message': 'Points must be whole numbers.'})
        return
    for n in nums:
        if n < 0 or n > 10:
            emit('error', {'message': 'Each value must be between 0 and 10.'})
            return
    if sum(nums) != 10:
        emit('error', {'message': 'Points must total exactly 10.'})
        return
    player['onboarding_practice_points'] = nums
    player['onboarding_practice_submitted'] = True
    pname = player.get('display_name', player.get('name', ''))
    db.save_onboarding_practice_vote(session_id, pname, nums[0], nums[1], nums[2])
    gid = game_state.get('game_id')
    if gid and db.is_configured():
        db.link_onboarding_practice_vote_to_game(session_id, gid)
    emit('onboarding_practice_points_saved', {'success': True})
    notify_admin_player_list()

@socketio.on('restart_game')
def handle_restart_game():
    """Admin-only: Restart game for everyone, kick all non-admin players, and create a new game_id"""
    global admin_session_id
    session_id = session.get('session_id')
    
    # Check if player is admin
    if session_id != admin_session_id:
        emit('error', {'message': 'Only admin can restart game'})
        return
    
    # End current game in database if one exists
    if db.is_configured() and game_state.get('game_id'):
        current_round = game_state.get('current_round', 0)
        if current_round > 0:
            # Mark game as ended with rounds completed
            db.end_game(game_id=game_state['game_id'], rounds_completed=current_round)
            print(f"✅ Ended game {game_state['game_id']} in database before restart")
        # End current round if one exists
        if game_state.get('round_id'):
            db.end_round(game_state['round_id'])
            print(f"✅ Ended round {game_state['round_id']} in database before restart")
    
    # Reset game state (game_id will be None, so next start_game will create a new one)
    game_state['status'] = 'lobby'
    game_state['onboarding_phase'] = 'prompting'
    game_state['onboarding_prompting_end_time'] = None
    game_state['current_round'] = 0
    game_state['round_start_time'] = None
    game_state['round_end_time'] = None
    game_state['voting_start_time'] = None
    game_state['allocation_session_started_at'] = None
    game_state['allocation_experiment_finalized'] = False
    game_state['allocation_vignette_vrids'] = {}
    game_state['allocation_final_vrid'] = None
    game_state['allocation_vignette_submitters'] = {}
    game_state['allocation_emit_vrid'] = {}
    game_state['allocation_round_submitters'] = {}
    game_state['allocation_points_recorded'] = set()
    game_state['allocation_ballot_map'] = {}
    game_state['allocation_slot_owners'] = {}
    game_state['final_allocation_plan'] = None
    game_state['game_id'] = None  # This ensures a new game_id will be created on next start
    game_state['round_id'] = None
    game_state['post_survey_active'] = False
    game_state['last_game_over_payload'] = None
    game_state['_synthetic_prompt_seq'] = 0

    # Kick ALL players including admin - remove them from the game and require them to rejoin
    players_to_remove = []
    for sess_id, player in list(players.items()):
        players_to_remove.append(sess_id)
        # Remove from player_sessions mapping
        socket_ids_to_remove = [sid for sid, p_sess_id in player_sessions.items() if p_sess_id == sess_id]
        for sid in socket_ids_to_remove:
            if sid in player_sessions:
                del player_sessions[sid]
        # Notify player they've been kicked and need to rejoin
        if player.get('socket_id'):
            socketio.emit('game_restarted_kick', {
                'message': 'The game has been restarted. Please rejoin to continue.'
            }, room=player['socket_id'])
    
    # Clear all image data from players before deleting them (aggressive memory clearing)
    for sess_id in players_to_remove:
        if sess_id in players:
            player = players[sess_id]
            # Clear all image data from all rounds
            for round_num in [1, 2, 3]:
                if round_num in player.get('images', {}):
                    for img in player['images'][round_num]:
                        if 'image_data' in img:
                            del img['image_data']
                if round_num in player.get('selected_images', {}):
                    selected = player['selected_images'][round_num]
                    if isinstance(selected, dict) and 'image_data' in selected:
                        del selected['image_data']
    
    # Remove all players from dictionary (including admin)
    for sess_id in players_to_remove:
        if sess_id in players:
            del players[sess_id]
    
    # Force garbage collection after clearing all players
    gc.collect()
    print(f"[MEMORY] Garbage collection completed after game restart")
    
    # Clear admin_session_id
    admin_session_id = None
    
    # Broadcast updated lobby (empty)
    lobby_players = []
    socketio.emit('lobby_players_update', {'players': lobby_players})
    
    print(f"🔄 Game restarted by admin - cleared all {len(players_to_remove)} players (including admin), new game_id will be created on next start")

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

    ensure_post_survey_fields(player)
    hydrate_post_survey_from_db(player)
    if game_state.get('post_survey_active') and not player.get('post_survey_completed'):
        emit('error', {'message': 'Please complete the post-game survey before returning home.'})
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
    
    # Only clear if game is in lobby, onboarding, or game_over (after final leaderboard)
    if game_state['status'] not in ['lobby', 'game_over', 'onboarding']:
        emit('error', {'message': 'Can only clear lobby when game is in lobby, onboarding, or game over state'})
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
                socketio.emit('error', {'message': 'You have been removed from the lobby by admin'}, room=player['socket_id'])
                socketio.emit('return_to_lobby', {'message': 'Removed from lobby'}, room=player['socket_id'])
    
    # Remove players from dictionary
    for sess_id in players_to_remove:
        if sess_id in players:
            del players[sess_id]

    if game_state['status'] == 'onboarding' and len([p for p in players.values() if not p['is_admin']]) == 0:
        game_state['status'] = 'lobby'
        game_state['current_round'] = 0
        game_state['onboarding_phase'] = 'prompting'
        game_state['onboarding_prompting_end_time'] = None

    if len([p for p in players.values() if not p['is_admin']]) == 0:
        game_state['post_survey_active'] = False
        game_state['last_game_over_payload'] = None

    # Broadcast updated lobby
    lobby_players = [lobby_player_row(p) for p in players.values()]
    socketio.emit('lobby_players_update', {'players': lobby_players})
    notify_admin_player_list()
    
    print(f"Lobby cleared by admin - removed {len(players_to_remove)} players")

@socketio.on('remove_player')
def handle_remove_player(data):
    """Admin-only: Remove a specific player from the lobby"""
    session_id = session.get('session_id')
    
    # Check if player is admin
    if session_id != admin_session_id:
        emit('error', {'message': 'Only admin can remove players'})
        return
    
    if game_state['status'] not in ['lobby', 'onboarding']:
        emit('error', {'message': 'Can only remove players when game is in lobby or onboarding'})
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
        socketio.emit('error', {'message': 'You have been removed from the lobby by admin'}, room=player['socket_id'])
        socketio.emit('return_to_lobby', {'message': 'Removed from lobby'}, room=player['socket_id'])
    
    # Remove player from dictionary
    del players[target_session_id]

    if game_state['status'] == 'onboarding' and len([p for p in players.values() if not p['is_admin']]) == 0:
        game_state['status'] = 'lobby'
        game_state['current_round'] = 0
        game_state['onboarding_phase'] = 'prompting'
        game_state['onboarding_prompting_end_time'] = None
    
    # Broadcast updated lobby
    lobby_players = [lobby_player_row(p) for p in players.values()]
    socketio.emit('lobby_players_update', {'players': lobby_players})
    notify_admin_player_list()
    
    print(f"Player {player_name} (session: {target_session_id}) removed by admin")

@socketio.on('set_player_team')
def handle_set_player_team(data):
    """Admin-only: Manually set a player's team"""
    session_id = session.get('session_id')
    
    # Check if player is admin
    if session_id != admin_session_id:
        emit('error', {'message': 'Only admin can set player teams'})
        return

    if game_state['status'] not in ('lobby', 'onboarding'):
        emit('error', {'message': 'Group changes are only allowed in the lobby or during onboarding practice.'})
        return

    target_session_id = data.get('session_id')
    team = data.get('condition') or data.get('team')
    
    if not target_session_id or not team:
        emit('error', {'message': 'Missing session_id or condition'})
        return
    
    if team not in PLAYER_GROUPS:
        emit('error', {'message': f'Condition must be one of: {", ".join(PLAYER_GROUPS)}'})
        return
    
    # Check if player exists
    if target_session_id not in players:
        emit('error', {'message': 'Player not found'})
        return
    
    player = players[target_session_id]
    
    # Don't allow changing admin's team
    if player['is_admin']:
        emit('error', {'message': 'Cannot change admin team'})
        return
    
    # Set team and character
    player['condition'] = team
    player['character'] = get_character(team)
    
    # Update database if game has started
    if game_state.get('game_id') and db.is_configured():
        db.create_player(
            game_id=game_state['game_id'],
            player_id=target_session_id,
            player_name=player['name'],
            condition=team,
            character=player['character']
        )
    
    # Broadcast updated lobby
    lobby_players = [lobby_player_row(p) for p in players.values()]
    socketio.emit('lobby_players_update', {'players': lobby_players})
    notify_admin_player_list()
    
    print(f"Admin set player {player.get('display_name', player['name'])} to team {team}")

def set_player_team_console(target_session_id: str, team: str):
    """Console command: Set a player's team manually"""
    if team not in PLAYER_GROUPS:
        print(f"❌ ERROR: Team must be one of {list(PLAYER_GROUPS)}")
        return
    
    if target_session_id not in players:
        print(f"❌ ERROR: Player not found: {target_session_id}")
        return
    
    player = players[target_session_id]
    
    if player['is_admin']:
        print(f"❌ ERROR: Cannot change admin team")
        return
    
    # Set team and character
    player['condition'] = team
    player['character'] = get_character(team)
    
    # Update database if game has started
    if game_state.get('game_id') and db.is_configured():
        db.create_player(
            game_id=game_state['game_id'],
            player_id=target_session_id,
            player_name=player['name'],
            condition=team,
            character=player['character']
        )
    
    # Broadcast updated lobby
    lobby_players = [lobby_player_row(p) for p in players.values()]
    socketio.emit('lobby_players_update', {'players': lobby_players})
    notify_admin_player_list()
    
    print(f"✅ Set player {player.get('display_name', player['name'])} to team {team}")

# Console command functions for Railway admin controls
# 
# Usage from Railway console:
#   python -c "from app import *; skip_selection()"
#   python -c "from app import *; skip_voting_console()"
#   python -c "from app import *; next_round_console()"
#   python -c "from app import *; restart_game_console()"
#
# Or via HTTP POST (backup method):
#   curl -X POST https://your-app.railway.app/admin/console/skip-selection
#   curl -X POST https://your-app.railway.app/admin/console/skip-voting
#   curl -X POST https://your-app.railway.app/admin/console/next-round
#   curl -X POST https://your-app.railway.app/admin/console/restart-game
def skip_selection():
    """Console command: Skip image selection — same as admin Skip Voting during selection (next prompting or R3 allocation prep)."""
    if game_state['status'] == 'voting':
        print("[CONSOLE] Skipping selection screen — advancing via force_finish_image_selection_phase")
        return force_finish_image_selection_phase()
    else:
        print(f"[CONSOLE] Cannot skip selection - current status is {game_state['status']}, expected 'voting'")
        return False

def skip_voting_console():
    """Console command: Skip voting screen and go to round results"""
    if game_state['status'] == 'voting_images':
        print("[CONSOLE] Skipping voting screen, advancing to round results")
        show_round_results()
        return True
    else:
        print(f"[CONSOLE] Cannot skip voting - current status is {game_state['status']}, expected 'voting_images'")
        return False

def next_round_console():
    """Console command: Advance to next round or final leaderboard"""
    if game_state['status'] == 'awaiting_next_prompting':
        print('[CONSOLE] Advancing from awaiting_next_prompting via advance_to_next_prompting_round_after_selection')
        advance_to_next_prompting_round_after_selection()
        notify_admin_player_list()
        return True
    if game_state['status'] == 'round_results':
        if game_state['current_round'] < 3:
            print(f"[CONSOLE] Advancing from round {game_state['current_round']} to next round")
            # Reuse the existing handle_next_round logic
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
                    p['prompt_count'] = 0
                    p['has_successful_prompt'][round_num] = False

            # Send game started to players only (not admin) - must check socket_id for socketio.emit too
            for p in players.values():
                if not p['is_admin']:
                    socket_id = p.get('socket_id')
                    if socket_id:  # Only send if player is connected
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

                        _gs = {
                            'round': game_state['current_round'],
                            'target': game_state['current_target'],
                            'end_time': game_state['round_end_time'],
                            'character': character_data,
                            'image_context_bullets': player_gets_image_context_bullets(p),
                        }
                        _gs.update(game_started_aggregate_heuristic_fields(p))
                        socketio.emit('game_started', _gs, room=socket_id)
            
            # Send admin game started event
            if admin_session_id in players and players[admin_session_id].get('socket_id'):
                time_remaining = game_state['round_end_time'] - time.time() if game_state.get('round_end_time') else None
                socketio.emit('admin_game_started', {
                    'round': game_state['current_round'],
                    'target': game_state['current_target'],
                    'time_remaining': time_remaining,
                    'game_id': game_state.get('game_id'),
                    'players': [{
                        'name': p.get('display_name', p['name']),
                        'condition': p['condition'],
                        'is_connected': p.get('socket_id') is not None,
                        'session_id': p['session_id'],
                        'seat_number': admin_seat_number_for_payload(p),
                        'score': p['score'],
                        'prompts_submitted': len(p['images'].get(game_state['current_round'], []))
                    } for p in players.values() if not p['is_admin']]
                }, room=players[admin_session_id]['socket_id'])
            return True
        else:
            print("[CONSOLE] All rounds complete, advancing to final leaderboard")
            end_game()
            return True
    else:
        print(f"[CONSOLE] Cannot advance round - current status is {game_state['status']}, expected 'round_results'")
        return False

def restart_game_console():
    """Console command: Restart game and clear all players including admin"""
    print("[CONSOLE] Restarting game and clearing all players")
    # End current game in database if one exists
    if db.is_configured() and game_state.get('game_id'):
        current_round = game_state.get('current_round', 0)
        if current_round > 0:
            db.end_game(game_id=game_state['game_id'], rounds_completed=current_round)
        if game_state.get('round_id'):
            db.end_round(game_state['round_id'])
    
    # Reset game state
    game_state['status'] = 'lobby'
    game_state['onboarding_phase'] = 'prompting'
    game_state['onboarding_prompting_end_time'] = None
    game_state['current_round'] = 0
    game_state['round_start_time'] = None
    game_state['round_end_time'] = None
    game_state['voting_start_time'] = None
    game_state['game_id'] = None
    game_state['round_id'] = None
    game_state['post_survey_active'] = False
    game_state['last_game_over_payload'] = None

    # Kick ALL players including admin
    global admin_session_id
    players_to_remove = []
    for sess_id, player in list(players.items()):
        players_to_remove.append(sess_id)
        socket_ids_to_remove = [sid for sid, p_sess_id in player_sessions.items() if p_sess_id == sess_id]
        for sid in socket_ids_to_remove:
            if sid in player_sessions:
                del player_sessions[sid]
        if player.get('socket_id'):
            socketio.emit('game_restarted_kick', {
                'message': 'The game has been restarted. Please rejoin to continue.'
            }, room=player['socket_id'])
    
    # Remove all players from dictionary
    for sess_id in players_to_remove:
        if sess_id in players:
            del players[sess_id]
    
    # Clear admin_session_id
    admin_session_id = None
    
    # Broadcast updated lobby (empty)
    lobby_players = []
    socketio.emit('lobby_players_update', {'players': lobby_players})
    
    print(f"[CONSOLE] Game restarted - cleared all {len(players_to_remove)} players (including admin)")
    return True

# Flask routes for HTTP-based console commands (backup method)
@app.route('/admin/console/skip-selection', methods=['POST'])
def console_skip_selection():
    """HTTP endpoint for skipping selection screen"""
    result = skip_selection()
    return {'success': result, 'status': game_state['status']}, 200 if result else 400

@app.route('/admin/console/skip-voting', methods=['POST'])
def console_skip_voting():
    """HTTP endpoint for skipping voting screen"""
    result = skip_voting_console()
    return {'success': result, 'status': game_state['status']}, 200 if result else 400

@app.route('/admin/console/next-round', methods=['POST'])
def console_next_round():
    """HTTP endpoint for advancing to next round"""
    result = next_round_console()
    return {'success': result, 'status': game_state['status'], 'round': game_state['current_round']}, 200 if result else 400

@app.route('/admin/console/restart-game', methods=['POST'])
def console_restart_game():
    """HTTP endpoint for restarting game"""
    result = restart_game_console()
    return {'success': result, 'status': game_state['status']}, 200 if result else 400

@app.route('/admin/console/set-player-team', methods=['POST'])
def console_set_player_team():
    """HTTP endpoint for setting player team"""
    import json
    data = request.get_json() or {}
    target_session_id = data.get('session_id')
    team = data.get('condition') or data.get('team')
    if not target_session_id or not team:
        return {'success': False, 'error': 'Missing session_id or condition'}, 400
    set_player_team_console(target_session_id, team)
    return {'success': True}

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
    # Allow unsafe werkzeug in production for Railway (which runs app directly)
    # PORT environment variable is set by Railway, indicating we're on a platform that needs this
    allow_unsafe_werkzeug = debug or os.environ.get('PORT') is not None
    socketio.run(app, host='0.0.0.0', port=port, debug=debug, allow_unsafe_werkzeug=allow_unsafe_werkzeug)
