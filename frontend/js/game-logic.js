// game-logic.js - Updated with proper API integration

// ==================== IMPORT API CLIENT ====================
// Note: If using vanilla HTML, copy api-service.js inline or use modules

const API_BASE = 'http://localhost:8000';

// ==================== ENHANCED API WRAPPER ====================

class APIClient {
    static async call(endpoint, options = {}) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);

        try {
            const response = await fetch(`${API_BASE}${endpoint}`, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers,
                },
                signal: controller.signal,
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            
            if (error.name === 'AbortError') {
                throw new Error('⏱️ Request timeout - Check if backend is running');
            }
            if (error.message.includes('Failed to fetch')) {
                throw new Error('🔌 Cannot connect to server. Start backend: python main.py');
            }
            throw error;
        }
    }
}

// ==================== GAME STATE ====================

let gameState = {
    playerName: localStorage.getItem('playerName') || "MARIO_SUPPORT",
    avatarUrl: localStorage.getItem('avatarUrl') || "./assets/avatar1.png",
    profile: null,
    score: 0,
    hearts: 3,
    world: 1, 
    ticketsCompleted: 0,
    totalTickets: 1,
    currentTicket: null,
    isGameOver: false,
    taskType: "easy",
    isLoading: false,
    lastReward: null,
    liveFeedback: null,
    showFeedback: false,
    xp: 0,
    level: 1,
    redAlertMode: false,
    timer: null,
    timeLeft: 45,
    startTime: null,
    sessionId: null
};

// ==================== TIMER MANAGEMENT ====================

function toggleRedAlert() {
    gameState.redAlertMode = document.getElementById('red-alert-toggle').checked;
    const timerEl = document.getElementById('countdown-timer');
    const alertIcon = document.getElementById('alert-icon');
    
    if (gameState.redAlertMode) {
        timerEl?.classList.remove('hidden');
        alertIcon?.classList.add('text-primary');
    } else {
        timerEl?.classList.add('hidden');
        alertIcon?.classList.remove('text-primary');
        stopTimer();
    }
}

function startTimer() {
    if (!gameState.redAlertMode) return;
    stopTimer();
    
    gameState.timeLeft = 45;
    gameState.startTime = Date.now();
    updateTimerUI();
    
    gameState.timer = setInterval(() => {
        gameState.timeLeft--;
        updateTimerUI();
        
        const missionCard = document.getElementById('mission-card');
        if (gameState.timeLeft <= 5) {
            missionCard?.classList.add('ring-4', 'ring-primary/50', 'animate-pulse');
            AudioEngine.failure(); // Warning tick
        }
        
        if (gameState.timeLeft <= 0) {
            handleTimerExpiry();
        }
    }, 1000);
}

function stopTimer() {
    if (gameState.timer) {
        clearInterval(gameState.timer);
        gameState.timer = null;
    }
    document.getElementById('mission-card')?.classList.remove('ring-4', 'ring-primary/50', 'animate-pulse');
}

function updateTimerUI() {
    const timerText = document.getElementById('timer-text');
    if (!timerText) return;
    
    timerText.innerText = `${gameState.timeLeft}s`;
    timerText.classList.toggle('text-yellow-400', gameState.timeLeft <= 10);
}

async function handleTimerExpiry() {
    stopTimer();
    showNotification("⏰ TIME'S UP! Ticket breached SLA! -1 Heart");
    await handleAction('escalate', true);
}

// ==================== AUDIO ENGINE ====================

const AudioEngine = {
    ctx: new (window.AudioContext || window.webkitAudioContext)(),
    
    beep(freq, duration, type = "square") {
        try {
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();
            osc.type = type;
            osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
            gain.gain.setValueAtTime(0.1, this.ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + duration);
            osc.connect(gain);
            gain.connect(this.ctx.destination);
            osc.start();
            osc.stop(this.ctx.currentTime + duration);
        } catch (e) {
            console.warn('Audio playback failed:', e);
        }
    },
    
    success() { 
        this.beep(880, 0.1); 
        setTimeout(() => this.beep(1109, 0.2), 100); 
    },
    
    failure() { 
        this.beep(220, 0.3, "sawtooth"); 
    },
    
    coin() { 
        this.beep(1320, 0.05); 
        setTimeout(() => this.beep(1760, 0.1), 50); 
    }
};

// ==================== API INTEGRATION ====================

