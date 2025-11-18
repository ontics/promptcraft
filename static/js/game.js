// Socket.IO connection
const socket = io();

// Game state
let gameState = {
    playerName: '',
    playerTeam: '',
    playerCharacter: '',
    currentRound: 0,
    selectedImageIndex: null,
    generatedImages: [],
    votedFor: null,
    isAdmin: false,
    tempVoteSelection: null,
    transitionTimer: null,
    transitionCountdown: null,
    messageAutoHideTimer: null,  // Timer for auto-hiding character messages
    // Avatar state
    currentCharacter: null,  // 'Bud' or 'Spud'
    avatarPlantState: null,  // 'base', 'yellow', 'dry' (for Spud)
    avatarAnimationState: null,  // 'smiling', 'talking', 'welling', 'sad', 'sad_talking', 'crying'
    avatarAnimationInterval: null,  // For talking animations
    hasConfirmedSelection: false,    // Track if player confirmed their selection
    // Admin time calculation (client-side)
    roundEndTime: null,  // Unix timestamp for round end
    votingStartTime: null,  // Unix timestamp for voting start
    votingDuration: null  // Duration in seconds
};

// DOM elements
const screens = {
    lobby: document.getElementById('lobby-screen'),
    game: document.getElementById('game-screen'),
    transition: document.getElementById('transition-screen'),
    selection: document.getElementById('selection-screen'),
    voting: document.getElementById('voting-screen'),
    results: document.getElementById('results-screen'),
    gameover: document.getElementById('gameover-screen')
};

// Avatar image cache for performance (prevents repeated HTTP requests)
// Avatar images are now embedded inline - no preloading or HTTP requests needed!

// Onboarding (How to Play) - Bud messages
const onboarding = {
    messages: [
        "Welcome to PromptCraft! Enter your name above to join.",
        "Hi there! I'm Bud. Click me to learn how the game works...",
        "In each round, we'll give you an image to target. Your mission is to write prompts that generate an image as close as you can to the target.",
        "Think of it like describing what you see to an AI artist! You'll get 5 minutes each round and you can submit as many prompts as you want during that time.",
        "At the end of each round, you'll see all the images you generated. Pick the one that matches the target best. That's the one you'll submit for others to see!",
        "Then you get to vote on which image looks most like the target! You'll earn a point for every vote your image receives.",
        "Orange and Green players will sit apart but there are no teams – it's every player for themselves. The Gamemaster will assign your group soon.",
        "We'll play 3 rounds in total. We'll let you know when we're about to begin. Have fun!"
    ],
    index: 0,
    initialized: false,
    animTimer: null
};

function onboardingStartTalking() {
    const img = document.getElementById('onboarding-bud-img');
    if (!img) return;
    // Avoid multiple timers
    onboardingStopTalking();
    let showTalking = false;
    onboarding.animTimer = setInterval(() => {
        showTalking = !showTalking;
        // Use inline SVG data instead of HTTP requests
        const svgKey = showTalking ? 'bud/bud_talking' : 'bud/bud_smiling';
        const svgContent = inlineSVGData[svgKey];
        if (svgContent) {
            img.innerHTML = svgContent;
        }
    }, 500);
}

function onboardingStopTalking() {
    if (onboarding.animTimer) {
        clearInterval(onboarding.animTimer);
        onboarding.animTimer = null;
    }
    const img = document.getElementById('onboarding-bud-img');
    if (img) {
        // Use inline SVG data instead of HTTP requests
        const svgContent = inlineSVGData['bud/bud_smiling'];
        if (svgContent) {
            img.innerHTML = svgContent;
        }
    }
}

function setOnboardingMessage(index) {
    const bubble = document.getElementById('onboarding-bubble');
    const text = document.getElementById('onboarding-text');
    const prevBtn = document.getElementById('onboarding-prev');
    const nextBtn = document.getElementById('onboarding-next');
    const budImg = document.getElementById('onboarding-bud-img');
    if (!bubble || !text || !prevBtn || !nextBtn) return;
    onboarding.index = Math.max(0, Math.min(index, onboarding.messages.length - 1));
    text.textContent = onboarding.messages[onboarding.index];
    bubble.style.display = 'block';
    prevBtn.disabled = onboarding.index === 0;
    
    // Initialize avatar with inline SVG if not already set
    if (budImg && !budImg.innerHTML && inlineSVGData) {
        const svgContent = inlineSVGData['bud/bud_smiling'];
        if (svgContent) {
            budImg.innerHTML = svgContent;
        }
    }
    nextBtn.disabled = onboarding.index === onboarding.messages.length - 1;
    // Animate Bud while a message is displayed
    onboardingStartTalking();
    // Progressive checklist appears starting from message 2 (index >= 1)
    const showCount = Math.max(0, onboarding.index); // index 1 => show first list item (2)
    const items = [
        document.getElementById('ob-item-2'),
        document.getElementById('ob-item-3'),
        document.getElementById('ob-item-4'),
        document.getElementById('ob-item-5'),
        document.getElementById('ob-item-6'),
        document.getElementById('ob-item-7')
    ];
    items.forEach((el, i) => {
        if (!el) return;
        // With the added welcome message at index 0,
        // show the first list item starting at message index 2 (i.e., i + 2)
        if (onboarding.index >= (i + 2)) {
            el.classList.remove('hidden');
            el.classList.add('visible');
        }
    });
}

function initOnboardingIfNeeded() {
    if (onboarding.initialized) return;
    const avatar = document.getElementById('onboarding-avatar');
    const prevBtn = document.getElementById('onboarding-prev');
    const nextBtn = document.getElementById('onboarding-next');
    if (!avatar || !prevBtn || !nextBtn) return;
    onboarding.initialized = true;
    setOnboardingMessage(0); // Show first message automatically
    avatar.addEventListener('click', () => setOnboardingMessage(onboarding.index + 1));
    nextBtn.addEventListener('click', () => setOnboardingMessage(onboarding.index + 1));
    prevBtn.addEventListener('click', () => setOnboardingMessage(onboarding.index - 1));
}
// Ensure onboarding shows immediately on landing in the lobby
document.addEventListener('DOMContentLoaded', () => {
    initOnboardingIfNeeded();
});
// Utility function to show screen
function showScreen(screenName) {
    Object.values(screens).forEach(screen => screen.classList.remove('active'));
    screens[screenName].classList.add('active');
}

// Lobby handlers
function joinGame() {
    const nameInput = document.getElementById('player-name');
    const name = nameInput.value.trim();

    if (name) {
        gameState.playerName = name;
        socket.emit('join_game', { name: name });
    } else {
        alert('Please enter your name');
    }
}

document.getElementById('join-btn').addEventListener('click', joinGame);

// Allow Enter to join game in lobby
document.getElementById('player-name').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        joinGame();
    }
});

document.getElementById('assign-teams-btn').addEventListener('click', () => {
    socket.emit('assign_teams');
});

document.getElementById('start-game-btn').addEventListener('click', () => {
    socket.emit('start_game');
});

document.getElementById('restart-game-btn').addEventListener('click', () => {
    if (confirm('Are you sure you want to restart the game? This will reset all players and create a new game session.')) {
        socket.emit('restart_game');
    }
});

// Game screen handlers
document.getElementById('generate-btn').addEventListener('click', () => {
    const promptInput = document.getElementById('prompt-input');
    const prompt = promptInput.value.trim();

    if (prompt) {
        socket.emit('send_prompt', { prompt: prompt });
        promptInput.value = '';
    }
});

// Allow Enter to send (with Shift+Enter for new line)
document.getElementById('prompt-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        document.getElementById('generate-btn').click();
    }
});

// Image selection
document.getElementById('confirm-selection-btn').addEventListener('click', () => {
    if (gameState.selectedImageIndex !== null) {
        // Mark as confirmed before notifying server
        gameState.hasConfirmedSelection = true;
        // Send prompt_id instead of image_index to avoid index mismatch (client filters errors, server doesn't)
        const selectedImage = gameState.generatedImages[gameState.selectedImageIndex];
        socket.emit('select_image', { 
            prompt_id: selectedImage.prompt_id,
            image_index: gameState.selectedImageIndex  // Keep for backward compatibility/validation
        });
        
        // Change button appearance to show it's been confirmed
        const confirmBtn = document.getElementById('confirm-selection-btn');
        if (confirmBtn) {
            confirmBtn.style.background = '#51cf66'; // Green color
            confirmBtn.textContent = 'Selection Confirmed';
            confirmBtn.disabled = true;
        }
    }
});

