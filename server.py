from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import time
import os
import unicodedata
import re
from code_snippets import get_snippet, get_total_rounds

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here-change-in-production')
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Game state
game_state = {
    'players': {},  # {socket_id: {name, score, current_round, start_time, round_complete}}
    'game_started': False,
    'current_round': 0,  # Global round that master controls
    'total_rounds': get_total_rounds(),
    'game_master': None  # Socket ID of the game master
}

def calculate_score_breakdown(snippet_points, time_taken, accuracy):
    """
    Calculate detailed score breakdown based heavily on accuracy, with speed bonus only for high accuracy.
    accuracy: 0-100
    Returns: dict with detailed breakdown
    """
    # Exponential accuracy curve - heavily penalizes low accuracy
    if accuracy < 20:
        accuracy_mult = 0.01  # Only 1% of points for very low accuracy
        accuracy_tier = "Terrible"
    elif accuracy < 40:
        accuracy_mult = 0.05  # 5% for poor accuracy
        accuracy_tier = "Poor"
    elif accuracy < 60:
        accuracy_mult = 0.20  # 20% for mediocre accuracy
        accuracy_tier = "Mediocre"
    elif accuracy < 80:
        accuracy_mult = 0.50  # 50% for good accuracy
        accuracy_tier = "Good"
    elif accuracy < 95:
        accuracy_mult = 0.80  # 80% for very good accuracy
        accuracy_tier = "Very Good"
    else:
        accuracy_mult = 1.0   # Full points for excellent accuracy
        accuracy_tier = "Excellent"

    # Calculate base points from accuracy
    base_points = int(snippet_points * accuracy_mult)

    # Speed bonus only applies to high accuracy (>70%)
    speed_mult = 1.0
    speed_bonus = 0
    speed_eligible = accuracy > 70 and time_taken < 30

    if speed_eligible:
        speed_mult = 1.0 + (30 - time_taken) / 30 * 0.5  # Up to 50% bonus for fast + accurate
        speed_bonus = int(base_points * (speed_mult - 1.0))

    final_score = max(1, base_points + speed_bonus)  # Minimum 1 point to avoid zero

    return {
        'final_score': final_score,
        'max_possible': snippet_points,
        'base_points': base_points,
        'speed_bonus': speed_bonus,
        'accuracy_mult': accuracy_mult,
        'accuracy_tier': accuracy_tier,
        'speed_eligible': speed_eligible,
        'speed_mult': speed_mult
    }