async function login() {
    try {
        const profile = await APIClient.call('/login', {
            method: 'POST',
            body: JSON.stringify({
                player_name: gameState.playerName,
                avatar_url: gameState.avatarUrl
            })
        });
        
        gameState.profile = profile;
        gameState.score = profile.score;
        gameState.hearts = profile.hearts;
        gameState.world = profile.world;
        gameState.xp = profile.xp || 0;
        gameState.level = profile.level || 1;
        
        console.log('✅ Login successful:', profile);
        updateUI();
    } catch (error) {
        console.error('❌ Login failed:', error);
        showNotification(`Login Error: ${error.message}`);
    }
}

async function initGame(type = "easy") {
    gameState.isLoading = true;
    gameState.taskType = type;
    updateUI();
    
    const startBtn = document.getElementById('start-button-text');
    if (startBtn) startBtn.innerText = "LOADING...";
    
    try {
        const data = await APIClient.call(`/reset?task_type=${type}`, { 
            method: 'POST' 
        });
        
        gameState.world = type === "easy" ? 1 : type === "medium" ? 2 : 3;
        gameState.currentTicket = data.observation;
        gameState.sessionId = data.session_id;
        gameState.ticketsCompleted = 0;
        gameState.score = 0;
        gameState.hearts = 3;
        gameState.isGameOver = false;
        
        console.log('✅ Game initialized:', data);
        
        if (gameState.redAlertMode) startTimer();
    } catch (error) {
        console.error('❌ Game init failed:', error);
        
        // Fallback ticket for offline mode
        gameState.currentTicket = { 
            ticket_id: "ERR_404", 
            customer_message: `⚠️ Backend Connection Failed\n\n${error.message}\n\nTo fix:\n1. cd backend\n2. python main.py\n3. Refresh this page`
        };
    } finally {
        gameState.isLoading = false;
        if (startBtn) startBtn.innerText = "GET TICKET";
        updateUI();
    }
}

async function handleAction(decision, isTimeout = false) {
    if (gameState.isGameOver || !gameState.currentTicket || gameState.isLoading) {
        return;
    }
    
    // Resume audio context
    if (AudioEngine.ctx.state === 'suspended') {
        AudioEngine.ctx.resume();
    }
    
    // Calculate time taken
    const timeTaken = gameState.redAlertMode && gameState.startTime 
        ? (Date.now() - gameState.startTime) / 1000 
        : 0;
    stopTimer();
    
    gameState.isLoading = true;
    
    // Show loading state
    const feedbackPortal = document.getElementById('ai-feedback-portal');
    const feedbackText = document.getElementById('ai-feedback-text');
    feedbackPortal?.classList.remove('hidden');
    if (feedbackText) {
        feedbackText.innerText = isTimeout 
            ? "⏰ SLA BREACHED! Quest Master is recording the failure..." 
            : "🔮 Quest Master is analyzing your reasoning...";
    }
    
    const draft = isTimeout 
        ? "SLA BREACHED: No response provided in time." 
        : document.getElementById('draft-input')?.value || "";
    
    const reasoning = isTimeout 
        ? "Agent failed to respond within the allocated time limit." 
        : document.getElementById('reasoning-input')?.value || "";
    
    const actionPayload = {
        decision: decision,
        team: decision === "escalate" ? "support" : "none",
        urgency: isTimeout ? "high" : "medium",
        draft_response: draft || `Support Agent ${gameState.playerName}: Triage action ${decision} applied.`,
        reasoning: reasoning || `Decided to ${decision} based on standard protocol.`,
        time_taken: timeTaken
    };
    
    try {
        // Include session_id in the request
        const endpoint = gameState.sessionId 
            ? `/step?session_id=${gameState.sessionId}` 
            : '/step';
        
        const data = await APIClient.call(endpoint, {
            method: 'POST',
            body: JSON.stringify(actionPayload)
        });
        
        // Extract reward
        const reward = data.reward.overall_score;
        gameState.lastReward = reward;
        gameState.liveFeedback = data.reward.live_feedback;
        
        // Evaluate & show feedback
        if (reward >= 0.7) {
            showVisualFeedback("⭐ PERFECT! +100 SCORE, +50 XP", "text-tertiary");
            AudioEngine.coin();
            gameState.score += 100;
            gameState.xp += 50;
        } else if (reward >= 0.4) {
            showVisualFeedback("✓ GOOD! +50 SCORE, +20 XP", "text-secondary-fixed");
            AudioEngine.success();
            gameState.score += 50;
            gameState.xp += 20;
        } else {
            showVisualFeedback("✗ MISS! -1 HEART", "text-primary");
            AudioEngine.failure();
            gameState.hearts--;
        }
        
        // Update level dynamically based on total XP
        gameState.level = Math.floor(gameState.xp / 100) + 1;
        
        // Sync progress
        gameState.ticketsCompleted = data.info.tickets_completed;
        gameState.totalTickets = data.info.total_tickets;
        
        // Removed profile sync as it was wiping local XP state back to default 0.
        // Instead, just proceed to update local UI.        
        // Show feedback
        if (feedbackText) {
            feedbackText.innerText = gameState.liveFeedback || "Mission analysis complete.";
        }
        
        updateUI();
        
        // Wait for player to read feedback
        await new Promise(resolve => setTimeout(resolve, 2500));
        
        // Auto-progress to next world if done
        if (data.done) {
            if (gameState.taskType === 'easy') {
                showNotification("LEVEL UP! Moving to WORLD 2 (Medium)");
                await initGame('medium');
                return;
            } else if (gameState.taskType === 'medium') {
                showNotification("LEVEL UP! Moving to WORLD 3 (Hard)");
                await initGame('hard');
                return;
            } else {
                gameState.currentTicket = null;
            }
        } else {
            // Load next ticket
            gameState.currentTicket = data.observation;
        }
        
        // Clear inputs
        const draftInput = document.getElementById('draft-input');
        const reasoningInput = document.getElementById('reasoning-input');
        if (draftInput) draftInput.value = "";
        if (reasoningInput) reasoningInput.value = "";
        
        feedbackPortal?.classList.add('hidden');
        
        // Check game over
        if (gameState.hearts <= 0) {
            gameState.isGameOver = true;
            showNotification("💔 GAME OVER! All hearts lost!");
        }
        
        // Start timer for next ticket
        if (gameState.redAlertMode && !gameState.isGameOver) {
            startTimer();
        }
        
    } catch (error) {
        console.error('❌ Action submission failed:', error);
        if (feedbackText) {
            feedbackText.innerText = `⚠️ Quest Master encountered an error: ${error.message}`;
        }
    } finally {
        gameState.isLoading = false;
        updateUI();
    }
}

