from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import time
import os
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

def calculate_accuracy(expected, actual):
    """Calculate typing accuracy percentage with harsh penalties for short submissions."""
    if len(expected) == 0:
        return 100

    # Heavily penalize empty or very short submissions
    if len(actual) == 0:
        return 0

    # If submission is less than 20% of expected length, cap accuracy at 20%
    if len(actual) < len(expected) * 0.2:
        return min(20, (len(actual) / len(expected)) * 100)

    # Character-by-character comparison
    matches = sum(1 for e, a in zip(expected, actual) if e == a)

    # Penalize length differences more heavily
    expected_len = len(expected)
    actual_len = len(actual)

    # Base accuracy from character matches
    base_accuracy = matches / expected_len * 100

    # Apply length penalty
    if actual_len != expected_len:
        length_penalty = abs(actual_len - expected_len) / expected_len
        length_penalty = min(0.5, length_penalty)  # Cap penalty at 50%
        base_accuracy = base_accuracy * (1 - length_penalty)

    return round(max(0, base_accuracy), 2)

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

    # Get snippet and calculate results
    snippet = get_snippet(current_round)
    typed_code = data.get('code', '')
    time_taken = time.time() - player['start_time']

    accuracy = calculate_accuracy(snippet['code'], typed_code)
    wpm = calculate_wpm(len(snippet['code']), time_taken)
    score_breakdown = calculate_score_breakdown(snippet['points'], time_taken, accuracy)
    round_score = score_breakdown['final_score']

    # Update player stats
    player['score'] += round_score
    player['round_complete'] = True

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