// Handle image selection response from server
socket.on('image_selected', (data) => {
    if (!data.success) {
        // Server rejected the selection (error image or missing prompt_id)
        console.error('[CLIENT] Image selection rejected:', data.error);
        gameState.hasConfirmedSelection = false; // Reset confirmation state
        
        // Reset button appearance
        const confirmBtn = document.getElementById('confirm-selection-btn');
        if (confirmBtn) {
            confirmBtn.style.background = ''; // Reset to default
            confirmBtn.textContent = 'Confirm Selection';
            confirmBtn.disabled = false;
        }
        
        // Show error message to user
        alert(data.error || 'Cannot select this image. Please choose a different one.');
        
        // Find and select the last valid image instead
        if (gameState.generatedImages.length > 0) {
            let lastValidIndex = -1;
            for (let i = gameState.generatedImages.length - 1; i >= 0; i--) {
                if (!gameState.generatedImages[i].error_type && gameState.generatedImages[i].prompt_id) {
                    lastValidIndex = i;
                    break;
                }
            }
            
            if (lastValidIndex >= 0) {
                gameState.selectedImageIndex = lastValidIndex;
                // Update visual selection
                const gallery = document.getElementById('selection-gallery');
                if (gallery) {
                    const items = gallery.querySelectorAll('.selection-item');
                    items.forEach((item, idx) => {
                        item.classList.remove('selected');
                        if (idx === lastValidIndex) {
                            item.classList.add('selected');
                        }
                    });
                }
            }
        }
    }
    // If success is true, the button state is already updated above
});

// Next round
document.getElementById('next-round-btn').addEventListener('click', () => {
    socket.emit('next_round');
});

// Back to Home (non-admin only)
document.getElementById('back-to-home-btn')?.addEventListener('click', () => {
    if (!gameState.isAdmin) {
        socket.emit('back_to_home');
    }
});

// Socket event handlers
socket.on('connect', () => {
    console.log('Connected to server');
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
});

socket.on('game_joined', (data) => {
    console.log('game_joined event received:', data);
    
    try {
        gameState.playerName = data.player.name;
        gameState.playerTeam = data.player.team;
        gameState.playerCharacter = data.player.character;
        gameState.isAdmin = data.player.is_admin;

        const playerDisplayName = document.getElementById('player-display-name');
        if (playerDisplayName) {
            playerDisplayName.textContent = data.player.name;
        }
        
        // Team display removed from header - no longer showing team subtext
        
        const playerScore = document.getElementById('player-score');
        if (playerScore) {
            playerScore.textContent = data.player.score;
        }

        // Show admin controls if admin (but hide admin screen - they're a player in lobby)
        if (data.player.is_admin) {
            const adminControls = document.getElementById('admin-controls');
            if (adminControls) {
                adminControls.style.display = 'flex';
            }
        }

        // Update lobby player list
        if (data.lobby_players) {
            updatePlayerList(data.lobby_players);
        }

        // Initialize onboarding (non-admin only, lobby screen)
        if (!gameState.isAdmin && screens.lobby && screens.lobby.classList.contains('active')) {
        initOnboardingIfNeeded();
        // Auto-advance Bud to the next message after player enters their name and joins
        if (onboarding.initialized && onboarding.messages.length > 1) {
            setOnboardingMessage(1);
        }
        }

        console.log('Joined game as', data.player.name);
    } catch (error) {
        console.error('Error in game_joined handler:', error);
    }
});

// Admin-specific event handlers
socket.on('admin_joined', (data) => {
    console.log('admin_joined event received:', data);
    gameState.isAdmin = true;
    
    // Show admin screen in lobby
    const adminScreen = document.getElementById('admin-screen');
    const adminControls = document.getElementById('admin-controls');
    if (adminScreen) {
        adminScreen.style.display = 'block';
    }
    if (adminControls) {
        adminControls.style.display = 'flex';
    }
    
    // Update admin player list
    updateAdminPlayerList(data.players);
});

socket.on('admin_game_started', (data) => {
    console.log('admin_game_started event received:', data);
    
    // Ensure admin screen is visible
    const adminScreen = document.getElementById('admin-screen');
    if (adminScreen) {
        adminScreen.style.display = 'block';
    }
    
    // Show admin game controls
    const adminGameControls = document.getElementById('admin-game-controls');
    if (adminGameControls) {
        adminGameControls.style.display = 'block';
    }
    
    // Update admin status (no target description - removed)
    document.getElementById('admin-round').textContent = data.round;
    document.getElementById('admin-status').textContent = 'Playing';
    document.getElementById('admin-target').textContent = `Round ${data.round} Target`;
    
    // Store round end time for client-side calculation
    if (data.round_end_time) {
        gameState.roundEndTime = data.round_end_time;
    }
    
    // Update time remaining (initial value)
    if (data.time_remaining !== null && data.time_remaining !== undefined) {
        const minutes = Math.floor(data.time_remaining / 60);
        const seconds = Math.floor(data.time_remaining % 60);
        document.getElementById('admin-time-remaining').textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    } else {
        document.getElementById('admin-time-remaining').textContent = '-';
    }
    
    // Start client-side time calculation (no server polling)
    startAdminTimeCalculation();
    
    // Update admin player list
    updateAdminPlayerList(data.players);
});

socket.on('admin_voting_started', (data) => {
    console.log('admin_voting_started event received:', data);
    
    // Ensure admin screen is visible
    const adminScreen = document.getElementById('admin-screen');
    if (adminScreen) {
        adminScreen.style.display = 'block';
    }
    
    // Store voting start time and duration for client-side calculation
    if (data.voting_start_time && data.voting_duration) {
        gameState.votingStartTime = data.voting_start_time;
        gameState.votingDuration = data.voting_duration;
    }
    
    // Update admin status
    document.getElementById('admin-status').textContent = 'Voting (Selection)';
    
    // Calculate initial time remaining
    if (data.voting_start_time && data.voting_duration) {
        const elapsed = (Date.now() / 1000) - data.voting_start_time;
        const remaining = Math.max(0, data.voting_duration - elapsed);
        const minutes = Math.floor(remaining / 60);
        const seconds = Math.floor(remaining % 60);
        document.getElementById('admin-time-remaining').textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    } else {
        document.getElementById('admin-time-remaining').textContent = '0:30';
    }
    
    // Start client-side time calculation for voting
    startAdminTimeCalculation();
    
    // Update admin player list with selection status
    updateAdminPlayerList(data.players);
});

socket.on('player_status_update', (data) => {
    console.log('player_status_update received:', data.players?.length || 0, 'players, isAdmin:', gameState.isAdmin);
    if (data.players) {
        console.log('Team assignments in update:', data.players.map(p => ({name: p.name, team: p.team})));
    }
    if (gameState.isAdmin) {
        updateAdminPlayerList(data.players);
    } else {
        console.warn('player_status_update received but user is not admin');
    }
});

// Note: admin_status handler removed - we no longer poll for status updates
// All updates now come via events (player_prompt_updated, player_selected_image, player_voted, etc.)

socket.on('admin_status_update', (data) => {
    if (gameState.isAdmin) {
        document.getElementById('admin-status').textContent = data.status;
        if (data.round) {
            document.getElementById('admin-round').textContent = data.round;
        }
    }
});

// Client-side time calculation (no server polling)
function startAdminTimeCalculation() {
    // Clear any existing timer
    if (adminTimerInterval) {
        clearInterval(adminTimerInterval);
    }
    
    // Update time remaining every second using client-side calculation
    adminTimerInterval = setInterval(() => {
        if (!gameState.isAdmin) {
            clearInterval(adminTimerInterval);
            adminTimerInterval = null;
            return;
        }
        
        const timeEl = document.getElementById('admin-time-remaining');
        if (!timeEl) return;
        
        let timeRemaining = null;
        
        // Calculate based on round end time (during gameplay)
        if (gameState.roundEndTime) {
            const now = Date.now() / 1000;
            timeRemaining = Math.max(0, gameState.roundEndTime - now);
        }
        // Calculate based on voting start time (during voting)
        else if (gameState.votingStartTime && gameState.votingDuration) {
            const now = Date.now() / 1000;
            const elapsed = now - gameState.votingStartTime;
            timeRemaining = Math.max(0, gameState.votingDuration - elapsed);
        }
        
        if (timeRemaining !== null) {
            const minutes = Math.floor(timeRemaining / 60);
            const seconds = Math.floor(timeRemaining % 60);
            timeEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        } else {
            timeEl.textContent = '-';
        }
    }, 1000);
}