// ==================== UI HELPERS ====================

function showVisualFeedback(text, colorClass) {
    const layer = document.getElementById('feedback-layer');
    if (!layer) return;
    
    const feedback = document.createElement('div');
    feedback.className = `font-pixel text-[14px] ${colorClass} feedback-float absolute`;
    feedback.innerText = text;
    layer.appendChild(feedback);
    
    setTimeout(() => feedback.remove(), 1000);
}

function showNotification(message) {
    // Simple alert for now - can be replaced with toast
    console.log('📢', message);
    // Optional: Create a toast notification element
}

function updateUI() {
    // Disable buttons during loading
    const buttons = document.querySelectorAll('.grid button');
    buttons.forEach(btn => {
        if (gameState.isLoading) {
            btn.classList.add('opacity-50', 'cursor-not-allowed');
            btn.disabled = true;
        } else {
            btn.classList.remove('opacity-50', 'cursor-not-allowed');
            btn.disabled = false;
        }
    });
    
    // Update stats
    const scoreDisplay = document.getElementById('score-display');
    const coinDisplay = document.getElementById('header-coin-display');
    const levelDisplay = document.getElementById('level-display');
    const worldDisplay = document.getElementById('world-display');
    const nameDisplay = document.getElementById('display-player-name');
    
    if (scoreDisplay) scoreDisplay.innerText = `SCORE: ${gameState.score}`;
    if (coinDisplay) coinDisplay.innerText = `COINS: ${gameState.profile?.coins || 0}`;
    if (levelDisplay) levelDisplay.innerText = `LEVEL_${gameState.level}`;
    if (worldDisplay) worldDisplay.innerText = `WORLD_${gameState.world}`;
    if (nameDisplay) nameDisplay.innerText = gameState.playerName;
    
    // Update hearts
    const heartsContainer = document.getElementById('hearts-container');
    if (heartsContainer) {
        heartsContainer.innerHTML = '';
        for (let i = 0; i < 3; i++) {
            const heart = document.createElement('span');
            heart.className = `material-symbols-outlined text-xl ${
                i < gameState.hearts 
                    ? 'text-primary dark:text-[#ffb4aa]' 
                    : 'text-outline opacity-30'
            }`;
            heart.style.fontVariationSettings = "'FILL' 1";
            heart.innerText = 'favorite';
            heartsContainer.appendChild(heart);
        }
    }
    
    // Update ticket display
    const ticket = gameState.currentTicket;
    const ticketId = document.getElementById('ticket-id');
    const ticketTitle = document.getElementById('ticket-title');
    const ticketMessage = document.getElementById('ticket-message');
    
    if (ticket) {
        if (ticketId) ticketId.innerText = `TICKET #${ticket.ticket_id}`;
        
        const showLoading = gameState.isLoading && !ticket.customer_message;
        
        if (ticketTitle) {
            ticketTitle.innerText = showLoading 
                ? "⚙️ SYNCING..." 
                : ticket.customer_message.split('\n')[0].substring(0, 60).toUpperCase();
        }
        
        if (ticketMessage) {
            ticketMessage.innerText = showLoading 
                ? "Connecting to the Cloud Fortress..." 
                : ticket.customer_message;
        }
    } else if (gameState.isGameOver) {
        if (ticketTitle) ticketTitle.innerText = "💀 GAME OVER";
        if (ticketMessage) ticketMessage.innerText = "You've lost all hearts! Press START to retry.";
    } else {
        if (ticketTitle) ticketTitle.innerText = "🏆 WORLD CLEAR!";
        if (ticketMessage) ticketMessage.innerText = `Great triage, ${gameState.playerName}! Mission accomplished.`;
    }
    
    // Update progress bar
    const progressText = document.getElementById('progress-text');
    const progressFill = document.getElementById('progress-fill');
    
    if (progressText) {
        progressText.innerText = `${gameState.ticketsCompleted} / ${gameState.totalTickets} DONE`;
    }
    
    if (progressFill) {
        const progressPercent = (gameState.ticketsCompleted / gameState.totalTickets) * 100;
        progressFill.style.width = `${progressPercent}%`;
    }
    
    // Update XP bar
    const xpFill = document.getElementById('xp-fill');
    const xpText = document.getElementById('xp-text');
    const levelSmall = document.getElementById('level-display-small');
    
    if (xpFill) {
        const xpInCurrentLevel = gameState.xp % 100;
        xpFill.style.width = `${xpInCurrentLevel}%`;
    }
    
    if (xpText) xpText.innerText = `CAREER XP: ${gameState.xp}`;
    if (levelSmall) levelSmall.innerText = `LVL ${gameState.level}`;
}

