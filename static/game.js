// Initialize Socket.IO
const socket = io();

// Game state
let currentPlayer = null;
let currentRound = 0;
let totalRounds = 10;
let roundStartTime = null;
let timeLimit = 0; // 0 means no time limit
let countdownTimer = null;
// Current snippet stored client-side for live projection
let currentSnippetCode = '';
let currentSnippetPoints = 0;
let lastInputValue = '';

// DOM Elements
const joinScreen = document.getElementById('join-screen');
const lobbyScreen = document.getElementById('lobby-screen');
const gameScreen = document.getElementById('game-screen');
const waitingScreen = document.getElementById('waiting-screen');
const gameoverScreen = document.getElementById('gameover-screen');

const playerNameInput = document.getElementById('player-name');
const joinBtn = document.getElementById('join-btn');
const welcomeName = document.getElementById('welcome-name');
const playerList = document.getElementById('player-list');
const startBtn = document.getElementById('start-btn');

const roundInfo = document.getElementById('round-info');
const currentRoundSpan = document.getElementById('current-round');
const totalRoundsSpan = document.getElementById('total-rounds');

const languageLabel = document.getElementById('language-label');
const pointsLabel = document.getElementById('points-label');
const codeDisplay = document.getElementById('code-display');
const codeInput = document.getElementById('code-input');
const submitBtn = document.getElementById('submit-btn');
const feedback = document.getElementById('feedback');
const leaderboard = document.getElementById('leaderboard');

const countdownElement = document.getElementById('countdown-timer');
const timerText = document.getElementById('timer-text');

const roundResults = document.getElementById('round-results');
const waitingLeaderboard = document.getElementById('waiting-leaderboard');

const finalLeaderboard = document.getElementById('final-leaderboard');
const playAgainBtn = document.getElementById('play-again-btn');

// Event Listeners
joinBtn.addEventListener('click', joinGame);
playerNameInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') joinGame();
});

submitBtn.addEventListener('click', submitCode);
playAgainBtn.addEventListener('click', () => location.reload());

// Live input handler: hide feedback, update hero meter, and spawn particle on inserted chars
codeInput.addEventListener('input', (e) => {
    feedback.classList.add('hidden');
    try {
        updateHeroMeter();

        // detect insertion vs deletion
        const newVal = codeInput.value || '';
        if (newVal.length > lastInputValue.length) {
            // spawn a flying particle near the input area to celebrate typing
            spawnParticle('✨');
        }
        lastInputValue = newVal;
    } catch (err) {
        console.warn('Hero meter update failed', err);
    }
});

/**
 * Compute Levenshtein distance (chars)
 */
function levenshtein(a, b) {
    if (a === b) return 0;
    const na = a.length, nb = b.length;
    if (na === 0) return nb;
    if (nb === 0) return na;
    let prev = new Array(nb + 1);
    for (let j = 0; j <= nb; j++) prev[j] = j;
    for (let i = 1; i <= na; i++) {
        let cur = [i];
        for (let j = 1; j <= nb; j++) {
            const cost = a.charAt(i - 1) === b.charAt(j - 1) ? 0 : 1;
            cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
        }
        prev = cur;
    }
    return prev[nb];
}

function mapAccuracyToMultiplier(acc) {
    if (acc < 20) return 0.01;
    if (acc < 40) return 0.05;
    if (acc < 60) return 0.20;
    if (acc < 80) return 0.50;
    if (acc < 95) return 0.80;
    return 1.0;
}

function normalizeText(s) {
    if (!s) return '';
    // simple normalization: collapse CRLF, trim trailing spaces per line
    s = s.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    return s.split('\n').map(l => l.replace(/\s+$/,'')).join('\n');
}