let adminTimerInterval = null;

socket.on('player_prompt_updated', (data) => {
    // Update real-time prompts count in admin dashboard
    if (gameState.isAdmin) {
        // Update the specific player's prompts count in the admin list
        const adminPlayerList = document.getElementById('admin-player-list');
        if (adminPlayerList) {
            // Find and update the player's item
            const items = adminPlayerList.querySelectorAll('.admin-player-item');
            items.forEach(item => {
                const nameElement = item.querySelector('strong');
                if (nameElement && nameElement.textContent === data.player_name) {
                    // Update prompts count in the item
                    const promptsText = item.querySelector('.prompts-count');
                    if (promptsText) {
                        promptsText.textContent = `Prompts: ${data.prompts_submitted}`;
                    } else {
                        // Add prompts count if it doesn't exist
                        const infoDiv = item.querySelector('div');
                        if (infoDiv) {
                            const promptsElement = document.createElement('small');
                            promptsElement.className = 'prompts-count';
                            promptsElement.textContent = `Prompts: ${data.prompts_submitted}`;
                            promptsElement.style.display = 'block';
                            infoDiv.appendChild(promptsElement);
                        }
                    }
                }
            });
        }
    }
});

socket.on('player_selected_image', (data) => {
    // Update admin dashboard when a player selects an image
    if (gameState.isAdmin) {
        const adminPlayerList = document.getElementById('admin-player-list');
        if (adminPlayerList) {
            const items = adminPlayerList.querySelectorAll('.admin-player-item');
            items.forEach(item => {
                const nameElement = item.querySelector('strong');
                if (nameElement && nameElement.textContent === data.player_name) {
                    // Update selection status
                    const selectionStatus = item.querySelector('.selection-status');
                    if (selectionStatus) {
                        selectionStatus.textContent = '✓ Selected';
                    } else {
                        // Add selection status if it doesn't exist
                        const infoDiv = item.querySelector('div');
                        if (infoDiv) {
                            const selectionElement = document.createElement('small');
                            selectionElement.className = 'selection-status';
                            selectionElement.textContent = '✓ Selected';
                            selectionElement.style.cssText = 'display: block; color: #4caf50;';
                            infoDiv.appendChild(selectionElement);
                        }
                    }
                }
            });
        }
    }
});

socket.on('player_voted', (data) => {
    // Update admin dashboard when a player votes
    if (gameState.isAdmin) {
        const adminPlayerList = document.getElementById('admin-player-list');
        if (adminPlayerList) {
            const items = adminPlayerList.querySelectorAll('.admin-player-item');
            items.forEach(item => {
                const nameElement = item.querySelector('strong');
                if (nameElement && nameElement.textContent === data.player_name) {
                    // Update vote status
                    const voteStatus = item.querySelector('.vote-status');
                    if (voteStatus) {
                        voteStatus.textContent = '✓ Voted';
                    } else {
                        // Add vote status if it doesn't exist
                        const infoDiv = item.querySelector('div');
                        if (infoDiv) {
                            const voteElement = document.createElement('small');
                            voteElement.className = 'vote-status';
                            voteElement.textContent = '✓ Voted';
                            voteElement.style.cssText = 'display: block; color: #4caf50;';
                            infoDiv.appendChild(voteElement);
                        }
                    }
                }
            });
        }
    }
});

function updateAdminPlayerList(players) {
    const adminPlayerList = document.getElementById('admin-player-list');
    if (!adminPlayerList) return;
    
    adminPlayerList.innerHTML = '<h3>Players</h3>';
    
    // Check if we're in lobby (gameState.currentRound === 0 means lobby)
    const isInLobby = gameState.currentRound === 0;
    
    // Add "Clear Lobby" button at the top (only show in lobby)
    if (isInLobby) {
        const clearLobbyBtn = document.createElement('button');
        clearLobbyBtn.className = 'btn btn-danger';
        clearLobbyBtn.style.cssText = 'margin-bottom: 15px; width: 100%; padding: 10px;';
        clearLobbyBtn.textContent = '🗑️ Clear All Players';
        clearLobbyBtn.addEventListener('click', () => {
            if (confirm('Are you sure you want to remove all players from the lobby?')) {
                socket.emit('clear_lobby');
            }
        });
        adminPlayerList.appendChild(clearLobbyBtn);
    }
    
    players.forEach(player => {
        if (player.is_admin) return; // Skip admin in list
        
        const item = document.createElement('div');
        item.className = 'admin-player-item';
        item.style.cssText = 'padding: 10px; margin: 5px 0; border: 1px solid #ddd; border-radius: 5px; display: flex; justify-content: space-between; align-items: center;';
        
        const statusColor = player.is_connected ? '#4caf50' : '#f44336';
        const statusText = player.is_connected ? '● Connected' : '○ Disconnected';
        const promptsSubmitted = player.prompts_submitted !== undefined ? player.prompts_submitted : 0;
        const selectionStatus = player.has_selected !== undefined ? (player.has_selected ? '✓ Selected' : '⏳ Selecting') : '';
        const voteStatus = player.has_voted !== undefined ? (player.has_voted ? '✓ Voted' : '⏳ Voting') : '';
        const scoreText = player.score !== undefined ? `Score: ${player.score}` : '';
        
        // Create left side with player info
        const leftDiv = document.createElement('div');
        leftDiv.style.cssText = 'flex: 1;';
        
        // Player name and team dropdown (only in lobby)
        const nameRow = document.createElement('div');
        nameRow.style.cssText = 'display: flex; align-items: center; gap: 10px; margin-bottom: 5px;';
        
        const nameStrong = document.createElement('strong');
        nameStrong.textContent = player.name;
        nameRow.appendChild(nameStrong);
        
        // Team dropdown (only in lobby, only for non-admin players)
        if (isInLobby && !player.is_admin) {
            const teamSelect = document.createElement('select');
            teamSelect.className = 'team-select';
            teamSelect.style.cssText = 'padding: 2px 5px; border: 1px solid #ddd; border-radius: 3px; font-size: 12px;';
            
            // Add options first
            const optionNone = document.createElement('option');
            optionNone.value = '';
            optionNone.textContent = 'No Team';
            teamSelect.appendChild(optionNone);
            
            const optionGreen = document.createElement('option');
            optionGreen.value = 'Green';
            optionGreen.textContent = 'Green';
            teamSelect.appendChild(optionGreen);
            
            const optionOrange = document.createElement('option');
            optionOrange.value = 'Orange';
            optionOrange.textContent = 'Orange';
            teamSelect.appendChild(optionOrange);
            
            // Set value AFTER options are added to ensure it works correctly
            // Handle null/undefined team values - explicitly convert to empty string for "No Team"
            const teamValue = (player.team && (player.team === 'Green' || player.team === 'Orange')) ? player.team : '';
            console.log(`Setting dropdown for ${player.name}: team="${player.team}" -> value="${teamValue}"`);
            teamSelect.value = teamValue;
            
            // Handle team change
            teamSelect.addEventListener('change', (e) => {
                const newTeam = e.target.value;
                if (newTeam && newTeam !== player.team) {
                    if (confirm(`Change ${player.name}'s team to ${newTeam}?`)) {
                        socket.emit('set_player_team', {
                            session_id: player.session_id,
                            team: newTeam
                        });
                    } else {
                        // Revert dropdown
                        teamSelect.value = player.team || '';
                    }
                }
            });
            
            nameRow.appendChild(teamSelect);
        } else {
            // Show team as text (not in lobby or during game)
            const teamSpan = document.createElement('span');
            teamSpan.textContent = `(${player.team ? player.team : '?'})`;
            teamSpan.style.cssText = 'color: #666; font-size: 12px;';
            nameRow.appendChild(teamSpan);
        }
        
        leftDiv.appendChild(nameRow);
        
        // Status and info
        const infoDiv = document.createElement('div');
        infoDiv.innerHTML = `
            <small style="color: ${statusColor}">${statusText}</small>
            <br><small class="prompts-count">Prompts: ${promptsSubmitted}</small>
            ${selectionStatus ? `<br><small>${selectionStatus}</small>` : ''}
            ${voteStatus ? `<br><small>${voteStatus}</small>` : ''}
        `;
        leftDiv.appendChild(infoDiv);
        
        // Create right side with score and remove button
        const rightDiv = document.createElement('div');
        rightDiv.style.cssText = 'display: flex; align-items: center; gap: 10px;';
        
        if (scoreText) {
            const scoreDiv = document.createElement('div');
            scoreDiv.textContent = scoreText;
            rightDiv.appendChild(scoreDiv);
        }
        
        // Add remove button (only in lobby)
        if (isInLobby) {
            const removeBtn = document.createElement('button');
            removeBtn.className = 'btn btn-danger';
            removeBtn.style.cssText = 'padding: 5px 10px; font-size: 0.8em; min-width: 60px;';
            removeBtn.textContent = '✕ Remove';
            removeBtn.addEventListener('click', () => {
                if (confirm(`Remove ${player.name} from the lobby?`)) {
                    socket.emit('remove_player', { session_id: player.session_id });
                }
            });
            rightDiv.appendChild(removeBtn);
        }
        
        item.appendChild(leftDiv);
        item.appendChild(rightDiv);
        adminPlayerList.appendChild(item);
    });
}