// ==================== PROFILE MANAGEMENT ====================

function selectAvatar(src) {
    gameState.avatarUrl = src;
    localStorage.setItem('avatarUrl', src);
    const currentAvatar = document.getElementById('current-avatar');
    if (currentAvatar) currentAvatar.src = src;
}

function saveProfile() {
    const nameInput = document.getElementById('name-input');
    const newName = nameInput?.value;
    
    if (newName && newName.trim()) {
        gameState.playerName = newName.trim();
        localStorage.setItem('playerName', newName.trim());
        login(); // Re-login with new name
    }
    
    document.getElementById('avatar-picker')?.classList.add('hidden');
}

// ==================== LEADERBOARD & STATS ====================

async function showLeaderboard() {
    const modal = document.getElementById('leaderboard-modal');
    const list = document.getElementById('leaderboard-list');
    
    if (!modal || !list) return;
    
    list.innerHTML = '<p class="font-pixel text-[8px] text-center p-4">📡 Syncing with Castle...</p>';
    modal.classList.remove('hidden');
    
    try {
        const data = await APIClient.call('/leaderboard');
        list.innerHTML = '';
        
        data.forEach((player, index) => {
            const item = document.createElement('div');
            item.className = 'flex items-center justify-between p-3 bg-surface-container dark:bg-[#1a1a1a] pixel-border';
            item.innerHTML = `
                <div class="flex items-center gap-3">
                    <span class="font-pixel text-[10px] text-primary dark:text-[#ffb4aa] w-4">${index + 1}.</span>
                    <p class="font-pixel text-[10px] uppercase">${player.player_name}</p>
                </div>
                <div class="text-right">
                    <p class="font-pixel text-[8px] text-secondary">SCORE: ${player.score}</p>
                    <p class="font-pixel text-[6px] opacity-70">W${player.world}</p>
                </div>
            `;
            list.appendChild(item);
        });
    } catch (error) {
        list.innerHTML = `<p class="font-pixel text-[8px] text-primary p-4">⚠️ ${error.message}</p>`;
    }
}

function hideLeaderboard() {
    document.getElementById('leaderboard-modal')?.classList.add('hidden');
}