function updateHeroMeter() {
    const expected = normalizeText(currentSnippetCode || codeDisplay.textContent || '');
    const actual = normalizeText(codeInput.value || '');
    if (!expected) return;
    // exact match fast path
    let accuracy = 0;
    if (expected === actual) accuracy = 100;
    else {
        const ed = levenshtein(expected, actual);
        const denom = Math.max(expected.length, actual.length || 1);
        accuracy = Math.max(0, Math.round((1 - ed / denom) * 100));
    }

    // map to server-style accuracy multiplier and compute projected base points
    const accMult = mapAccuracyToMultiplier(accuracy);
    const projBase = Math.max(1, Math.floor((currentSnippetPoints || parseInt(pointsLabel.textContent.replace(/\D/g,'')) || 0) * accMult));

    // Update meter UI
    const fill = document.getElementById('meter-fill');
    const projText = document.getElementById('projected-points');
    if (fill) fill.style.width = `${Math.min(100, accuracy)}%`;
    if (projText) projText.textContent = projBase;

    // small avatar reaction for great accuracy
    const avatar = document.querySelector('.hero-avatar');
    if (avatar) {
        if (accuracy > 95) {
            avatar.style.transform = 'scale(1.08)';
            setTimeout(() => avatar.style.transform = '', 220);
        }
    }
}

function spawnParticle(char) {
    const p = document.createElement('div');
    p.className = 'particle';
    p.textContent = char;
    document.body.appendChild(p);
    // position near the input: random x within input rect, at bottom of input
    const rect = codeInput.getBoundingClientRect();
    const x = rect.left + Math.random() * rect.width;
    const y = rect.top + rect.height - 10;
    p.style.left = `${x}px`;
    p.style.top = `${y}px`;
    // remove after animation
    setTimeout(() => { try { p.remove(); } catch (e) {} }, 900);
}

// Anti-cheat UI: make the displayed snippet harder to copy
// These are client-side deterrents only (not foolproof). Server-side checks are enforced too.
try {
    // Disable text selection on the displayed snippet
    codeDisplay.style.userSelect = 'none';
    codeDisplay.style.webkitUserSelect = 'none';
    codeDisplay.style.msUserSelect = 'none';

    // Prevent right-click / context menu on snippet
    codeDisplay.addEventListener('contextmenu', (e) => e.preventDefault());

    // Prevent copy/cut events on the snippet element
    codeDisplay.addEventListener('copy', (e) => {
        e.preventDefault();
        showFeedback('Copying the snippet is disabled to keep the game fair.', 'error');
        // Optionally notify server that a copy attempt was made (for moderation)
        socket.emit('copy_attempt');
    });
    codeDisplay.addEventListener('cut', (e) => {
        e.preventDefault();
        socket.emit('copy_attempt');
    });
} catch (err) {
    console.warn('Anti-cheat snippet protections not fully supported in this browser', err);
}

// Prevent pasting into the typing area and notify server when attempted
codeInput.addEventListener('paste', (e) => {
    e.preventDefault();
    showFeedback('Pasting is disabled. Please type the snippet manually.', 'error');
    socket.emit('paste_detected');
});

// Add keyboard shortcut for submit (Ctrl+Enter)
codeInput.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') {
        e.preventDefault();
        e.stopPropagation();
        if (!submitBtn.disabled) {
            submitCode();
        }
    }
});


// Also listen for the shortcut globally in case user is not in the text area
document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') {
        e.preventDefault();
        // Only submit if we're on the game screen and submit button is enabled
        if (!gameScreen.classList.contains('hidden') && !submitBtn.disabled) {
            submitCode();
        }
    }
});

/* Matrix backdrop animation
   Lightweight canvas animation that renders falling green characters.
   It runs continuously but is inexpensive and uses requestAnimationFrame.
*/
(function initMatrixBackdrop() {
    const canvas = document.getElementById('matrix-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    // Characters to use (mono-spaced glyphs look best)
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@#$%&*()[]{}<>\/|';
    let fontSize = 16;
    let columns = [];
    let width = 0;
    let height = 0;

    function resize() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
        // Choose font size proportional to viewport but keep readable
        fontSize = Math.max(12, Math.floor(Math.min(22, Math.max(12, width / 100))));
        ctx.font = `${fontSize}px monospace`;
        columns = new Array(Math.floor(width / fontSize)).fill(0).map(() => Math.floor(Math.random() * height));
    }

    function draw() {
        // Slight translucent black to create trail/fade effect
        ctx.fillStyle = 'rgba(0, 0, 0, 0.08)';
        ctx.fillRect(0, 0, width, height);

        ctx.fillStyle = '#0f0'; // bright green
        ctx.textBaseline = 'top';

        for (let i = 0; i < columns.length; i++) {
            const x = i * fontSize;
            // pick a random character
            const ch = chars.charAt(Math.floor(Math.random() * chars.length));
            const y = columns[i] * fontSize;
            // slightly brighter for head
            ctx.fillStyle = `rgba(144, 255, 144, ${Math.random() * 0.8 + 0.2})`;
            ctx.fillText(ch, x, y);

            // move drop
            if (y > height && Math.random() > 0.975) {
                columns[i] = 0;
            }
            columns[i]++;
        }
        requestAnimationFrame(draw);
    }

    // initialize
    resize();
    window.addEventListener('resize', resize);
    requestAnimationFrame(draw);
})();