// Admin control button handlers
document.getElementById('admin-end-round-btn')?.addEventListener('click', () => {
    if (confirm('End the current round early and move to image selection?')) {
        socket.emit('admin_end_round');
    }
});

document.getElementById('admin-skip-voting-btn')?.addEventListener('click', () => {
    socket.emit('skip_voting');
});

document.getElementById('admin-next-round-btn')?.addEventListener('click', () => {
    socket.emit('next_round');
});

socket.on('lobby_players_update', (data) => {
    console.log('lobby_players_update received:', data.players?.length || 0, 'players');
    updatePlayerList(data.players);
});

function updatePlayerList(players) {
    const playerList = document.getElementById('player-list');
    if (!playerList) {
        console.error('player-list element not found');
        return;
    }
    playerList.innerHTML = '';
    
    // Count non-admin players
    let nonAdminCount = 0;
    
    // Find current player's team for inline message
    const currentPlayer = players.find(p => p.name === gameState.playerName);
    const currentPlayerTeam = currentPlayer ? currentPlayer.team : null;
    
    // Update inline team message
    const lobbyInfo = document.querySelector('.lobby-info');
    if (lobbyInfo) {
        // Remove existing team message if present
        const existingTeamMsg = lobbyInfo.querySelector('.player-team-message');
        if (existingTeamMsg) {
            existingTeamMsg.remove();
        }
        
        // Add team message if player has a team
        if (currentPlayerTeam && !gameState.isAdmin) {
            const teamMsg = document.createElement('span');
            teamMsg.className = 'player-team-message';
            teamMsg.style.cssText = 'margin-left: 10px; font-size: 1rem;';
            const teamColor = currentPlayerTeam === 'Green' ? '#155724' : '#cc6600';
            teamMsg.innerHTML = ` | You are <strong style="color: ${teamColor};">${currentPlayerTeam}</strong>`;
            const lobbyCountEl = document.getElementById('lobby-count');
            if (lobbyCountEl && lobbyCountEl.parentNode) {
                lobbyCountEl.parentNode.appendChild(teamMsg);
            }
        }
    }
    
    players.forEach(player => {
        const item = document.createElement('div');
        item.className = 'player-item';
        
        // Determine badge text and styling
        let badgeText = '';
        let badgeClass = '';
        let badgeStyle = '';
        if (player.is_admin) {
            badgeText = 'Admin';
            badgeStyle = 'background: #667eea; color: white;';
        } else {
            nonAdminCount++;
            if (player.team) {
                badgeText = player.team; // Just show "Green" or "Orange"
                badgeClass = `team-${player.team}`; // Apply CSS class for color
        } else {
            badgeText = 'Waiting';
            badgeStyle = 'background: #e0e0e0;';
            }
        }
        
        // Connection status removed from lobby display (still tracked for admin dashboard)
        
        item.innerHTML = `
            <span>${player.name}</span>
            <span class="player-team-badge ${badgeClass}" style="${badgeStyle}">${badgeText}</span>
        `;
        playerList.appendChild(item);
    });
    
    const lobbyCountEl = document.getElementById('lobby-count');
    if (lobbyCountEl) {
        lobbyCountEl.textContent = nonAdminCount;
    }
}

socket.on('game_started', (data) => {
    // Don't handle game events if user is admin
    if (gameState.isAdmin) {
        return;
    }
    
    gameState.currentRound = data.round;
    gameState.generatedImages = [];
    gameState.selectedImageIndex = null;
    
    // Reset avatar animation
    stopCharacterTalking();
    // Hide message bubble
    const messageBubble = document.getElementById('character-bubble');
    if (messageBubble) {
        messageBubble.style.display = 'none';
    }

    document.getElementById('round-number').textContent = data.round;
    
    // Display target image
    const targetImage = document.getElementById('target-image-display');
    targetImage.src = data.target.url;
    targetImage.alt = 'Target Image';

    // Clear conversation area
    const conversationArea = document.getElementById('conversation-area');
    conversationArea.innerHTML = '<p class="empty-conversation">Start generating images by typing a prompt below</p>';

    // Set up initial avatar state based on character data from server
    if (data.character) {
        updateAvatarState(data.character);
        
        // Display welcome message if present (lasts 20 seconds or until first prompt)
        if (data.character.message) {
            const messageBubble = document.getElementById('character-bubble');
            const messageText = document.getElementById('character-bubble-text');
            
            // Clear any existing message auto-hide timer
            if (gameState.messageAutoHideTimer) {
                clearTimeout(gameState.messageAutoHideTimer);
                gameState.messageAutoHideTimer = null;
            }
            
            // Display the welcome message
            messageText.textContent = data.character.message;
            messageBubble.style.display = 'block';
            
            // Style based on character
            if (data.character.character === 'Spud') {
                messageBubble.style.background = '#ffe8e8';
                messageBubble.style.borderLeft = '4px solid #ff6b6b';
                messageBubble.style.setProperty('--bubble-color', '#ffe8e8');
            } else {
                messageBubble.style.background = '#fff3bf';
                messageBubble.style.borderLeft = '4px solid #fab005';
                messageBubble.style.setProperty('--bubble-color', '#fff3bf');
            }
            
            // Auto-hide message after 20 seconds
            gameState.messageAutoHideTimer = setTimeout(() => {
                messageBubble.style.display = 'none';
                stopCharacterTalking();
                // Return to static animation state (no message)
                updateAvatarState({
                    character: data.character.character,
                    animation_state: data.character.animation_state,
                    plant_state: data.character.plant_state,
                    message: null
                });
                gameState.messageAutoHideTimer = null;
            }, 20000);  // 20 seconds
        }
    } else {
        // Fallback: use old setupCharacterAvatar if no character data
    setupCharacterAvatar();
    }

    showScreen('game');

    // Start timer
    startRoundTimer(data.end_time);
});

/**
 * Load and display avatar SVG based on character and state (using inline SVGs)
 */