async function showArchives() {
    const modal = document.getElementById('archives-modal');
    if (!modal) return;
    
    modal.classList.remove('hidden');
    
    try {
        const data = await APIClient.call('/stats');
        
        const totalTriageStat = document.getElementById('total-triage-stat');
        const avgScoreStat = document.getElementById('avg-score-stat');
        
        if (totalTriageStat) totalTriageStat.innerText = data.total_triage;
        if (avgScoreStat) avgScoreStat.innerText = `${Math.round(data.avg_score * 100)}%`;
        
        // Build accuracy chart
        const chart = document.getElementById('accuracy-chart');
        if (chart) {
            chart.innerHTML = '';
            
            (data.recent_logs || []).forEach(log => {
                const barHeight = Math.max(5, log.score * 100);
                const bar = document.createElement('div');
                bar.className = `w-4 ${
                    log.score >= 0.7 ? 'bg-tertiary' : 
                    log.score >= 0.4 ? 'bg-secondary' : 
                    'bg-primary'
                } border-x border-t border-black/20`;
                bar.style.height = `${barHeight}%`;
                chart.appendChild(bar);
            });
            
            // Fill empty bars
            for (let i = data.recent_logs.length; i < 10; i++) {
                const emptyBar = document.createElement('div');
                emptyBar.className = "w-4 h-1 bg-surface-container-highest dark:bg-[#433632] opacity-30";
                chart.appendChild(emptyBar);
            }
        }
    } catch (error) {
        console.error('Failed to load archives:', error);
    }
}

function hideArchives() {
    document.getElementById('archives-modal')?.classList.add('hidden');
}

// ==================== HINT & CUSTOM QUEST ====================

async function getHint() {
    if (!gameState.profile || gameState.profile.coins < 50) {
        showNotification("💰 Not enough coins! Earn more by solving missions.");
        return;
    }
    
    const feedbackPortal = document.getElementById('ai-feedback-portal');
    const feedbackText = document.getElementById('ai-feedback-text');
    
    feedbackPortal?.classList.remove('hidden');
    if (feedbackText) feedbackText.innerText = "📜 The Quest Master is consulting the ancient scrolls...";
    
    try {
        const data = await APIClient.call('/hint');
        if (feedbackText) feedbackText.innerText = `💡 ${data.hint}`;
        AudioEngine.beep(660, 0.2);
        
        // Deduct coins locally (will sync on next action)
        if (gameState.profile) {
            gameState.profile.coins -= 50;
            updateUI();
        }
    } catch (error) {
        if (feedbackText) feedbackText.innerText = `⚠️ ${error.message}`;
    }
}

async function startCustomQuest() {
    const topicInput = document.getElementById('custom-topic');
    const topic = topicInput?.value;
    
    if (!topic || !topic.trim()) {
        showNotification("📝 Enter a topic for the Quest Master!");
        return;
    }
    
    const startBtn = document.getElementById('start-button-text');
    gameState.isLoading = true;
    if (startBtn) startBtn.innerText = "CRAFTING...";
    updateUI();
    
    try {
        await APIClient.call(`/generate_quest?topic=${encodeURIComponent(topic)}`, { 
            method: 'POST' 
        });
        await initGame('custom');
    } catch (error) {
        showNotification(`Quest generation failed: ${error.message}`);
    } finally {
        gameState.isLoading = false;
        if (startBtn) startBtn.innerText = "GET TICKET";
        updateUI();
    }
}

// ==================== THEME TOGGLE ====================

function toggleTheme() {
    const isDark = document.documentElement.classList.toggle('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
}

// ==================== INITIALIZATION ====================

window.onload = async () => {
    // Load theme preference
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.documentElement.classList.add('dark');
    }
    
    // Initialize game
    await login();
    await initGame(gameState.taskType);
    
    console.log('🎮 Game initialized successfully');
};

// ==================== ERROR BOUNDARY ====================

window.addEventListener('unhandledrejection', (event) => {
    console.error('❌ Unhandled Promise Rejection:', event.reason);
    showNotification(`Error: ${event.reason?.message || 'Unknown error'}`);
});

// ==================== GLOBAL EXPORTS FOR INLINE HTML ====================
window.handleAction = handleAction;
window.initGame = initGame;
window.toggleRedAlert = toggleRedAlert;
window.showArchives = showArchives;
window.hideArchives = hideArchives;
window.startCustomQuest = startCustomQuest;
window.getHint = getHint;
window.showLeaderboard = showLeaderboard;
window.hideLeaderboard = hideLeaderboard;
window.selectAvatar = selectAvatar;
window.saveProfile = saveProfile;
window.toggleTheme = toggleTheme;