// Socket Event Handlers
socket.on('connect', () => {
    console.log('Connected to server');
});

socket.on('game_state', (data) => {
    currentRound = data.current_round;
    totalRounds = data.total_rounds;
    totalRoundsSpan.textContent = totalRounds;
});

socket.on('join_success', (data) => {
    currentPlayer = data.name;
    welcomeName.textContent = data.name;
    // update hero name
    const heroNameEl = document.getElementById('hero-name');
    if (heroNameEl) heroNameEl.textContent = data.name;
    showScreen('lobby');
});

socket.on('player_joined', (data) => {
    showNotification(`${data.name} joined the game!`);
});

socket.on('player_left', (data) => {
    showNotification(`${data.name} left the game`);
});

socket.on('update_players', (data) => {
    updatePlayerList(data.players);
});

socket.on('game_started', (data) => {
    currentRound = data.round;
    totalRounds = data.total_rounds;
    timeLimit = data.timeLimit || 0;
    roundStartTime = Date.now();
    loadRound(data.snippet);
    // Ensure input and submit button are enabled (re-enable after any reset)
    codeInput.value = '';
    codeInput.disabled = false;
    submitBtn.disabled = false;
    feedback.classList.add('hidden');
    codeInput.focus();
    showScreen('game');
    roundInfo.classList.remove('hidden');
    startCountdown();
});

socket.on('new_round', (data) => {
    currentRound = data.round;
    roundStartTime = Date.now();
    loadRound(data.snippet);
    codeInput.value = '';
    codeInput.disabled = false;
    submitBtn.disabled = false;
    feedback.classList.add('hidden');
    showScreen('game');
    startCountdown();
});

socket.on('round_result', (data) => {
    stopCountdown();
    showWaitingScreen(data);
});

socket.on('game_over', (data) => {
    updateFinalLeaderboard(data.leaderboard);
    showScreen('gameover');
});

socket.on('update_leaderboard', (data) => {
    updateLeaderboard(data.leaderboard);
    // Also update waiting screen leaderboard
    if (!waitingScreen.classList.contains('hidden')) {
        updateWaitingLeaderboard(data.leaderboard);
    }
    // Also update final leaderboard if on gameover screen
    if (!gameoverScreen.classList.contains('hidden')) {
        updateFinalLeaderboard(data.leaderboard);
    }
});

socket.on('error', (data) => {
    showFeedback(data.message, 'error');
});

// When master resets players, return player UI to waiting/lobby state
socket.on('players_reset', (data) => {
    console.log('Received players_reset from server', data);

    // Stop any active timers and disable submission
    stopCountdown();
    submitBtn.disabled = true;
    codeInput.disabled = true;

    // Clear code input and feedback
    codeInput.value = '';
    feedback.classList.add('hidden');

    // Reset round info display
    roundInfo.classList.add('hidden');
    currentRound = 0;
    currentRoundSpan.textContent = currentRound;

    // Update player list if provided
    if (data && Array.isArray(data.players)) {
        updatePlayerList(data.players);
    } else {
        // Ask server for fresh player list
        socket.emit('get_leaderboard');
    }

    // Show lobby/waiting screen
    showScreen('lobby');
});
    