function loadAvatarSVG(character, plantState = null, animationState = 'smiling') {
    const avatarContainer = document.getElementById('avatar-svg-container');
    const avatarLarge = document.getElementById('character-avatar-large');
    
    if (!avatarContainer || !avatarLarge) return;
    
    // Build the key for the inline SVG data
    let svgKey = '';
    if (character === 'Bud') {
        svgKey = `bud/bud_${animationState}`;
        avatarLarge.className = 'character-avatar-large';
    } else if (character === 'Spud') {
        svgKey = `spud/${plantState}/spud_${plantState}_${animationState}`;
        avatarLarge.className = 'character-avatar-large spuddy';
        
        // Add wilted class for visual effect
        if (plantState === 'yellow') {
            avatarLarge.classList.add('wilted-light');
        } else if (plantState === 'dry') {
            avatarLarge.classList.add('wilted');
        } else {
            avatarLarge.classList.remove('wilted', 'wilted-light');
        }
    }
    
    // Get SVG content from inline data
    const svgContent = inlineSVGData[svgKey];
    if (svgContent) {
        // Inject inline SVG directly into container (no HTTP request!)
        avatarContainer.innerHTML = svgContent;
        avatarContainer.style.display = 'block';
    } else {
        console.error(`SVG not found in inline data: ${svgKey}`);
        // Fallback logic for missing SVGs
        if (character === 'Spud') {
            if (animationState === 'talking' && plantState !== 'base') {
                if (plantState === 'yellow') {
                    loadAvatarSVG('Spud', 'yellow', 'welling');
                } else if (plantState === 'dry') {
                    loadAvatarSVG('Spud', 'dry', 'sad');
                }
            } else if (animationState !== 'smiling') {
                loadAvatarSVG('Spud', plantState, 'smiling');
            } else if (plantState !== 'base') {
                loadAvatarSVG('Spud', 'base', 'smiling');
            }
        } else if (character === 'Bud' && animationState !== 'smiling') {
            loadAvatarSVG('Bud', null, 'smiling');
        }
        return;
    }
    
    // Store current state
    gameState.currentCharacter = character;
    gameState.avatarPlantState = plantState;
    gameState.avatarAnimationState = animationState;
}

/**
 * Animate character talking (alternate between base state and talking state)
 */
function animateCharacterTalking(character, plantState, baseState) {
    // Clear any existing animation
    if (gameState.avatarAnimationInterval) {
        clearInterval(gameState.avatarAnimationInterval);
        gameState.avatarAnimationInterval = null;
    }
    
    // Determine talking state based on base state and character
    let talkingState;
    if (character === 'Bud') {
        // Bud cycles through: smiling -> talking -> sad_talking
        // This is handled separately in animateBudTalking
        return;
    } else if (character === 'Spud') {
        if (baseState === 'smiling') {
            talkingState = 'talking';
        } else if (baseState === 'sad') {
            talkingState = 'sad_talking';
        } else if (baseState === 'welling') {
            talkingState = 'crying';
        } else {
            // Already in a talking state, don't animate
            return;
        }
    } else {
        return;
    }
    
    // Alternate between base state and talking state every 500ms
    let showingTalking = false;
    gameState.avatarAnimationInterval = setInterval(() => {
        const stateToShow = showingTalking ? talkingState : baseState;
        loadAvatarSVG(character, plantState, stateToShow);
        showingTalking = !showingTalking;
    }, 500);
}

/**
 * Animate Bud talking (cycle through: smiling -> talking)
 */
function animateBudTalking() {
    // Clear any existing animation
    if (gameState.avatarAnimationInterval) {
        clearInterval(gameState.avatarAnimationInterval);
        gameState.avatarAnimationInterval = null;
    }
    
    // Cycle through: smiling -> talking -> smiling...
    const states = ['smiling', 'talking'];
    let currentIndex = 0;
    
    gameState.avatarAnimationInterval = setInterval(() => {
        loadAvatarSVG('Bud', null, states[currentIndex]);
        currentIndex = (currentIndex + 1) % states.length;
    }, 500);
}

/**
 * Stop character talking animation
 */
function stopCharacterTalking() {
    if (gameState.avatarAnimationInterval) {
        clearInterval(gameState.avatarAnimationInterval);
        gameState.avatarAnimationInterval = null;
    }
}

/**
 * Update avatar state based on character data
 */
function updateAvatarState(characterData) {
    if (!characterData) return;
    
    const character = characterData.character;
    const animationState = characterData.animation_state || 'smiling';
    const plantState = characterData.plant_state || 'base';
    const hasMessage = characterData.message && characterData.message.trim() !== '';
    
    // Stop any existing animation
    stopCharacterTalking();
    
    if (character === 'Bud') {
        // Bud: static pose is always smiling
        // When message appears, animate through: smiling -> talking -> sad_talking
        if (hasMessage) {
            // Start animation cycle
            animateBudTalking();
        } else {
            // No message: return to static pose (smiling)
            loadAvatarSVG('Bud', null, 'smiling');
        }
    } else if (character === 'Spud') {
        // Spud: animation depends on plant state and prompt count
        if (hasMessage) {
            // Message exists: animate based on static pose
            if (animationState === 'smiling') {
                // Base plant: animate between smiling and talking
                animateCharacterTalking('Spud', plantState, 'smiling');
            } else if (animationState === 'sad') {
                // Yellow/dry plant (prompts 1-6): animate between sad and sad_talking
                animateCharacterTalking('Spud', plantState, 'sad');
            } else if (animationState === 'welling') {
                // Dry plant (prompts 7+): animate between welling and crying
                animateCharacterTalking('Spud', plantState, 'welling');
            } else {
                // Fallback: just show the static state
                loadAvatarSVG('Spud', plantState, animationState);
            }
        } else {
            // No message: return to static pose
            loadAvatarSVG('Spud', plantState, animationState);
        }
    }
}

socket.on('character_message', (data) => {
    const messageBubble = document.getElementById('character-bubble');
    const messageText = document.getElementById('character-bubble-text');

    // Clear any existing message auto-hide timer
    if (gameState.messageAutoHideTimer) {
        clearTimeout(gameState.messageAutoHideTimer);
        gameState.messageAutoHideTimer = null;
    }

    // Update avatar state
    updateAvatarState(data);

    // Update message bubble (messages stay until replaced or 20 seconds pass)
    if (data.message) {
    messageText.textContent = data.message;
    messageBubble.style.display = 'block';

        // Style based on character
        if (data.character === 'Spud') {
        messageBubble.style.background = '#ffe8e8';
        messageBubble.style.borderLeft = '4px solid #ff6b6b';
            // Update bubble arrow color
            messageBubble.style.setProperty('--bubble-color', '#ffe8e8');
    } else {
        messageBubble.style.background = '#fff3bf';
        messageBubble.style.borderLeft = '4px solid #fab005';
            messageBubble.style.setProperty('--bubble-color', '#fff3bf');
        }
        
        // Auto-hide message after 20 seconds and return to static pose
        gameState.messageAutoHideTimer = setTimeout(() => {
            messageBubble.style.display = 'none';
            stopCharacterTalking();
            // Return to static animation state (no message)
            updateAvatarState({
                character: data.character,
                animation_state: data.animation_state,
                plant_state: data.plant_state,
                message: null  // Explicitly no message to trigger static pose
            });
            gameState.messageAutoHideTimer = null;
        }, 20000);  // 20 seconds
    } else {
        // No message - hide bubble and return to static pose
        messageBubble.style.display = 'none';
        // Stop any talking animation and return to static pose
        stopCharacterTalking();
        // Return to static animation state (no message)
        updateAvatarState({
            character: data.character,
            animation_state: data.animation_state,
            plant_state: data.plant_state,
            message: null  // Explicitly no message to trigger static pose
        });
    }
});

socket.on('image_generation_error', (data) => {
    // Note: Error messages are now shown as character messages (speech bubbles from Bud/Spud)
    // This handler is kept for logging/analytics purposes, but the character message is the primary UI
    // The character message will appear via the 'character_message' event, which is more integrated
    // into the game experience than a separate error box.
    
    // Log error for debugging (optional - can be removed if not needed)
    console.log('Image generation error:', data.error_type, data.message);

    // Replace the last loading placeholder (hourglass) with a blank placeholder so it doesn't linger
    const conversationArea = document.getElementById('conversation-area');
    if (conversationArea) {
        const imageContainers = conversationArea.querySelectorAll('.image-container');
        if (imageContainers.length > 0) {
            const lastContainer = imageContainers[imageContainers.length - 1];
            // Only replace if it is still showing the loading indicator
            if (lastContainer.querySelector('.image-loading')) {
                // Insert an empty result element so layout remains consistent but shows as blank
                lastContainer.innerHTML = '<div class="image-result error-blank"></div>';
            }
        }
    }
});