def _normalize_text(s):
    """Normalize text for fair comparison:
    - Normalize Unicode (NFC)
    - Normalize line endings to LF
    - Strip trailing whitespace on each line
    - Collapse multiple internal spaces is intentionally avoided for code, but could be enabled
    """
    if s is None:
        s = ''
    # Normalize unicode and line endings
    s = unicodedata.normalize('NFC', s)
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    # Strip trailing whitespace from each line (invisible differences)
    lines = [line.rstrip() for line in s.split('\n')]
    return '\n'.join(lines)


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein edit distance (characters)."""
    if a == b:
        return 0
    na, nb = len(a), len(b)
    if na == 0:
        return nb
    if nb == 0:
        return na
    # Use a single-row DP for memory efficiency
    prev = list(range(nb + 1))
    for i in range(1, na + 1):
        cur = [i] + [0] * nb
        ai = a[i - 1]
        for j in range(1, nb + 1):
            cost = 0 if ai == b[j - 1] else 1
            cur[j] = min(prev[j] + 1,      # deletion
                         cur[j - 1] + 1,   # insertion
                         prev[j - 1] + cost)  # substitution
        prev = cur
    return prev[nb]


def calculate_accuracy(expected, actual):
    """Calculate typing accuracy as a normalized edit-similarity percentage.

    Improvements over prior implementation:
    - Normalizes unicode and line endings and strips trailing whitespace per-line
    - Uses character-level Levenshtein distance to compute similarity
    - Preserves a conservative short-submission cap: if actual is <20% of expected length,
      we cap reported accuracy at 20% (to discourage empty/abbreviated submissions), but
      we otherwise return the edit-based similarity which is more robust to small differences
      such as missing trailing newline or different trailing spaces.
    """
    exp = _normalize_text(expected)
    act = _normalize_text(actual)

    if len(exp) == 0:
        return 100.0

    if len(act) == 0:
        return 0.0

    # Exact match (fast path)
    if exp == act:
        return 100.0

    ed = _levenshtein(exp, act)
    # Use the longer length to normalize distance so extra/short content is penalized
    denom = max(len(exp), len(act))
    similarity = max(0.0, 1.0 - (ed / denom))
    accuracy = round(similarity * 100.0, 2)

    # Cap accuracy for very short submissions relative to expected length
    if len(act) < len(exp) * 0.2:
        accuracy = min(accuracy, 20.0)

    return accuracy

def calculate_wpm(text_length, time_taken):
    """Calculate words per minute (using standard 5 chars = 1 word)."""
    if time_taken == 0:
        return 0
    words = text_length / 5
    minutes = time_taken / 60
    return round(words / minutes, 1)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/master')
def master():
    return render_template('master.html')

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')
    emit('game_state', {
        'total_rounds': game_state['total_rounds'],
        'game_started': game_state['game_started']
    })

@socketio.on('disconnect')
def handle_disconnect():
    player_name = game_state['players'].get(request.sid, {}).get('name', 'Unknown')
    if request.sid in game_state['players']:
        del game_state['players'][request.sid]
        print(f'{player_name} disconnected')
        emit('player_left', {'name': player_name}, broadcast=True)
        emit('update_players', {'players': get_player_list()}, broadcast=True)

@socketio.on('join_game')
def handle_join(data):
    player_name = data.get('name', 'Anonymous')
    game_state['players'][request.sid] = {
        'name': player_name,
        'score': 0,
        'current_round': 0,
        'start_time': None,
        'round_complete': False
    }
    print(f'{player_name} joined the game')
    emit('join_success', {'name': player_name})
    emit('player_joined', {'name': player_name}, broadcast=True)
    broadcast_player_update()

@socketio.on('join_master')
def handle_join_master(data):
    game_state['game_master'] = request.sid
    print(f'Game master connected: {request.sid}')
    emit('master_joined', {'players': get_player_list()})

@socketio.on('start_game')
def handle_start_game(data=None):
    # Only game master can start
    if request.sid != game_state['game_master']:
        emit('error', {'message': 'Only game master can start the game'})
        return

    if game_state['game_started']:
        emit('error', {'message': 'Game already started'})
        return

    # Get time limit from master (default 0 = no limit)
    time_limit = 0
    if data and 'timeLimit' in data:
        time_limit = data['timeLimit']

    game_state['game_started'] = True
    game_state['current_round'] = 1
    game_state['time_limit'] = time_limit

    # Initialize each player to round 1
    for player in game_state['players'].values():
        player['current_round'] = 1
        player['start_time'] = time.time()
        player['round_complete'] = False

    # Send each player their first round
    for sid, player in game_state['players'].items():
        snippet = get_snippet(1)
        # store the exact snippet (code and points) that was sent to this player
        game_state['players'][sid]['expected_snippet'] = snippet['code']
        game_state['players'][sid]['expected_points'] = snippet['points']
        socketio.emit('game_started', {
            'round': 1,
            'total_rounds': game_state['total_rounds'],
            'snippet': snippet,
            'timeLimit': time_limit
        }, room=sid)

    # Notify game master
    if game_state['game_master']:
        socketio.emit('game_started_master', {
            'current_round': 1,
            'total_rounds': game_state['total_rounds']
        }, room=game_state['game_master'])

    print(f'Game started by master! Time limit: {time_limit}s')

@socketio.on('next_round')
def handle_next_round():
    # Only game master can advance rounds
    if request.sid != game_state['game_master']:
        emit('error', {'message': 'Only game master can advance rounds'})
        return

    if not game_state['game_started']:
        emit('error', {'message': 'Game not started'})
        return

    if game_state['current_round'] >= game_state['total_rounds']:
        # Game over
        game_state['game_started'] = False
        socketio.emit('game_over', {'leaderboard': get_leaderboard()})
        if game_state['game_master']:
            socketio.emit('game_over_master', {}, room=game_state['game_master'])
        print('Game over!')
        return

    # Advance to next round
    game_state['current_round'] += 1

    # Reset all players for new round
    for player in game_state['players'].values():
        player['current_round'] = game_state['current_round']
        player['start_time'] = time.time()
        player['round_complete'] = False

    # Send new round to all players
    snippet = get_snippet(game_state['current_round'])
    for sid in game_state['players'].keys():
        # store the exact snippet sent to each player so scoring is deterministic
        game_state['players'][sid]['expected_snippet'] = snippet['code']
        game_state['players'][sid]['expected_points'] = snippet['points']
        socketio.emit('new_round', {
            'round': game_state['current_round'],
            'total_rounds': game_state['total_rounds'],
            'snippet': snippet,
            'timeLimit': game_state.get('time_limit', 0)
        }, room=sid)

    # Notify game master
    if game_state['game_master']:
        socketio.emit('round_advanced', {
            'current_round': game_state['current_round'],
            'total_rounds': game_state['total_rounds']
        }, room=game_state['game_master'])

    # Immediately update master with cleared player statuses
    broadcast_player_update()

    print(f'Master advanced to round {game_state["current_round"]}')

@socketio.on('submit_code')
def handle_submit(data):
    if not game_state['game_started']:
        emit('error', {'message': 'Game not started'})
        return

    player = game_state['players'].get(request.sid)
    if not player:
        emit('error', {'message': 'Player not found'})
        return

    if player['round_complete']:
        emit('error', {'message': 'Already completed this round. Waiting for master to advance.'})
        return

    current_round = player['current_round']
    if current_round == 0:
        emit('error', {'message': 'No active round'})
        return

    if current_round > game_state['total_rounds']:
        emit('error', {'message': 'All rounds completed'})
        return

    # Get the typed code and time taken
    typed_code = data.get('code', '')
    time_taken = time.time() - player['start_time']

    # Use the exact snippet that was sent to this player (prevent variation mismatch)
    expected_code = player.get('expected_snippet')
    snippet_points = player.get('expected_points')
    # Fallback: if for some reason we don't have stored snippet, fetch one and store it now
    if expected_code is None or snippet_points is None:
        fetched = get_snippet(current_round)
        if fetched:
            expected_code = fetched['code']
            snippet_points = fetched['points']
            player['expected_snippet'] = expected_code
            player['expected_points'] = snippet_points
        else:
            expected_code = ''
            snippet_points = 0

    accuracy = calculate_accuracy(expected_code, typed_code)
    wpm = calculate_wpm(len(expected_code), time_taken)
    score_breakdown = calculate_score_breakdown(snippet_points, time_taken, accuracy)
    round_score = score_breakdown['final_score']

    # Server-side simple cheat detection: detect paste-like impossible speeds
    try:
        # Flagged if WPM extremely high (e.g., > 200) and accuracy is suspiciously perfect
        if wpm > 200 and accuracy > 95:
            player['flagged_cheating'] = True
            print(f"Cheat detected for player {player.get('name')} - WPM: {wpm}, Accuracy: {accuracy}")
            if game_state.get('game_master'):
                socketio.emit('cheat_detected', {
                    'player': player.get('name'),
                    'wpm': wpm,
                    'accuracy': accuracy,
                    'round': current_round
                }, room=game_state['game_master'])
    except Exception:
        pass

    # Debugging: if accuracy unexpectedly low, log normalized/raw forms and edit distance
    try:
        if accuracy < 90:
            exp_norm = _normalize_text(expected_code)
            act_norm = _normalize_text(typed_code)
            ed = _levenshtein(exp_norm, act_norm)
            print('--- MISMATCH DEBUG ---')
            print('Player:', game_state['players'].get(request.sid, {}).get('name'))
            print('Round:', current_round)
            print('Accuracy:', accuracy)
            print('Expected repr:', repr(expected_code))
            print('Submitted repr:', repr(typed_code))
            print('Normalized expected repr:', repr(exp_norm))
            print('Normalized submitted repr:', repr(act_norm))
            print('Lengths expected/submitted (raw):', len(expected_code), len(typed_code))
            print('Lengths expected/submitted (norm):', len(exp_norm), len(act_norm))
            print('Levenshtein(normalized):', ed)
            print('--- END MISMATCH DEBUG ---')
            # Also notify master if connected so they can inspect quickly
            if game_state.get('game_master'):
                socketio.emit('mismatch_debug', {
                    'player': game_state['players'].get(request.sid, {}).get('name'),
                    'round': current_round,
                    'accuracy': accuracy,
                    'expected': repr(expected_code),
                    'submitted': repr(typed_code),
                    'normalized_expected': repr(exp_norm),
                    'normalized_submitted': repr(act_norm),
                    'levenshtein': ed
                }, room=game_state['game_master'])
    except Exception as e:
        print('Error during mismatch debug logging:', e)

    # Update player stats
    player['score'] += round_score
    player['round_complete'] = True

    # Clear the stored expected snippet to avoid accidental reuse
    try:
        if 'expected_snippet' in player:
            del player['expected_snippet']
        if 'expected_points' in player:
            del player['expected_points']
    except Exception:
        pass

    # Send detailed result to player
    emit('round_result', {
        'round': current_round,
        'score': round_score,
        'total_score': player['score'],
        'accuracy': accuracy,
        'wpm': wpm,
        'time': round(time_taken, 2),
        'breakdown': score_breakdown
    })

    print(f'{player["name"]} completed round {current_round}: {round_score} points')

    # Don't advance player automatically - wait for master
    # Just mark round as complete

    # Broadcast updates
    broadcast_player_update()



@socketio.on('get_leaderboard')
def handle_get_leaderboard():
    emit('update_leaderboard', {'leaderboard': get_leaderboard()})


@socketio.on('paste_detected')
def handle_paste_detected():
    """Client reported a paste attempt (or paste prevented). Flag player for moderation and notify master."""
    player = game_state['players'].get(request.sid)
    name = player.get('name') if player else 'Unknown'
    print(f'Paste detected from player {name} ({request.sid})')
    if player is not None:
        player['paste_attempt'] = True
    if game_state.get('game_master'):
        socketio.emit('paste_detected', {'player': name}, room=game_state['game_master'])


@socketio.on('copy_attempt')
def handle_copy_attempt():
    player = game_state['players'].get(request.sid)
    name = player.get('name') if player else 'Unknown'
    print(f'Copy attempt detected from player {name} ({request.sid})')
    if player is not None:
        player['copy_attempt'] = True
    if game_state.get('game_master'):
        socketio.emit('copy_attempt', {'player': name}, room=game_state['game_master'])

def get_player_list():
    """Get list of players with detailed info for game master."""
    return [
        {
            'name': player['name'],
            'score': player['score'],
            'current_round': player['current_round'],
            'total_rounds': game_state['total_rounds'],
            'round_complete': player.get('round_complete', False)
        }
        for player in game_state['players'].values()
    ]


@socketio.on('reset_players')
def handle_reset_players():
    """Reset scores and rounds for all players. Only the game master may invoke this."""
    if request.sid != game_state.get('game_master'):
        emit('error', {'message': 'Only game master can reset players'})
        return

    for player in game_state['players'].values():
        player['score'] = 0
        player['current_round'] = 0
        player['start_time'] = None
        player['round_complete'] = False

    # Stop the current game and reset global round state
    game_state['game_started'] = False
    game_state['current_round'] = 0

    # Broadcast update so clients and master refresh
    broadcast_player_update()
    # Include the updated player list so master can immediately switch to setup view
    players_list = get_player_list()
    socketio.emit('players_reset', {'players': players_list, 'total_rounds': game_state['total_rounds']})
    # Some clients may not respond to the custom event in certain browsers — also emit a simple 'force_lobby' event
    socketio.emit('force_lobby', {})
    print(f'Game master reset all players (broadcasted to {len(players_list)} players)')


@socketio.on('reset_server')
def handle_reset_server():
    """Reset entire server state (clear players, stop game). Only the game master may invoke this."""
    if request.sid != game_state.get('game_master'):
        emit('error', {'message': 'Only game master can reset the server'})
        return

    # Clear players and reset global state
    game_state['players'].clear()
    game_state['game_started'] = False
    game_state['current_round'] = 0
    game_state['total_rounds'] = get_total_rounds()
    game_state['game_master'] = None

    # Notify everyone and ask clients to reload/handle reset
    socketio.emit('server_reset', {})
    print('Game master reset the entire server')

def get_leaderboard():
    """Get sorted leaderboard."""
    players = [
        {
            'name': player['name'],
            'score': player['score'],
            'current_round': player['current_round']
        }
        for player in game_state['players'].values()
    ]
    return sorted(players, key=lambda x: x['score'], reverse=True)

def broadcast_player_update():
    """Broadcast player updates to all clients and game master."""
    leaderboard = get_leaderboard()
    player_list = get_player_list()

    # Update players
    socketio.emit('update_leaderboard', {'leaderboard': leaderboard})

    # Update game master
    if game_state['game_master']:
        socketio.emit('update_master', {'players': player_list}, room=game_state['game_master'])

if __name__ == '__main__':
    import os

    # Production settings
    debug_mode = os.getenv('FLASK_ENV') != 'production'
    port = int(os.getenv('PORT', 5000))

    if debug_mode:
        print('Starting Code Typing Speed Championship Server...')
        print(f'Open http://localhost:{port} in your browser')
    else:
        print(f'Starting production server on port {port}')

    socketio.run(app, host='0.0.0.0', port=port, debug=debug_mode, allow_unsafe_werkzeug=True)