// Fallback event for browsers that may not handle the custom payload event reliably
socket.on('force_lobby', (data) => {
    console.log('Received force_lobby from server', data);
    // Reuse the same reset logic — stop timers, disable input and show lobby
    stopCountdown();
    submitBtn.disabled = true;
    codeInput.disabled = true;
        // Central focused-mode toggle: add class when on game screen
        try {
            if (screen === 'game') document.body.classList.add('focused-mode');
            else document.body.classList.remove('focused-mode');
        } catch (e) {
            // ignore when DOM not available
        }
    codeInput.value = '';
    feedback.classList.add('hidden');
    roundInfo.classList.add('hidden');
    currentRound = 0;
    currentRoundSpan.textContent = currentRound;
    showScreen('lobby');
    // Request updated players list so UI refreshes
    socket.emit('get_leaderboard');
});

// Functions
function joinGame() {
    const name = playerNameInput.value.trim();
    if (name.length === 0) {
        alert('Please enter your name');
        return;
    }
    socket.emit('join_game', { name: name });
}

function submitCode(isAutoSubmit = false) {
    const code = codeInput.value.trim();

    // Get the current snippet length for comparison
    const expectedCode = codeDisplay.textContent;

    // Only show warnings for manual submissions, not auto-submissions
    if (!isAutoSubmit) {
        // Warn about empty or very short submissions
        if (code.length === 0) {
            if (!confirm('🙄 Really? REALLY? You didn\'t type a single character and you want to submit? Fine, enjoy your 1 point, genius. Continue with this embarrassment?')) {
                return;
            }
        } else if (code.length < expectedCode.length * 0.2) {
            if (!confirm(`😂 Oh this is precious! You typed ${code.length} characters when you needed ${expectedCode.length}. That\'s like bringing a spoon to a sword fight. Sure you want to humiliate yourself?`)) {
                return;
            }
        }
    }

    socket.emit('submit_code', { code: code });
}

function loadRound(snippet) {
    currentRoundSpan.textContent = currentRound;
    languageLabel.textContent = snippet.language.toUpperCase();
    pointsLabel.textContent = `Base Points: ${snippet.points}`;
    codeDisplay.textContent = snippet.code;
    codeInput.value = '';
    codeInput.focus();
    // store snippet locally for live projection
    currentSnippetCode = snippet.code;
    currentSnippetPoints = snippet.points;
    lastInputValue = '';
    // initialize meter
    updateHeroMeter();
}

function startCountdown() {
    if (timeLimit <= 0) {
        countdownElement.classList.add('hidden');
        return;
    }

    countdownElement.classList.remove('hidden');
    let timeLeft = timeLimit;
    timerText.textContent = timeLeft;

    // Reset timer classes
    countdownElement.className = 'countdown-timer';

    countdownTimer = setInterval(() => {
        timeLeft--;
        timerText.textContent = timeLeft;

        // Update timer appearance based on remaining time
        if (timeLeft <= 10) {
            countdownElement.className = 'countdown-timer critical';
        } else if (timeLeft <= 30) {
            countdownElement.className = 'countdown-timer warning';
        }

        if (timeLeft <= 0) {
            stopCountdown();
            handleTimeUp();
        }
    }, 1000);
}

function stopCountdown() {
    if (countdownTimer) {
        clearInterval(countdownTimer);
        countdownTimer = null;
    }
    countdownElement.classList.add('hidden');
}

function handleTimeUp() {
    if (!submitBtn.disabled) {
        // Auto-submit whatever is typed without confirmation prompts
        showFeedback('⏰ Time\'s up! Auto-submitting...', 'error');

        // Disable further submissions to prevent double submission
        submitBtn.disabled = true;
        codeInput.disabled = true;

        setTimeout(() => {
            submitCode(true); // Pass true for auto-submit (bypasses confirmations)
        }, 1000);
    }
}

function showFeedback(message, type) {
    feedback.innerHTML = message;
    feedback.className = 'feedback ' + type;
    feedback.classList.remove('hidden');
}

function updatePlayerList(players) {
    if (players.length === 0) {
        playerList.innerHTML = '<p>No players yet...</p>';
        return;
    }

    playerList.innerHTML = players.map(player =>
        `<div class="player-item">${player.name} - ${player.score} points</div>`
    ).join('');
}

