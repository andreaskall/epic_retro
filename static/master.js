// Initialize Socket.IO
const socket = io();

// State
let gameStarted = false;
let players = [];
let currentRound = 0;
let totalRounds = 10;
let timeLimit = 90; // Default 90 seconds

// DOM Elements
const pregameSection = document.getElementById('pregame-section');
const gameSection = document.getElementById('game-section');
const playerCountEl = document.getElementById('player-count');
const startGameBtn = document.getElementById('start-game-btn');
const timeLimitSelect = document.getElementById('time-limit');

const currentRoundNum = document.getElementById('current-round-num');
const totalRoundsNum = document.getElementById('total-rounds-num');
const completionStatus = document.getElementById('completion-status');
const nextRoundBtn = document.getElementById('next-round-btn');

const statPlayers = document.getElementById('stat-players');
const statCompleted = document.getElementById('stat-completed');
const statInProgress = document.getElementById('stat-in-progress');
const statTopScore = document.getElementById('stat-top-score');

const playerGrid = document.getElementById('player-grid');

// Event Listeners
startGameBtn.addEventListener('click', startGame);
nextRoundBtn.addEventListener('click', nextRound);

// Socket Events
socket.on('connect', () => {
    console.log('Game master connected');
    socket.emit('join_master', {});
});

socket.on('master_joined', (data) => {
    console.log('Master joined successfully');
    players = data.players || [];
    updatePreGameDisplay();
});

socket.on('player_joined', (data) => {
    console.log(`Player joined: ${data.name}`);
});

socket.on('update_master', (data) => {
    players = data.players || [];
    if (gameStarted) {
        updateGameDisplay();
    } else {
        updatePreGameDisplay();
    }
});

socket.on('game_started_master', (data) => {
    gameStarted = true;
    currentRound = data.current_round;
    totalRounds = data.total_rounds;
    showGameSection();
    updateGameDisplay();
});

socket.on('round_advanced', (data) => {
    currentRound = data.current_round;
    updateGameDisplay();
});

socket.on('game_over_master', () => {
    nextRoundBtn.disabled = true;
    nextRoundBtn.textContent = 'Game Over';
});

// Functions
function startGame() {
    if (players.length === 0) {
        alert('No players connected yet!');
        return;
    }

    timeLimit = parseInt(timeLimitSelect.value);

    if (confirm(`Start game with ${players.length} player(s) and ${timeLimit > 0 ? timeLimit + ' second' : 'no'} time limit?`)) {
        socket.emit('start_game', { timeLimit: timeLimit });
    }
}

function nextRound() {
    if (confirm('Advance to next round?')) {
        socket.emit('next_round');
    }
}

function updatePreGameDisplay() {
    const count = players.length;
    playerCountEl.textContent = `${count} player${count !== 1 ? 's' : ''} connected`;
    startGameBtn.disabled = count === 0;
}

function updateGameDisplay() {
    // Update round info
    currentRoundNum.textContent = currentRound;
    totalRoundsNum.textContent = totalRounds;

    // Update stats
    const totalPlayers = players.length;
    const completedPlayers = players.filter(p => p.round_complete).length;
    const inProgressPlayers = totalPlayers - completedPlayers;
    const topScore = totalPlayers > 0
        ? Math.max(...players.map(p => p.score))
        : 0;

    completionStatus.textContent = `${completedPlayers} of ${totalPlayers} players completed`;
    statPlayers.textContent = totalPlayers;
    statCompleted.textContent = completedPlayers;
    statInProgress.textContent = inProgressPlayers;
    statTopScore.textContent = topScore;

    // Enable/disable next round button
    if (currentRound >= totalRounds) {
        nextRoundBtn.disabled = true;
        nextRoundBtn.textContent = 'Game Complete';
    } else {
        nextRoundBtn.disabled = false;
        nextRoundBtn.textContent = completedPlayers === totalPlayers ? 'Next Round (All Ready!)' : 'Next Round';
    }

    // Update player grid
    updatePlayerGrid();
}

function updatePlayerGrid() {
    if (players.length === 0) {
        playerGrid.innerHTML = '<p style="text-align: center; color: #718096;">No players yet...</p>';
        return;
    }

    // Sort by score descending
    const sortedPlayers = [...players].sort((a, b) => b.score - a.score);

    playerGrid.innerHTML = sortedPlayers.map(player => {
        const isCompleted = player.round_complete;
        const isFinished = player.current_round > player.total_rounds;

        let statusClass = 'status-playing';
        let statusText = 'Playing';

        if (isFinished) {
            statusClass = 'status-finished';
            statusText = 'All Done!';
        } else if (isCompleted) {
            statusClass = 'status-completed';
            statusText = 'Completed ✓';
        }

        return `
            <div class="player-card ${isFinished ? 'finished' : ''}">
                <div class="player-header">
                    <div class="player-name">${player.name}</div>
                    <div class="player-status ${statusClass}">
                        ${statusText}
                    </div>
                </div>

                <div class="player-stats">
                    <div class="stat-item">
                        <div class="stat-item-label">Score</div>
                        <div class="stat-item-value">${player.score}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-item-label">Round</div>
                        <div class="stat-item-value">${Math.min(player.current_round, player.total_rounds)}/${player.total_rounds}</div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function showGameSection() {
    pregameSection.classList.add('hidden');
    gameSection.classList.remove('hidden');
}

// Auto-refresh player data every 2 seconds
setInterval(() => {
    if (gameStarted) {
        updateGameDisplay();
    }
}, 2000);