socket.on('prompt_sent', (data) => {
    // Show prompt bubble and loading placeholder
    const conversationArea = document.getElementById('conversation-area');
    
    // Remove empty message if present
    const emptyMsg = conversationArea.querySelector('.empty-conversation');
    if (emptyMsg) emptyMsg.remove();
    
    // Create conversation item
    const item = document.createElement('div');
    item.className = 'conversation-item';
    item.innerHTML = `
        <div class="prompt-bubble">${data.prompt}</div>
        <div class="image-container">
            <div class="image-loading"></div>
        </div>
    `;
    
    conversationArea.appendChild(item);
    conversationArea.scrollTop = conversationArea.scrollHeight;
});

socket.on('image_generated', (data) => {
    // Skip error images - don't add them to generatedImages or selection gallery
    if (data.error_type) {
        // Error images are handled via character error messages
        // Don't add them to the selection gallery
        return;
    }
    
    gameState.generatedImages.push(data);

    // Find the last loading image and replace with actual image
    const conversationArea = document.getElementById('conversation-area');
    const imageContainers = conversationArea.querySelectorAll('.image-container');
    
    if (imageContainers.length > 0) {
        const lastContainer = imageContainers[imageContainers.length - 1];
        // Prefer image_url over image_data to reduce memory usage
        const imageSrc = data.image_url || data.image_data || '';
        lastContainer.innerHTML = `<img src="${imageSrc}" alt="Generated image" class="image-result">`;
    }
    
    // Note: Error messages are handled separately via 'image_generation_error' event
    
    // Scroll to bottom
    if (conversationArea) {
    conversationArea.scrollTop = conversationArea.scrollHeight;
    }
    
    // If we're in selection screen, add this image to the gallery
    const selectionScreen = document.getElementById('selection-screen');
    if (selectionScreen && selectionScreen.classList.contains('active')) {
        // Only add valid (non-error) images to selection gallery
        const validImageIndex = gameState.generatedImages.length - 1;
        addImageToSelectionGallery(data, validImageIndex);
        
        // If the player hasn't confirmed a selection yet, shift default to the newest valid image
        if (!gameState.hasConfirmedSelection) {
            gameState.selectedImageIndex = validImageIndex;

            // Visual feedback - move the green border to the newest image in the gallery
            // The gallery only contains valid images, so we need to find the last item
    const gallery = document.getElementById('selection-gallery');
            if (gallery) {
                const items = gallery.querySelectorAll('.selection-item');
                if (items.length > 0) {
                    // Select the last item in the gallery (which is the newest valid image)
                    items.forEach(i => i.classList.remove('selected'));
                    items[items.length - 1].classList.add('selected');
                }
            }
            
            // Show default selection notice
            const defaultNotice = document.getElementById('default-selection-notice');
            if (defaultNotice) {
                defaultNotice.style.display = 'block';
            }
        }
    }
});

function addImageToSelectionGallery(imgData, index) {
    const gallery = document.getElementById('selection-gallery');
    if (!gallery) return;
    
    // Check if image already exists in gallery
    const existingItems = gallery.querySelectorAll('.selection-item');
    if (existingItems.length > index) return; // Already added
    
        const item = document.createElement('div');
        item.className = 'selection-item';
        // Prefer image_url over image_data to reduce memory usage
        const imageSrc = imgData.image_url || imgData.image_data || '';
        item.innerHTML = `
            <img src="${imageSrc}" alt="Generated image">
        `;

        item.addEventListener('click', () => {
            // Deselect all
            document.querySelectorAll('.selection-item').forEach(i => i.classList.remove('selected'));
            // Select this
            item.classList.add('selected');
            gameState.selectedImageIndex = index;
        const confirmBtn = document.getElementById('confirm-selection-btn');
        if (confirmBtn) {
            confirmBtn.disabled = false;
        }
        // Hide default selection notice
        const defaultNotice = document.getElementById('default-selection-notice');
        if (defaultNotice) {
            defaultNotice.style.display = 'none';
        }
        });

        gallery.appendChild(item);
}

socket.on('image_url_updated', (data) => {
    // Update image URL in client-side array when upload completes
    // This allows selection screen to use URLs instead of base64
    if (data.prompt_id && data.image_url) {
        const imageIndex = gameState.generatedImages.findIndex(img => img.prompt_id === data.prompt_id);
        if (imageIndex !== -1) {
            gameState.generatedImages[imageIndex].image_url = data.image_url;
            // Optionally clear base64 from client-side array to free memory
            if (gameState.generatedImages[imageIndex].image_data) {
                delete gameState.generatedImages[imageIndex].image_data;
            }
            
            // Update the image in the selection gallery if it exists
            const gallery = document.getElementById('selection-gallery');
            if (gallery) {
                const items = gallery.querySelectorAll('.selection-item');
                if (items[imageIndex]) {
                    const img = items[imageIndex].querySelector('img');
                    if (img) {
                        img.src = data.image_url;
                    }
                }
            }
            
            // Update the image in the conversation area if it exists
            const conversationArea = document.getElementById('conversation-area');
            if (conversationArea) {
                const imageContainers = conversationArea.querySelectorAll('.image-container');
                if (imageContainers[imageIndex]) {
                    const img = imageContainers[imageIndex].querySelector('img');
                    if (img) {
                        img.src = data.image_url;
                    }
                }
            }
        }
    }
});

socket.on('voting_started', (data) => {
    console.log('[CLIENT] voting_started event received:', data);
    
    // Don't handle voting events if user is admin
    if (gameState.isAdmin) {
        console.log('[CLIENT] Admin user, ignoring voting_started');
        return;
    }
    
    console.log('[CLIENT] Showing selection screen');
    showScreen('selection');
    
    // Reset confirmation state at the start of selection
    gameState.hasConfirmedSelection = false;
    
    // Reset confirm button appearance
    const confirmBtnReset = document.getElementById('confirm-selection-btn');
    if (confirmBtnReset) {
        confirmBtnReset.style.background = ''; // Reset to default
        confirmBtnReset.textContent = 'Confirm Selection';
        confirmBtnReset.disabled = false;
    }

    // Clear transition timer and countdown if they exist
    if (gameState.transitionTimer) {
        clearTimeout(gameState.transitionTimer);
        gameState.transitionTimer = null;
    }
    if (gameState.transitionCountdown) {
        clearInterval(gameState.transitionCountdown);
        gameState.transitionCountdown = null;
    }
    console.log('[CLIENT] Cleared transition timers');

    // Populate selection gallery with all valid (non-error) images (including any generated during buffer)
    const gallery = document.getElementById('selection-gallery');
    if (gallery) {
        gallery.innerHTML = '';

        // Filter out error images - only show valid images in selection gallery
        gameState.generatedImages.forEach((imgData, index) => {
            // Only add images without error_type
            if (!imgData.error_type) {
                addImageToSelectionGallery(imgData, index);
            }
        });
    }

    // Always show default selection UI (green border on last valid image)
    // This is UI-only - the server won't submit it until timer expires or player confirms
    const defaultNotice = document.getElementById('default-selection-notice');
    const confirmBtn = document.getElementById('confirm-selection-btn');
    
    // Show default selection notice
    if (defaultNotice) {
        defaultNotice.style.display = 'block';
    }
    
    // Auto-select last valid image in UI (default selection)
    if (gameState.generatedImages.length > 0) {
        // Find the last valid (non-error) image
        let lastValidIndex = -1;
        for (let i = gameState.generatedImages.length - 1; i >= 0; i--) {
            if (!gameState.generatedImages[i].error_type) {
                lastValidIndex = i;
                break;
            }
        }
        
        if (lastValidIndex >= 0) {
            gameState.selectedImageIndex = lastValidIndex;
            const lastItem = gallery?.querySelectorAll('.selection-item')[lastValidIndex];
            if (lastItem) {
                lastItem.classList.add('selected');
            }
        } else {
            // Fallback: use last image even if it has an error (shouldn't happen)
            const lastIndex = gameState.generatedImages.length - 1;
            gameState.selectedImageIndex = lastIndex;
            const lastItem = gallery?.querySelectorAll('.selection-item')[lastIndex];
            if (lastItem) {
                lastItem.classList.add('selected');
            }
        }
        if (confirmBtn) {
            confirmBtn.disabled = false;
        }
    }

    // Start selection timer
    // Use synchronized start time from server for timer synchronization
    startSelectionTimer(data.duration || 30, data.start_time);
});