function updateLeaderboard(players) {
    if (players.length === 0) {
        leaderboard.innerHTML = '<p>No scores yet...</p>';
        return;
    }

    leaderboard.innerHTML = players.map((player, index) => `
        <div class="leaderboard-item">
            <span class="player-rank">#${index + 1}</span>
            <div class="player-info">
                <div>${player.name}</div>
                <small>Round ${player.current_round}/10</small>
            </div>
            <span class="player-score">${player.score}</span>
        </div>
    `).join('');
}

function updateFinalLeaderboard(players) {
    if (players.length === 0) {
        finalLeaderboard.innerHTML = '<p>No scores...</p>';
        return;
    }

    finalLeaderboard.innerHTML = players.map((player, index) => {
        let medal = '';
        if (index === 0) medal = '🥇';
        else if (index === 1) medal = '🥈';
        else if (index === 2) medal = '🥉';

        return `
            <div class="leaderboard-item">
                <span class="player-rank">${medal || `#${index + 1}`}</span>
                <div class="player-info">
                    <div><strong>${player.name}</strong></div>
                    <small>Round ${player.current_round}/10</small>
                </div>
                <span class="player-score">${player.score}</span>
            </div>
        `;
    }).join('');
}

function showWaitingScreen(data) {
    // Determine accuracy status for styling
    let accuracyClass = '';
    let accuracyMessage = '';

    if (data.accuracy < 20) {
        accuracyClass = 'accuracy-terrible';
        accuracyMessage = '💥 Did you type with your feet? Even monkeys have better accuracy!';
    } else if (data.accuracy < 40) {
        accuracyClass = 'accuracy-poor';
        accuracyMessage = '🤦 Wow, such typing skills! Maybe try looking at the screen next time?';
    } else if (data.accuracy < 60) {
        accuracyClass = 'accuracy-mediocre';
        accuracyMessage = '😴 Meh. I\'ve seen toddlers with better hand-eye coordination.';
    } else if (data.accuracy < 80) {
        accuracyClass = 'accuracy-good';
        accuracyMessage = '👌 Not terrible! You\'re almost functioning like a normal human being.';
    } else if (data.accuracy < 95) {
        accuracyClass = 'accuracy-very-good';
        accuracyMessage = '😎 Oh look, someone who can actually read! How refreshing.';
    } else {
        accuracyClass = 'accuracy-excellent';
        accuracyMessage = '🏆 Fine, fine... I guess you\'re not completely hopeless after all.';
    }

    // Show round results with enhanced accuracy feedback and detailed breakdown
    const breakdown = data.breakdown || {};
    const maxScore = breakdown.max_possible || 'Unknown';
    const basePoints = breakdown.base_points || data.score;
    const speedBonus = breakdown.speed_bonus || 0;
    const accuracyMult = Math.round((breakdown.accuracy_mult || 1) * 100);

    let speedSection = '';
    if (breakdown.speed_eligible) {
        speedSection = `
            <div class="score-component speed-bonus">
                <span class="component-label">⚡ Speed Bonus:</span>
                <span class="component-value">+${speedBonus} pts</span>
                <span class="component-note">(Fast + accurate!)</span>
            </div>
        `;
    } else if (data.accuracy > 70) {
        speedSection = `
            <div class="score-component speed-missed">
                <span class="component-label">⚡ Speed Bonus:</span>
                <span class="component-value">+0 pts</span>
                <span class="component-note">(Too slow for bonus)</span>
            </div>
        `;
    } else {
        speedSection = `
            <div class="score-component speed-locked">
                <span class="component-label">🔒 Speed Bonus:</span>
                <span class="component-value">Locked</span>
                <span class="component-note">(Need 70%+ accuracy)</span>
            </div>
        `;
    }

    const accuracyDisplay = (typeof data.accuracy === 'number') ? data.accuracy.toFixed(2) : Number(data.accuracy).toFixed(2);

    roundResults.innerHTML = `
        <div class="round-complete-header">
            <strong>Round ${data.round} Complete! ✅</strong>
        </div>
        <div class="accuracy-feedback ${accuracyClass}">
            <strong>Accuracy: ${accuracyDisplay}%</strong>
            <div class="accuracy-message">${accuracyMessage}</div>
        </div>
        <div class="score-breakdown-detailed">
            <div class="score-summary">
                <div class="final-score">
                    <span class="score-label">Final Score:</span>
                    <span class="score-value">${data.score}</span>
                    <span class="max-score">/ ${maxScore}</span>
                </div>
                <div class="score-percentage">${Math.round((data.score / maxScore) * 100)}% of maximum</div>
            </div>

            <div class="score-components">
                <div class="score-component accuracy-points">
                    <span class="component-label">🎯 Accuracy Points:</span>
                    <span class="component-value">${basePoints} pts</span>
                    <span class="component-note">(${accuracyMult}% of base ${maxScore})</span>
                </div>
                ${speedSection}
            </div>

            <div class="performance-stats">
                <div class="stat-item">
                    <span class="stat-label">WPM:</span>
                    <span class="stat-value">${data.wpm}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Time:</span>
                    <span class="stat-value">${data.time}s</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Total Score:</span>
                    <span class="stat-value">${data.total_score}</span>
                </div>
            </div>
        </div>
    `;

    // Request current leaderboard
    socket.emit('get_leaderboard');

    // Switch to waiting screen
    showScreen('waiting');
}

function updateWaitingLeaderboard(players) {
    if (players.length === 0) {
        waitingLeaderboard.innerHTML = '<p>No scores yet...</p>';
        return;
    }

    waitingLeaderboard.innerHTML = players.map((player, index) => `
        <div class="leaderboard-item">
            <span class="player-rank">#${index + 1}</span>
            <div class="player-info">
                <div>${player.name}</div>
                <small>Round ${player.current_round}/10</small>
            </div>
            <span class="player-score">${player.score}</span>
        </div>
    `).join('');
}

function showScreen(screen) {
    joinScreen.classList.add('hidden');
    lobbyScreen.classList.add('hidden');
    gameScreen.classList.add('hidden');
    waitingScreen.classList.add('hidden');
    gameoverScreen.classList.add('hidden');

    switch(screen) {
        case 'join':
            joinScreen.classList.remove('hidden');
            break;
        case 'lobby':
            lobbyScreen.classList.remove('hidden');
            break;
        case 'game':
            gameScreen.classList.remove('hidden');
            break;
        case 'waiting':
            waitingScreen.classList.remove('hidden');
            break;
        case 'gameover':
            gameoverScreen.classList.remove('hidden');
            break;
    }
    // Central focused-mode toggle: add class when on game screen
    try {
        if (screen === 'game') document.body.classList.add('focused-mode');
        else document.body.classList.remove('focused-mode');
    } catch (e) {
        // ignore when DOM not available
    }

    // Debug log to help verify behavior in the browser console
    try { console.log('showScreen ->', screen, 'focused-mode=', document.body.classList.contains('focused-mode')); } catch (e) {}

    // Inline fallback: apply minimal inline styles so focused-mode is visible
    // even if the served CSS is stale or cached. These are cleared when
    // switching away from the game screen.
    try {
        const lb = document.querySelector('.leaderboard-section');
        const gc = document.querySelector('.game-container');
        const codeSec = document.querySelector('.code-section');
        const typingSec = document.querySelector('.typing-section');
        if (screen === 'game') {
            if (lb) {
                lb.style.position = 'fixed';
                lb.style.top = '16px';
                lb.style.right = '16px';
                lb.style.width = '240px';
                lb.style.maxHeight = 'calc(100vh - 32px)';
                lb.style.zIndex = '40';
                lb.style.padding = '12px';
            }
            if (gc) {
                gc.style.display = 'flex';
                gc.style.flexDirection = 'column';
                gc.style.alignItems = 'center';
            }
            if (codeSec) codeSec.style.width = '92%';
            if (typingSec) typingSec.style.width = '92%';
        } else {
            if (lb) lb.style.cssText = '';
            if (gc) gc.style.cssText = '';
            if (codeSec) codeSec.style.cssText = '';
            if (typingSec) typingSec.style.cssText = '';
        }
    } catch (e) {
        // ignore DOM errors
    }

}

function showNotification(message) {
    console.log(message);
    // Could add toast notifications here
}

// Request leaderboard updates periodically during game
setInterval(() => {
    if (gameScreen.classList.contains('hidden') === false || waitingScreen.classList.contains('hidden') === false) {
        socket.emit('get_leaderboard');
    }
}, 2000);