socket.on('selection_waiting', (data) => {
    const waitingEl = document.getElementById('selection-waiting');
    const waitingCount = document.getElementById('waiting-count');
    
    if (waitingEl && waitingCount) {
        waitingEl.style.display = 'block';
        waitingCount.textContent = data.waiting_count;
    }
});

function startSelectionTimer(duration, startTime) {
    const timerEl = document.getElementById('selection-timer');
    if (!timerEl) return;
    
    // Use server-provided start time for synchronization, or fall back to current time
    const serverStartTime = startTime || (Date.now() / 1000);
    
    const updateTimer = () => {
        const now = Date.now() / 1000;
        const elapsed = now - serverStartTime;
        const timeLeft = Math.max(0, Math.floor(duration - elapsed));
        
        timerEl.textContent = timeLeft;
        
        if (timeLeft <= 10) {
            timerEl.classList.add('warning');
        } else {
            timerEl.classList.remove('warning');
        }
        
        if (timeLeft <= 0) {
            clearInterval(timerEl.timerInterval);
            timerEl.textContent = '0';
            
            // If no selection made, auto-select last valid image and notify server
            if (gameState.selectedImageIndex === null && gameState.generatedImages.length > 0) {
                const defaultNotice = document.getElementById('default-selection-notice');
                if (defaultNotice) {
                    defaultNotice.style.display = 'block';
                }
                
                // Find the last valid (non-error) image
                let lastValidIndex = -1;
                for (let i = gameState.generatedImages.length - 1; i >= 0; i--) {
                    if (!gameState.generatedImages[i].error_type) {
                        lastValidIndex = i;
                        break;
                    }
                }
                
                // Auto-select last valid image (or last image if somehow all are errors)
                let effectiveIndex;
                if (lastValidIndex >= 0) {
                    gameState.selectedImageIndex = lastValidIndex;
                    effectiveIndex = lastValidIndex;
                } else {
                    // Fallback: use last image even if it has an error (shouldn't happen)
                    effectiveIndex = gameState.generatedImages.length - 1;
                    gameState.selectedImageIndex = effectiveIndex;
                }
                
                // Visual feedback - select the last valid image in the gallery
                // Since we're always selecting the last valid image, it will be the last item in the gallery
                const gallery = document.getElementById('selection-gallery');
                if (gallery) {
                    const items = gallery.querySelectorAll('.selection-item');
                    if (items.length > 0) {
                        items.forEach(i => i.classList.remove('selected'));
                        items[items.length - 1].classList.add('selected');
                    }
                }
                
                // Notify server of auto-selection (send prompt_id to avoid index mismatch)
                const autoSelectedImage = gameState.generatedImages[effectiveIndex];
                socket.emit('select_image', { 
                    prompt_id: autoSelectedImage.prompt_id,
                    image_index: effectiveIndex  // Keep for backward compatibility
                });
                console.log('[CLIENT] Timer expired - auto-selected last valid image');
            }
            
            // Request server to check if all players are ready (will advance to voting)
            socket.emit('check_selection_status');
        }
    };
    
    // Update immediately and then every 100ms for smooth countdown
    updateTimer();
    timerEl.timerInterval = setInterval(updateTimer, 100);
}

socket.on('vote_on_images', (data) => {
    // Don't handle voting events if user is admin
    if (gameState.isAdmin) {
        return;
    }
    
    showScreen('voting');

    // Reset vote state
    gameState.tempVoteSelection = null;
    gameState.votedFor = null;

    // Reset confirm vote button
    const confirmVoteBtn = document.getElementById('confirm-vote-btn');
    if (confirmVoteBtn) {
    confirmVoteBtn.disabled = true;
    confirmVoteBtn.textContent = 'Confirm Vote';
    }

    // Display target image on the right (no description)
    const targetImageEl = document.getElementById('voting-target-image');
    if (targetImageEl && data.target_image) {
        targetImageEl.src = data.target_image.url;
        targetImageEl.alt = 'Target Image';
    }

    const gallery = document.getElementById('voting-gallery');
    if (!gallery) return;
    
    gallery.innerHTML = '';

    // Filter out player's own image
    const mySessionId = data.my_session_id;
    const otherPlayerImages = data.images.filter(item => item.session_id !== mySessionId);

    if (otherPlayerImages.length === 0) {
        gallery.innerHTML = '<p>No other players to vote for!</p>';
        return;
    }

    // Store prompt_id mapping for voting
    const promptIdMap = {};  // session_id -> prompt_id

    otherPlayerImages.forEach((item) => {
        const votingItem = document.createElement('div');
        votingItem.className = 'voting-item';
        votingItem.dataset.sessionId = item.session_id;
        
        // Store prompt_id for this session
        if (item.prompt_id) {
            promptIdMap[item.session_id] = item.prompt_id;
        }
        
        // Display only image (no player name, no prompt text) - anonymized voting
        // Support both URL and base64 (URL preferred for memory efficiency)
        const imageSrc = item.image.image_url || item.image.image_data || '';
        votingItem.innerHTML = `
            <img src="${imageSrc}" alt="Submission image">
        `;

        votingItem.addEventListener('click', () => {
            // Allow changing vote before confirmation
            if (gameState.votedFor) return; // Already confirmed vote

            // Mark as selected (but not confirmed)
            document.querySelectorAll('.voting-item').forEach(i => i.classList.remove('selected'));
            votingItem.classList.add('selected');

            gameState.tempVoteSelection = item.session_id;
            if (confirmVoteBtn) {
            confirmVoteBtn.disabled = false;
            }
        });

        gallery.appendChild(votingItem);
    });
    
    // Add confirm vote button handler (using existing confirmVoteBtn variable)
    if (confirmVoteBtn) {
    confirmVoteBtn.onclick = function() {
        if (gameState.tempVoteSelection) {
                const promptId = promptIdMap[gameState.tempVoteSelection];
                socket.emit('cast_vote', { 
                    voted_for: gameState.tempVoteSelection,
                    prompt_id: promptId  // Include prompt_id for database tracking
                });
            confirmVoteBtn.disabled = true;
            confirmVoteBtn.textContent = 'Vote Submitted';
            gameState.votedFor = gameState.tempVoteSelection;
                
                // Mark the selected item as voted (visual feedback)
                const selectedItem = document.querySelector('.voting-item.selected');
                if (selectedItem) {
                    selectedItem.classList.remove('selected');
                    selectedItem.classList.add('voted');
                }
        }
    };
    }
});

socket.on('vote_cast', (data) => {
    if (data.success) {
        addSystemMessage('Vote cast successfully!');
    }
});

socket.on('self_vote_error', (data) => {
    // Show error message and flash the selected image
    const selectedItem = document.querySelector('.voting-item.voted');
    if (selectedItem) {
        selectedItem.classList.add('flash-red');
        setTimeout(() => {
            selectedItem.classList.remove('flash-red');
            selectedItem.classList.remove('voted');
        }, 2000);
    }
});

socket.on('round_results', (data) => {
    // Don't handle results events if user is admin
    if (gameState.isAdmin) {
        return;
    }
    
    showScreen('results');

    document.getElementById('results-round').textContent = data.round;

    const resultsList = document.getElementById('results-list');
    resultsList.innerHTML = '';

    data.results.forEach((result, index) => {
        const item = document.createElement('div');
        item.className = 'result-item';

        item.innerHTML = `
            ${result.image ? `<img src="${result.image}" class="result-image" alt="${result.player_name}'s image">` : ''}
            <div class="result-info">
                <h3>${result.player_name}</h3>
            </div>
            <div class="result-score">${result.votes}</div>
        `;

        resultsList.appendChild(item);
    });

    // Update player score
    const myResult = data.results.find(r => r.player_name === gameState.playerName);
    if (myResult) {
        document.getElementById('player-score').textContent = myResult.total_score;
    }

    // Reset for next round
    gameState.selectedImageIndex = null;
    gameState.votedFor = null;

    // Hide next round button - players don't see it (admin has separate controls in admin dashboard)
    const nextRoundBtn = document.getElementById('next-round-btn');
    if (nextRoundBtn) {
        nextRoundBtn.style.display = 'none';
        }
});

socket.on('game_over', (data) => {
    // Don't handle game over events if user is admin
    if (gameState.isAdmin) {
        return;
    }
    
    showScreen('gameover');

    const finalResults = document.getElementById('final-results');
    finalResults.innerHTML = '<h2>Final Standings</h2>';

    data.results.forEach((result, index) => {
        const item = document.createElement('div');
        item.className = 'final-result-item';

        if (index === 0) item.classList.add('podium-1');
        else if (index === 1) item.classList.add('podium-2');
        else if (index === 2) item.classList.add('podium-3');

        let rankEmoji = '';
        if (index === 0) rankEmoji = '🥇';
        else if (index === 1) rankEmoji = '🥈';
        else if (index === 2) rankEmoji = '🥉';
        else rankEmoji = `#${index + 1}`;

        item.innerHTML = `
            <div class="result-rank">${rankEmoji}</div>
            <div class="result-info">
                <h3>${result.player_name}</h3>
                <p>Round Scores: ${result.round_scores.join(', ')}</p>
            </div>
            <div class="result-score">${result.total_score}</div>
        `;

        finalResults.appendChild(item);
    });
});

socket.on('game_restarted', (data) => {
    // Admin stays in the game, just reset their view
    if (gameState.isAdmin) {
    showScreen('lobby');
    // Reset state
    gameState.currentRound = 0;
    gameState.selectedImageIndex = null;
    gameState.generatedImages = [];
    gameState.votedFor = null;
        
        // Show message if provided
        if (data && data.message) {
            alert(data.message);
        }
    }
});

socket.on('game_restarted_kick', (data) => {
    // Non-admin players have been kicked - they need to rejoin
    showScreen('lobby');
    
    // Clear all game state
    gameState.currentRound = 0;
    gameState.selectedImageIndex = null;
    gameState.generatedImages = [];
    gameState.votedFor = null;
    gameState.playerName = null;
    gameState.playerTeam = null;
    gameState.playerCharacter = null;
    gameState.isAdmin = false;
    gameState.hasConfirmedSelection = false;
    
    // Clear player name input so they need to re-enter
    const nameInput = document.getElementById('player-name');
    if (nameInput) {
        nameInput.value = '';
        nameInput.disabled = false;
    }
    
    // Clear player list
    const playerList = document.getElementById('player-list');
    if (playerList) {
        playerList.innerHTML = '';
    }
    
    // Show message
    const message = data && data.message ? data.message : 'The game has been restarted. Please rejoin to continue.';
    alert(message);
    
    // Reset avatar state
    stopCharacterTalking();
    gameState.currentCharacter = null;
    gameState.avatarPlantState = null;
    gameState.avatarAnimationState = null;
});

socket.on('error', (data) => {
    alert(data.message);
});

// Helper functions
function addChatMessage(type, content) {
    const chatMessages = document.getElementById('chat-messages');
    const message = document.createElement('div');
    message.className = `message ${type}-message`;
    message.textContent = content;
    chatMessages.appendChild(message);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addSystemMessage(content) {
    const chatMessages = document.getElementById('chat-messages');
    const message = document.createElement('div');
    message.className = 'system-message';
    message.textContent = content;
    chatMessages.appendChild(message);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addImageToGallery(imageData, prompt, index) {
    const gallery = document.getElementById('image-gallery');

    // Remove empty message
    const emptyMsg = gallery.querySelector('.empty-gallery');
    if (emptyMsg) emptyMsg.remove();

    const item = document.createElement('div');
    item.className = 'gallery-item';
    item.innerHTML = `
        <img src="${imageData}" alt="Generated image">
        <div class="prompt-label">${prompt}</div>
    `;

    gallery.appendChild(item);
}

let timerInterval;

function startRoundTimer(endTime) {
    if (timerInterval) clearInterval(timerInterval);

    const timerEl = document.getElementById('timer');
    const bufferTimerEl = document.getElementById('buffer-timer');
    if (timerEl) timerEl.classList.remove('warning'); // Reset warning state
    if (bufferTimerEl) bufferTimerEl.style.display = 'none';

    timerInterval = setInterval(() => {
        const now = Date.now() / 1000;
        const remaining = Math.max(0, endTime - now);

        if (timerEl) {
        const minutes = Math.floor(remaining / 60);
        const seconds = Math.floor(remaining % 60);
        timerEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;

        // Only show warning if under 30 seconds
        if (remaining > 0 && remaining <= 30) {
            timerEl.classList.add('warning');
        } else {
            timerEl.classList.remove('warning');
            }
        }

        if (remaining <= 0) {
            clearInterval(timerInterval);
            if (timerEl) timerEl.textContent = '0:00';
            socket.emit('round_timer_check');
        }
    }, 1000);
}

// Handle timer updates from server
socket.on('timer_update', (data) => {
    const timerEl = document.getElementById('timer');
    
    if (timerEl && data.time_remaining !== undefined) {
        const minutes = Math.floor(data.time_remaining / 60);
        const seconds = Math.floor(data.time_remaining % 60);
        timerEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        
        if (data.time_remaining <= 30) {
            timerEl.classList.add('warning');
        } else {
            timerEl.classList.remove('warning');
        }
    }
});

// Handle transition screen
socket.on('show_transition_screen', (data) => {
    // Don't handle transition events if user is admin
    if (gameState.isAdmin) {
        return;
    }
    
    showScreen('transition');
    const messageEl = document.getElementById('transition-message');
    if (messageEl && data.message) {
        messageEl.textContent = data.message;
    }
    
    // Clear any existing transition timer
    if (gameState.transitionTimer) {
        clearTimeout(gameState.transitionTimer);
        clearInterval(gameState.transitionCountdown);
    }
    
    // Client-side fallback: Ensure progression after max wait
    const maxWait = data.max_wait || 10; // Default to 10 seconds max
    
    // Client-side safety net: Request status check after max wait if still on transition screen
    gameState.transitionTimer = setTimeout(() => {
        console.log("[CLIENT] Transition max duration reached - requesting status update");
        
        // Check current screen - if still on transition, something went wrong
        const transitionScreen = document.getElementById('transition-screen');
        if (transitionScreen && transitionScreen.classList.contains('active')) {
            console.log("[CLIENT] Still on transition screen after max wait - requesting status");
            // Request status update from server
            socket.emit('round_timer_check');
        }
        gameState.transitionTimer = null;
    }, (maxWait + 0.5) * 1000); // Add 0.5s buffer
});

socket.on('return_to_lobby', (data) => {
    // Return to lobby screen
    showScreen('lobby');
    // Reset game state
    gameState.selectedImageIndex = null;
    gameState.generatedImages = [];
    gameState.votedFor = null;
    gameState.tempVoteSelection = null;
    gameState.currentRound = 0;
    
    // Clear time calculation timers
    if (adminTimerInterval) {
        clearInterval(adminTimerInterval);
        adminTimerInterval = null;
    }
    gameState.roundEndTime = null;
    gameState.votingStartTime = null;
    gameState.votingDuration = null;
    
    // Reset avatar state
    stopCharacterTalking();
    gameState.currentCharacter = null;
    gameState.avatarPlantState = null;
    gameState.avatarAnimationState = null;
    const avatarImg = document.getElementById('avatar-svg');
    if (avatarImg) {
        avatarImg.style.display = 'none';
    }
    const messageBubble = document.getElementById('character-bubble');
    if (messageBubble) {
        messageBubble.style.display = 'none';
    }
    
    // Clear transition timers
    if (gameState.transitionTimer) {
        clearTimeout(gameState.transitionTimer);
        gameState.transitionTimer = null;
    }
    if (gameState.transitionCountdown) {
        clearInterval(gameState.transitionCountdown);
        gameState.transitionCountdown = null;
    }
});

// Duplicate function removed - using the one defined earlier

// Auto-refresh timer periodically - check for both game screen and transition screen
setInterval(() => {
    const transitionScreen = document.getElementById('transition-screen');
    const isOnTransition = transitionScreen && transitionScreen.classList.contains('active');
    const isOnGame = screens.game && screens.game.classList.contains('active');
    
    // Check timer for both game screen and transition screen
    // This ensures transition screen progresses automatically
    if (gameState.currentRound > 0 && (isOnGame || isOnTransition)) {
        socket.emit('round_timer_check');
    }
}, 1000); // Check every 1 second for better responsiveness during transition
