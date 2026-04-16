// Socket.IO connection
const socket = io();

/** Study groups (must match app.py PLAYER_GROUPS). */
const PLAYER_GROUPS = ['C_NA', 'C_HU', 'T_NA', 'T_HU'];

function playerCondition(p) {
    if (!p) return '';
    return p.condition != null && p.condition !== '' ? p.condition : (p.team || '');
}

/** Treatment arms: show heuristics under images on the selection screen (matches server T_NA / T_HU). */
function showTreatmentSelectionHeuristics() {
    const c = String(gameState.playerCondition || '').toUpperCase();
    return c === 'T_NA' || c === 'T_HU';
}

function buildHeuristicLinesHtml(lines) {
    if (!Array.isArray(lines) || !lines.length) return '';
    return lines.map((h) => {
        const lab = (h.label || '').replace(/</g, '&lt;');
        const val = (h.value || '').replace(/</g, '&lt;');
        return `<div class="heuristic-line"><span class="hl">${lab}</span>: <span class="hv">${val}</span></div>`;
    }).join('');
}

function findConversationImageContainer(conversationArea, promptIndex) {
    if (!conversationArea || promptIndex == null || promptIndex === undefined) return null;
    const item = conversationArea.querySelector(`.conversation-item[data-prompt-index="${promptIndex}"]`);
    return item ? item.querySelector('.image-container') : null;
}

/** If prompt_index is missing (old server), fall back to the newest row that still shows loading. */
function findConversationImageContainerFallback(conversationArea) {
    if (!conversationArea) return null;
    const containers = conversationArea.querySelectorAll('.image-container');
    for (let i = containers.length - 1; i >= 0; i--) {
        if (containers[i].querySelector('.image-loading')) return containers[i];
    }
    return containers.length ? containers[containers.length - 1] : null;
}

/** Map index in gameState.generatedImages to index among .selection-item (valid images only). */
function generatedIndexToGalleryItemIndex(genIdx) {
    let g = 0;
    for (let i = 0; i <= genIdx && i < gameState.generatedImages.length; i++) {
        if (!gameState.generatedImages[i].error_type) {
            if (i === genIdx) return g;
            g++;
        }
    }
    return -1;
}

// Game state
let gameState = {
    playerName: '',
    playerCondition: '',
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
    votingDuration: null,  // Duration in seconds
    inSelectionPhase: false,  // Track if we're in the selection phase (for late-arriving images)
    surveyCompleted: false,
    inOnboarding: false,
    onboardingPhase: 'prompting', // 'prompting' | 'practice_voting' while inOnboarding
    onboardingMaxPrompts: 3,
    onboardingPromptCount: 0,
    /** Live play only: show bullet slots under images when server sets image_context_bullets (never during onboarding). */
    imageContextBulletsEnabled: false,
    /** Server-authoritative allocation voting round index while on #voting-screen. */
    allocationRoundIndex: 1,
    /** True while game_state.status is allocation_voting (admin dashboard context). */
    inAllocationVoting: false,
    postSurveyCompleted: false,
    postSurveyActive: false,
    canStartPostSurvey: false,
    pendingGameOver: null,
};

let timerInterval;

function syncImageContextBulletsVisibility() {
    const enabled = Boolean(gameState.imageContextBulletsEnabled) && !gameState.inOnboarding;
    document.body.classList.toggle('image-context-bullets-enabled', enabled);
    document.querySelectorAll('.gameplay-image-context-bullets').forEach((el) => {
        el.setAttribute('aria-hidden', enabled ? 'false' : 'true');
    });
}

function applyOnboardingGenerateState() {
    if (!gameState.inOnboarding || gameState.isAdmin) return;
    if (gameState.onboardingPhase === 'practice_voting') return;
    const max = gameState.onboardingMaxPrompts || 3;
    const btn = document.getElementById('generate-btn');
    const input = document.getElementById('prompt-input');
    const hint = document.getElementById('onboarding-limit-hint');
    const atLimit = gameState.onboardingPromptCount >= max;
    if (atLimit) {
        if (input) {
            input.disabled = true;
            input.style.display = 'none';
        }
        if (btn) {
            btn.disabled = true;
            btn.style.display = 'none';
        }
        if (hint) {
            hint.style.display = 'block';
            hint.textContent = 'Practice limit reached.';
        }
    } else {
        if (input) {
            input.disabled = false;
            input.style.display = '';
        }
        if (btn) {
            btn.disabled = false;
            btn.style.display = '';
        }
        if (hint) hint.style.display = 'none';
    }
}

function clearRoundTimerIfAny() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

function setGameRoundHeadingPractice() {
    const normal = document.getElementById('round-title-mode-normal');
    const practice = document.getElementById('round-title-mode-practice');
    if (normal) normal.style.display = 'none';
    if (practice) practice.style.display = '';
}

function setGameRoundHeadingNormal(roundNum) {
    const normal = document.getElementById('round-title-mode-normal');
    const practice = document.getElementById('round-title-mode-practice');
    const rn = document.getElementById('round-number');
    if (practice) practice.style.display = 'none';
    if (normal) normal.style.display = '';
    if (rn != null && roundNum != null) {
        rn.textContent = String(roundNum);
    }
}

function setOnboardingInstructionsPanelVisible(visible) {
    const panel = document.getElementById('onboarding-instructions-panel');
    const bubble = document.getElementById('character-bubble');
    const avatarLarge = document.getElementById('character-avatar-large');
    if (panel) {
        panel.style.display = visible ? 'block' : 'none';
        panel.setAttribute('aria-hidden', visible ? 'false' : 'true');
    }
    if (visible) {
        if (bubble) bubble.style.display = 'none';
        if (avatarLarge) avatarLarge.style.display = 'none';
    } else {
        if (avatarLarge) avatarLarge.style.display = '';
    }
}

// DOM elements
const screens = {
    lobby: document.getElementById('lobby-screen'),
    game: document.getElementById('game-screen'),
    onboardingPracticeVoting: document.getElementById('onboarding-practice-voting-screen'),
    transition: document.getElementById('transition-screen'),
    selection: document.getElementById('selection-screen'),
    voting: document.getElementById('voting-screen'),
    results: document.getElementById('results-screen'),
    gameover: document.getElementById('gameover-screen'),
    postGameSurvey: document.getElementById('post-game-survey-screen'),
};

/** Gamemaster Round Controls: full buttons for live play; onboarding prompting shows End Round only. */
function setAdminRoundControlsForContext() {
    const grp = document.getElementById('admin-game-controls');
    const endBtn = document.getElementById('admin-end-round-btn');
    const skipBtn = document.getElementById('admin-skip-voting-btn');
    const nextBtn = document.getElementById('admin-next-round-btn');
    if (!endBtn || !skipBtn || !nextBtn) return;

    if (gameState.isAdmin && gameState.inOnboarding) {
        if (grp) grp.style.display = 'block';
        if (gameState.onboardingPhase === 'prompting') {
            endBtn.style.display = '';
            endBtn.textContent = 'End Round Early';
            skipBtn.style.display = 'none';
            nextBtn.style.display = 'none';
        } else {
            endBtn.style.display = 'none';
            skipBtn.style.display = 'none';
            nextBtn.style.display = 'none';
        }
    } else if (gameState.isAdmin) {
        endBtn.style.display = '';
        endBtn.textContent = 'End Round Early';
        skipBtn.style.display = '';
        nextBtn.style.display = '';
    }
}

let obPracticeInputListenersBound = false;

function getObPracticeValues() {
    const out = [];
    for (let i = 1; i <= 3; i++) {
        const el = document.getElementById(`ob-practice-pts-${i}`);
        const raw = el && el.value !== '' ? el.value : '0';
        const n = parseInt(raw, 10);
        out.push(Number.isFinite(n) ? Math.min(10, Math.max(0, n)) : 0);
    }
    return out;
}

function syncObPracticeRemaining(editedIndex) {
    let vals = getObPracticeValues();
    let sum = vals[0] + vals[1] + vals[2];
    if (sum > 10 && editedIndex >= 0 && editedIndex <= 2) {
        const overflow = sum - 10;
        vals[editedIndex] = Math.max(0, vals[editedIndex] - overflow);
        const el = document.getElementById(`ob-practice-pts-${editedIndex + 1}`);
        if (el) el.value = String(vals[editedIndex]);
        sum = vals[0] + vals[1] + vals[2];
    }
    updateAllocationPointsHeader(vals[0], vals[1], vals[2], 'ob-practice-header-points');
    const btn = document.getElementById('ob-practice-submit-btn');
    if (btn && btn.dataset.submitted !== '1') {
        btn.disabled = sum !== 10;
    }
}

function resetObPracticeVotingForm() {
    for (let i = 1; i <= 3; i++) {
        const el = document.getElementById(`ob-practice-pts-${i}`);
        if (el) {
            el.value = '0';
            el.disabled = false;
        }
    }
    const err = document.getElementById('ob-practice-vote-error');
    if (err) {
        err.style.display = 'none';
        err.textContent = '';
    }
    const done = document.getElementById('ob-practice-vote-done');
    if (done) done.style.display = 'none';
    const submit = document.getElementById('ob-practice-submit-btn');
    if (submit) {
        submit.disabled = true;
        submit.style.display = '';
        delete submit.dataset.submitted;
    }
    syncObPracticeRemaining(0);
}

function applyObPracticeSubmittedState(points) {
    const submit = document.getElementById('ob-practice-submit-btn');
    if (submit) {
        submit.style.display = 'none';
        submit.dataset.submitted = '1';
    }
    for (let i = 0; i < 3; i++) {
        const el = document.getElementById(`ob-practice-pts-${i + 1}`);
        if (el) {
            el.value = String(points[i] != null ? points[i] : 0);
            el.disabled = true;
        }
    }
    syncObPracticeRemaining(0);
    const done = document.getElementById('ob-practice-vote-done');
    if (done) done.style.display = 'block';
}

function initOnboardingPracticeVotingListeners() {
    if (obPracticeInputListenersBound) return;
    obPracticeInputListenersBound = true;
    for (let i = 1; i <= 3; i++) {
        const idx = i - 1;
        document.getElementById(`ob-practice-pts-${i}`)?.addEventListener('input', () => {
            syncObPracticeRemaining(idx);
        });
    }
    document.getElementById('ob-practice-submit-btn')?.addEventListener('click', () => {
        const vals = getObPracticeValues();
        const err = document.getElementById('ob-practice-vote-error');
        if (vals[0] + vals[1] + vals[2] !== 10) {
            if (err) {
                err.textContent = 'Assign exactly 10 points across the three images.';
                err.style.display = 'block';
            }
            return;
        }
        if (err) err.style.display = 'none';
        socket.emit('submit_onboarding_practice_points', { points: vals });
    });
}

function showOnboardingPracticeVotingFromPayload(data) {
    initOnboardingPracticeVotingListeners();
    gameState.imageContextBulletsEnabled = false;
    gameState.inOnboarding = true;
    gameState.onboardingPhase = 'practice_voting';

    const opts = data.option_images || [];
    opts.forEach((row) => {
        const slot = row.slot;
        const el = document.getElementById(`ob-practice-opt-img-${slot}`);
        if (el && row.url) el.src = row.url;
    });
    const img = document.getElementById('ob-practice-target-img');
    if (img && data.target && data.target.url) {
        img.src = data.target.url;
        img.alt = 'Practice target';
    }
    if (data.already_submitted && Array.isArray(data.existing_points) && data.existing_points.length === 3) {
        resetObPracticeVotingForm();
        applyObPracticeSubmittedState(data.existing_points);
    } else {
        resetObPracticeVotingForm();
    }

    syncImageContextBulletsVisibility();
    syncAllocationVotingHeaderAlias();
    showScreen('onboardingPracticeVoting');
}

// Avatar images are embedded inline — no preloading or HTTP requests needed.

const PRE_SURVEY_SKILLS_MAX = 2000;

function readPreSurveyForm() {
    const prof = document.querySelector('input[name="pre-survey-proficiency"]:checked');
    const freq = document.querySelector('input[name="pre-survey-frequency"]:checked');
    const skillsEl = document.getElementById('pre-survey-skills');
    const skills = (skillsEl && skillsEl.value) ? skillsEl.value.trim() : '';
    return {
        proficiency: prof ? prof.value : null,
        frequency: freq ? freq.value : null,
        skills_text: skills
    };
}

function updatePreSurveySubmitEnabled() {
    const btn = document.getElementById('pre-survey-submit-btn');
    if (!btn || gameState.surveyCompleted) return;
    const { proficiency, frequency, skills_text } = readPreSurveyForm();
    const ok = proficiency && frequency && skills_text.length > 0 && skills_text.length <= PRE_SURVEY_SKILLS_MAX;
    btn.disabled = !ok;
}

function showLobbySurveyForPlayer() {
    const card = document.getElementById('lobby-survey-card');
    const formWrap = document.getElementById('lobby-survey-form-wrap');
    const done = document.getElementById('lobby-survey-done');
    const err = document.getElementById('lobby-survey-error');
    if (!card) return;

    if (gameState.isAdmin) {
        card.style.display = 'none';
        return;
    }

    const onLobby = screens.lobby && screens.lobby.classList.contains('active');
    if (!onLobby) {
        card.style.display = 'none';
        return;
    }

    card.style.display = 'block';
    if (err) {
        err.style.display = 'none';
        err.textContent = '';
    }

    if (gameState.surveyCompleted) {
        if (formWrap) formWrap.style.display = 'none';
        if (done) done.style.display = 'block';
    } else {
        if (formWrap) formWrap.style.display = 'block';
        if (done) done.style.display = 'none';
        updatePreSurveySubmitEnabled();
    }
}

function initLobbyPreSurvey() {
    const submitBtn = document.getElementById('pre-survey-submit-btn');
    const skillsEl = document.getElementById('pre-survey-skills');
    if (!submitBtn) return;

    document.querySelectorAll('input[name="pre-survey-proficiency"], input[name="pre-survey-frequency"]').forEach((el) => {
        el.addEventListener('change', updatePreSurveySubmitEnabled);
    });
    if (skillsEl) {
        skillsEl.addEventListener('input', updatePreSurveySubmitEnabled);
    }

    submitBtn.addEventListener('click', () => {
        const err = document.getElementById('lobby-survey-error');
        const { proficiency, frequency, skills_text } = readPreSurveyForm();
        if (!proficiency || !frequency) {
            if (err) {
                err.textContent = 'Please answer both multiple-choice questions.';
                err.style.display = 'block';
            }
            return;
        }
        if (!skills_text.length) {
            if (err) {
                err.textContent = 'Please enter an answer for the open-ended question.';
                err.style.display = 'block';
            }
            return;
        }
        if (skills_text.length > PRE_SURVEY_SKILLS_MAX) {
            if (err) {
                err.textContent = `Answer is too long (max ${PRE_SURVEY_SKILLS_MAX} characters).`;
                err.style.display = 'block';
            }
            return;
        }
        if (err) err.style.display = 'none';
        socket.emit('submit_pre_survey', {
            proficiency,
            frequency,
            skills_text
        });
    });

    updatePreSurveySubmitEnabled();
}

document.addEventListener('DOMContentLoaded', () => {
    initLobbyPreSurvey();
    initPostGameSurveyListeners();
});
// Utility function to show screen
function showScreen(screenName) {
    Object.values(screens).forEach((screen) => {
        if (screen) screen.classList.remove('active');
    });
    const next = screens[screenName];
    if (next) next.classList.add('active');
    if (screenName === 'lobby') {
        showLobbySurveyForPlayer();
    }
    if (gameState.isAdmin) {
        syncStartPostSurveyButton();
    }
}

function syncStartPostSurveyButton() {
    const btn = document.getElementById('start-post-survey-btn');
    if (!btn) return;
    if (!gameState.isAdmin) {
        btn.disabled = true;
        return;
    }
    const active = gameState.postSurveyActive;
    // Always clickable except while a survey is already open (server will error if other preconditions fail)
    btn.disabled = active;
    btn.title = active
        ? 'Post-game survey is already open for players.'
        : 'Open the post-game survey for everyone in this session. Requires at least one player and a started game with database records; you will see a message if it cannot run yet.';
}

const POST_SURVEY_M1_STEMS = ['longer', 'more', 'vocab'];
const POST_SURVEY_M1_ROWS = ['creative', 'precise', 'skilled', 'efficient'];
const POST_SURVEY_M2_KEYS = [
    'visual_similarity',
    'considers_prompt_count',
    'considers_word_count',
    'considers_vocab_variability',
    'value_not_easily_created',
    'few_prompts_better_understands',
    'dozens_poor_engineering',
];

function collectPostSurveyMatrix1() {
    const matrix1 = {};
    for (const stem of POST_SURVEY_M1_STEMS) {
        matrix1[stem] = {};
        for (const row of POST_SURVEY_M1_ROWS) {
            const selected = document.querySelector(`input[name="post-m1-${stem}-${row}"]:checked`);
            if (!selected) return null;
            matrix1[stem][row] = selected.value;
        }
    }
    return matrix1;
}

function collectPostSurveyMatrix2() {
    const matrix2 = {};
    for (const key of POST_SURVEY_M2_KEYS) {
        const selected = document.querySelector(`input[name="post-m2-${key}"]:checked`);
        if (!selected) return null;
        matrix2[key] = selected.value;
    }
    return matrix2;
}

function isPostSurveyComplete() {
    const q1 = (document.getElementById('post-free-q1')?.value || '').trim();
    const q2 = (document.getElementById('post-free-q2')?.value || '').trim();
    const q3 = (document.getElementById('post-free-q3')?.value || '').trim();
    const q4 = (document.getElementById('post-free-q4')?.value || '').trim();
    const l1 = document.querySelector('input[name="post-likert-best-work"]:checked');
    const l2 = document.querySelector('input[name="post-likert-effort"]:checked');
    const impressive = document.querySelector('input[name="post-impressive"]:checked');
    return Boolean(q1 && q2 && q3 && q4 && l1 && l2 && impressive && collectPostSurveyMatrix1() && collectPostSurveyMatrix2());
}

function renderGameOverContent(data) {
    const finalResults = document.getElementById('final-results');
    if (!finalResults || !data) return;
    const selfName = (gameState.playerName || '').trim();
    const isSelfResult = (resultName) => {
        if (!selfName || !resultName) return false;
        return String(resultName).trim().toLowerCase() === selfName.toLowerCase();
    };
    const renderResultName = (resultName) => {
        const safeName = resultName || '';
        if (!isSelfResult(safeName)) return safeName;
        return `${safeName} <span class="you-badge" aria-label="This is you">You</span>`;
    };

    if (data.experiment) {
        finalResults.innerHTML = '<h2>Game results</h2>';
        (data.results || []).forEach((result) => {
            const item = document.createElement('div');
            item.className = 'final-result-item experiment-rank';
            if (isSelfResult(result.player_name)) item.classList.add('self-result');
            const r = result.rank || 1;
            let badge = String(r);
            if (r === 1) badge = '🥇';
            else if (r === 2) badge = '🥈';
            else if (r === 3) badge = '🥉';
            item.innerHTML = `
                <div class="result-rank">${badge}</div>
                <div class="result-info"><h3>${renderResultName(result.player_name)}</h3></div>
            `;
            finalResults.appendChild(item);
        });
        return;
    }

    finalResults.innerHTML = '<h2>Final Standings</h2>';
    (data.results || []).forEach((result, index) => {
        const item = document.createElement('div');
        item.className = 'final-result-item';
        if (isSelfResult(result.player_name)) item.classList.add('self-result');

        if (index === 0) item.classList.add('podium-1');
        else if (index === 1) item.classList.add('podium-2');
        else if (index === 2) item.classList.add('podium-3');

        let rankEmoji = '';
        if (index === 0) rankEmoji = '🥇';
        else if (index === 1) rankEmoji = '🥈';
        else if (index === 2) rankEmoji = '🥉';
        else rankEmoji = `#${index + 1}`;

        const roundScores = Array.isArray(result.round_scores) ? result.round_scores.join(', ') : '';
        item.innerHTML = `
            <div class="result-rank">${rankEmoji}</div>
            <div class="result-info">
                <h3>${renderResultName(result.player_name)}</h3>
                <p>Round Scores: ${roundScores}</p>
            </div>
            <div class="result-score">${result.total_score ?? ''}</div>
        `;
        finalResults.appendChild(item);
    });
}

function resetPostGameSurveyForm() {
    for (let i = 1; i <= 4; i++) {
        const el = document.getElementById(`post-free-q${i}`);
        if (el) {
            el.value = '';
            el.disabled = false;
        }
    }
    document.querySelectorAll('#post-game-survey-form-wrap input[type="radio"]').forEach((r) => {
        r.checked = false;
        r.disabled = false;
    });
    const err = document.getElementById('post-game-survey-error');
    if (err) {
        err.style.display = 'none';
        err.textContent = '';
    }
    const wrap = document.getElementById('post-game-survey-form-wrap');
    const done = document.getElementById('post-game-survey-done');
    if (wrap) wrap.style.display = 'block';
    if (done) done.style.display = 'none';
    const submit = document.getElementById('post-game-survey-submit-btn');
    if (submit) {
        submit.disabled = true;
        delete submit.dataset.submitted;
    }
    updatePostGameSurveySubmitEnabled();
}

function updatePostGameSurveySubmitEnabled() {
    const submit = document.getElementById('post-game-survey-submit-btn');
    if (!submit || submit.dataset.submitted === '1') return;
    submit.disabled = !isPostSurveyComplete();
}

function initPostGameSurveyListeners() {
    for (let i = 1; i <= 4; i++) {
        document.getElementById(`post-free-q${i}`)?.addEventListener('input', updatePostGameSurveySubmitEnabled);
    }
    document.querySelectorAll('#post-game-survey-form-wrap input[type="radio"]').forEach((el) => {
        el.addEventListener('change', updatePostGameSurveySubmitEnabled);
    });
    document.getElementById('post-game-survey-submit-btn')?.addEventListener('click', () => {
        const err = document.getElementById('post-game-survey-error');
        if (err) {
            err.style.display = 'none';
            err.textContent = '';
        }
        const free_q1 = (document.getElementById('post-free-q1')?.value || '').trim();
        const free_q2 = (document.getElementById('post-free-q2')?.value || '').trim();
        const free_q3 = (document.getElementById('post-free-q3')?.value || '').trim();
        const free_q4 = (document.getElementById('post-free-q4')?.value || '').trim();
        const likert_best_work = document.querySelector('input[name="post-likert-best-work"]:checked')?.value;
        const likert_effort = document.querySelector('input[name="post-likert-effort"]:checked')?.value;
        const matrix1 = collectPostSurveyMatrix1();
        const matrix2 = collectPostSurveyMatrix2();
        const impressive_if = document.querySelector('input[name="post-impressive"]:checked')?.value;
        if (
            !free_q1 || !free_q2 || !free_q3 || !free_q4 ||
            !likert_best_work || !likert_effort || !matrix1 || !matrix2 || !impressive_if
        ) {
            if (err) {
                err.textContent = 'Please answer every question before submitting.';
                err.style.display = 'block';
            }
            return;
        }
        socket.emit('submit_post_game_survey', {
            free_q1,
            free_q2,
            free_q3,
            free_q4,
            likert_best_work,
            likert_effort,
            matrix1,
            matrix2,
            impressive_if,
        });
    });
    document.getElementById('post-game-survey-back-btn')?.addEventListener('click', () => {
        socket.emit('back_to_home');
    });
    document.getElementById('start-post-survey-btn')?.addEventListener('click', () => {
        if (!gameState.isAdmin) return;
        if (gameState.postSurveyActive) return;
        if (!confirm('Open the post-game survey for all connected players now?')) return;
        socket.emit('admin_start_post_survey');
    });
}

function applyPostSurveyFlagsFromServer(data) {
    if (data.post_survey_active !== undefined) {
        gameState.postSurveyActive = !!data.post_survey_active;
    }
    if (data.can_start_post_survey !== undefined) {
        gameState.canStartPostSurvey = !!data.can_start_post_survey;
    }
}

// Lobby handlers
function joinGame() {
    const joinBtn = document.getElementById('join-btn');
    if (joinBtn) joinBtn.disabled = true;
    socket.emit('join_game', {});
}

document.getElementById('join-btn').addEventListener('click', joinGame);

document.getElementById('assign-teams-btn').addEventListener('click', () => {
    socket.emit('assign_teams');
});

document.getElementById('start-onboarding-btn')?.addEventListener('click', () => {
    socket.emit('start_onboarding');
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
            prompt_index: selectedImage.prompt_index,
            image_index: gameState.selectedImageIndex,
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
                    const gi = generatedIndexToGalleryItemIndex(lastValidIndex);
                    items.forEach((item) => item.classList.remove('selected'));
                    if (gi >= 0 && items[gi]) {
                        items[gi].classList.add('selected');
                    } else if (items.length) {
                        items[items.length - 1].classList.add('selected');
                    }
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

// Admin login via lobby footer link
document.getElementById('admin-login-link')?.addEventListener('click', () => {
    const code = window.prompt('Enter admin password:');
    if (!code) {
        return;
    }
    socket.emit('admin_login', { code });
});

// Socket event handlers
socket.on('connect', () => {
    console.log('Connected to server');
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
});

socket.on('survey_submitted', () => {
    gameState.surveyCompleted = true;
    showLobbySurveyForPlayer();
});

socket.on('game_joined', (data) => {
    console.log('game_joined event received:', data);
    
    try {
        const joinBtn = document.getElementById('join-btn');
        if (joinBtn) joinBtn.disabled = false;

        gameState.playerName = data.player.name;
        gameState.playerCondition = data.player.condition || data.player.team;
        gameState.playerCharacter = data.player.character;
        gameState.isAdmin = data.player.is_admin;
        gameState.surveyCompleted = data.player.survey_completed === true;
        if (data.player.post_survey_completed !== undefined) {
            gameState.postSurveyCompleted = !!data.player.post_survey_completed;
        }
        if (data.player.post_survey_active !== undefined) {
            gameState.postSurveyActive = !!data.player.post_survey_active;
        }
        gameState.pendingGameOver = null;
        if (data.player.post_survey_game_over !== undefined) {
            gameState.pendingGameOver = data.player.post_survey_game_over;
        }
        gameState.canStartPostSurvey = false;

        const playerDisplayName = document.getElementById('player-display-name');
        if (playerDisplayName) {
            playerDisplayName.textContent = data.player.name;
        }
        
        // Team display removed from header - no longer showing team subtext
        
        const playerScore = document.getElementById('player-score');
        if (playerScore) {
            playerScore.textContent = data.player.score;
        }

        // Show current alias in lobby
        const aliasEl = document.getElementById('current-alias');
        if (aliasEl && !gameState.isAdmin) {
            aliasEl.textContent = `You are playing as: ${data.player.name}`;
            aliasEl.style.display = 'block';
        }

        // Update lobby player list
        if (data.lobby_players) {
            updatePlayerList(data.lobby_players);
        }

        showLobbySurveyForPlayer();

        if (!gameState.isAdmin && gameState.pendingGameOver && gameState.postSurveyCompleted) {
            renderGameOverContent(gameState.pendingGameOver);
            showScreen('gameover');
        } else if (!gameState.isAdmin && gameState.postSurveyActive && !gameState.postSurveyCompleted) {
            resetPostGameSurveyForm();
            showScreen('postGameSurvey');
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
    applyPostSurveyFlagsFromServer(data);
    syncGameStateFromAdminDashboardPayload(data);
    if (data.game_status == null) {
        gameState.currentRound = 0;
        gameState.inOnboarding = false;
        gameState.onboardingPhase = 'prompting';
        gameState.inAllocationVoting = false;
    }

    // Lobby holds admin chrome (e.g. Restart Game). Show it even if we were mid-game (recovery).
    showScreen('lobby');

    // Show admin screen in lobby
    const adminScreen = document.getElementById('admin-screen');
    const adminControls = document.getElementById('admin-controls');
    if (adminScreen) {
        adminScreen.style.display = 'block';
    }
    if (adminControls) {
        adminControls.style.display = 'flex';
    }
    syncStartPostSurveyButton();

    // Update admin player list
    updateAdminPlayerList(data.players);
    showLobbySurveyForPlayer();
});

// Admin replaced (another admin took over) — old Gamemaster is disconnected from the game
socket.on('admin_replaced', (data) => {
    console.log('admin_replaced event received');
    const message = (data && data.message) ? data.message : 'You were replaced as Gamemaster. Please rejoin the game.';
    gameState.isAdmin = false;
    showScreen('lobby');
    if (document.getElementById('admin-screen')) {
        document.getElementById('admin-screen').style.display = 'none';
    }
    if (document.getElementById('admin-controls')) {
        document.getElementById('admin-controls').style.display = 'none';
    }
    socket.disconnect();
    alert(message);
});

socket.on('admin_game_started', (data) => {
    console.log('admin_game_started event received:', data);

    gameState.inOnboarding = false;
    gameState.inAllocationVoting = false;
    gameState.currentRound = data.round != null ? data.round : 1;

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
    setAdminRoundControlsForContext();
    
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

socket.on('admin_onboarding_started', (data) => {
    gameState.inOnboarding = true;
    gameState.inAllocationVoting = false;
    gameState.onboardingPhase = data.onboarding_phase === 'practice_voting' ? 'practice_voting' : 'prompting';
    gameState.currentRound = 0;
    gameState.roundEndTime = null;
    if (adminTimerInterval) {
        clearInterval(adminTimerInterval);
        adminTimerInterval = null;
    }

    const adminScreen = document.getElementById('admin-screen');
    if (adminScreen) adminScreen.style.display = 'block';

    const adminGameControls = document.getElementById('admin-game-controls');
    if (adminGameControls) adminGameControls.style.display = 'block';
    setAdminRoundControlsForContext();

    const timeEl = document.getElementById('admin-time-remaining');
    if (timeEl) timeEl.textContent = '5:00';

    document.getElementById('admin-round').textContent = '—';
    document.getElementById('admin-status').textContent =
        gameState.onboardingPhase === 'practice_voting'
            ? 'Onboarding (practice voting)'
            : 'Onboarding (practice)';
    document.getElementById('admin-target').textContent = 'Practice target';

    if (data.players) {
        updateAdminPlayerList(data.players);
    }
});

socket.on('admin_onboarding_practice_voting', () => {
    if (!gameState.isAdmin) return;
    gameState.inOnboarding = true;
    gameState.inAllocationVoting = false;
    gameState.onboardingPhase = 'practice_voting';
    setAdminRoundControlsForContext();
    const st = document.getElementById('admin-status');
    if (st) st.textContent = 'Onboarding (practice voting)';
});

socket.on('admin_allocation_started', (data) => {
    if (!gameState.isAdmin) return;
    gameState.inAllocationVoting = true;
    const st = document.getElementById('admin-status');
    if (st) st.textContent = 'Allocation voting';
    const ar = document.getElementById('admin-round');
    if (ar) ar.textContent = data && data.total ? String(data.total) : '10';
    const timeEl = document.getElementById('admin-time-remaining');
    if (timeEl) timeEl.textContent = '—';
    if (adminTimerInterval) {
        clearInterval(adminTimerInterval);
        adminTimerInterval = null;
    }
});

socket.on('admin_voting_started', (data) => {
    console.log('admin_voting_started event received:', data);
    
    // Ensure admin screen is visible
    const adminScreen = document.getElementById('admin-screen');
    if (adminScreen) {
        adminScreen.style.display = 'block';
    }
    gameState.inOnboarding = false;
    gameState.inAllocationVoting = false;
    gameState.onboardingPhase = 'prompting';
    setAdminRoundControlsForContext();
    
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
        console.log('Condition assignments in update:', data.players.map(p => ({name: p.name, condition: playerCondition(p)})));
    }
    applyPostSurveyFlagsFromServer(data);
    if (gameState.isAdmin) {
        syncGameStateFromAdminDashboardPayload(data);
        updateAdminPlayerList(data.players);
        syncStartPostSurveyButton();
    } else {
        console.warn('player_status_update received but user is not admin');
    }
});

socket.on('post_survey_started', (data) => {
    if (gameState.isAdmin) return;
    gameState.postSurveyActive = true;
    if (data && data.game_over) {
        gameState.pendingGameOver = data.game_over;
    }
    if (gameState.postSurveyCompleted) return;
    const hintGo = document.getElementById('gameover-post-survey-hint');
    if (hintGo) hintGo.style.display = 'none';
    resetPostGameSurveyForm();
    showScreen('postGameSurvey');
});

socket.on('post_game_survey_saved', (data) => {
    if (gameState.isAdmin) return;
    gameState.postSurveyCompleted = true;
    const submit = document.getElementById('post-game-survey-submit-btn');
    if (submit) {
        submit.dataset.submitted = '1';
        submit.disabled = true;
    }
    if (data && data.game_over) {
        gameState.pendingGameOver = data.game_over;
        renderGameOverContent(data.game_over);
        showScreen('gameover');
        return;
    }
    const wrap = document.getElementById('post-game-survey-form-wrap');
    const done = document.getElementById('post-game-survey-done');
    if (wrap) wrap.style.display = 'none';
    if (done) done.style.display = 'block';
});

// Note: admin_status handler removed - we no longer poll for status updates
// All updates now come via events (player_prompt_updated, player_selected_image, player_voted, etc.)

socket.on('admin_status_update', (data) => {
    if (gameState.isAdmin) {
        document.getElementById('admin-status').textContent = data.status;
        if (data.round) {
            document.getElementById('admin-round').textContent = data.round;
            gameState.currentRound = data.round;
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

/** Apply server game phase fields included on admin_joined / player_status_update payloads. */
function syncGameStateFromAdminDashboardPayload(data) {
    if (!data || typeof data !== 'object') return;
    if (data.game_status != null) {
        gameState.inAllocationVoting = data.game_status === 'allocation_voting';
    }
    if (data.current_round !== undefined && data.current_round !== null) {
        gameState.currentRound = data.current_round;
    }
    if (data.game_status === 'onboarding') {
        gameState.inOnboarding = true;
        if (data.onboarding_phase === 'practice_voting' || data.onboarding_phase === 'prompting') {
            gameState.onboardingPhase = data.onboarding_phase;
        }
    } else if (data.game_status != null && data.game_status !== 'onboarding') {
        gameState.inOnboarding = false;
        gameState.onboardingPhase = 'prompting';
    }
}

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

    if (gameState.isAdmin && gameState.inOnboarding) {
        const nonAdmin = players.filter((p) => !p.is_admin);
        if (nonAdmin.length === 0) {
            gameState.inOnboarding = false;
            gameState.onboardingPhase = 'prompting';
            const timeEl = document.getElementById('admin-time-remaining');
            if (timeEl) timeEl.textContent = '-';
            const st = document.getElementById('admin-status');
            if (st) st.textContent = '-';
            const ar = document.getElementById('admin-round');
            if (ar) ar.textContent = '-';
            const at = document.getElementById('admin-target');
            if (at) at.textContent = '-';
        }
    }
    
    adminPlayerList.innerHTML = '<h3>Players</h3>';
    
    const isInLobby = gameState.currentRound === 0 && !gameState.inOnboarding && !gameState.inAllocationVoting;
    // Team dropdown + remove player: lobby, or onboarding practice (not live rounds)
    const showTeamAndRosterControls = (gameState.currentRound === 0 || gameState.inOnboarding) && !gameState.inAllocationVoting;

    const connectedCount = players.filter((p) => !p.is_admin && p.is_connected).length;
    const disconnectedCount = players.filter((p) => !p.is_admin && !p.is_connected).length;

    const connectionCountsEl = document.createElement('div');
    connectionCountsEl.className = 'admin-connection-counts';
    connectionCountsEl.style.cssText = 'margin-bottom: 10px; display: flex; gap: 12px; flex-wrap: wrap; font-size: 0.95rem;';
    connectionCountsEl.innerHTML = `
        <div><strong>Connected:</strong> ${connectedCount}</div>
        <div><strong>Disconnected:</strong> ${disconnectedCount}</div>
    `;
    adminPlayerList.appendChild(connectionCountsEl);

    // Pre-survey stats + clear lobby (lobby only)
    if (isInLobby) {
        const nonAdminLobby = players.filter((p) => !p.is_admin);
        const preSurveyCompletedCount = nonAdminLobby.filter((p) => p.survey_completed === true).length;
        const preSurveyPendingCount = nonAdminLobby.length - preSurveyCompletedCount;

        const surveyCountsEl = document.createElement('div');
        surveyCountsEl.style.cssText = 'margin-bottom: 10px; display: flex; gap: 12px; flex-wrap: wrap; font-size: 0.95rem;';
        surveyCountsEl.innerHTML = `
            <div><strong>Pre-survey:</strong> ${preSurveyPendingCount}</div>
            <div><strong>Pre-survey completed:</strong> ${preSurveyCompletedCount}</div>
        `;
        adminPlayerList.appendChild(surveyCountsEl);

        if (gameState.postSurveyActive || nonAdminLobby.some((p) => p.post_survey_completed === true)) {
            const postDone = nonAdminLobby.filter((p) => p.post_survey_completed === true).length;
            const postPending = nonAdminLobby.length - postDone;
            const postCountsEl = document.createElement('div');
            postCountsEl.style.cssText = 'margin-bottom: 10px; display: flex; gap: 12px; flex-wrap: wrap; font-size: 0.95rem;';
            postCountsEl.innerHTML = `
                <div><strong>Post-survey pending:</strong> ${postPending}</div>
                <div><strong>Post-survey completed:</strong> ${postDone}</div>
            `;
            adminPlayerList.appendChild(postCountsEl);
        }

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
        
        // Team dropdown (lobby or onboarding practice; hidden during scored rounds)
        if (showTeamAndRosterControls && !player.is_admin) {
            const teamSelect = document.createElement('select');
            teamSelect.className = 'team-select';
            teamSelect.style.cssText = 'padding: 2px 5px; border: 1px solid #ddd; border-radius: 3px; font-size: 12px;';
            
            // Add options first
            const optionNone = document.createElement('option');
            optionNone.value = '';
            optionNone.textContent = 'No group';
            teamSelect.appendChild(optionNone);
            
            PLAYER_GROUPS.forEach((g) => {
                const opt = document.createElement('option');
                opt.value = g;
                opt.textContent = g;
                teamSelect.appendChild(opt);
            });
            const pc = playerCondition(player);
            if (pc === 'Green' || pc === 'Orange') {
                const leg = document.createElement('option');
                leg.value = pc;
                leg.textContent = `${pc} (legacy)`;
                teamSelect.appendChild(leg);
            }
            
            // Set value AFTER options are added to ensure it works correctly
            const teamValue = (pc && (PLAYER_GROUPS.includes(pc) || pc === 'Green' || pc === 'Orange')) ? pc : '';
            console.log(`Setting dropdown for ${player.name}: condition="${pc}" -> value="${teamValue}"`);
            teamSelect.value = teamValue;
            
            // Handle condition change
            teamSelect.addEventListener('change', (e) => {
                const newTeam = e.target.value;
                if (newTeam && newTeam !== pc) {
                    if (confirm(`Change ${player.name}'s condition to ${newTeam}?`)) {
                        socket.emit('set_player_team', {
                            session_id: player.session_id,
                            condition: newTeam
                        });
                    } else {
                        teamSelect.value = pc || '';
                    }
                }
            });
            
            nameRow.appendChild(teamSelect);
        } else {
            // Show team as text (not in lobby or during game)
            const teamSpan = document.createElement('span');
            teamSpan.textContent = `(${playerCondition(player) || '?'})`;
            teamSpan.style.cssText = 'color: #666; font-size: 12px;';
            nameRow.appendChild(teamSpan);
        }
        
        leftDiv.appendChild(nameRow);
        
        // Status and info
        let phaseBadge = '';
        if (!player.is_admin) {
            if (player.allocation_voting_total != null && player.allocation_voting_total > 0) {
                const t = player.allocation_voting_total;
                const r = player.allocation_voting_round;
                if (r == null) {
                    phaseBadge = `<br><small style="color: #868e96; font-weight: 600;">Allocation voting: — / ${t}</small>`;
                } else if (r > t) {
                    phaseBadge = `<br><small style="color: #0b7285; font-weight: 600;">✓ Allocation complete (${t}/${t}) — waiting for others if needed</small>`;
                } else {
                    phaseBadge = `<br><small style="color: #0b7285; font-weight: 600;">Allocation voting: round ${r} / ${t}</small>`;
                }
            } else if (isInLobby) {
                const preSmall = `<small style="color: ${player.survey_completed === true ? '#2b8a3e' : '#868e96'}; font-weight: 600;">${player.survey_completed === true ? 'Pre-survey completed' : 'Pre-survey'}</small>`;
                const parts = [preSmall];
                if (gameState.postSurveyActive || player.post_survey_completed === true) {
                    const pd = player.post_survey_completed === true;
                    parts.push(
                        `<small style="color: ${pd ? '#2b8a3e' : '#868e96'}; font-weight: 600;">${pd ? 'Post-survey completed' : 'Post-survey pending'}</small>`
                    );
                }
                phaseBadge = '<br>' + parts.join('<br>');
            } else if (gameState.postSurveyActive) {
                const pd = player.post_survey_completed === true;
                phaseBadge = `<br><small style="color: ${pd ? '#2b8a3e' : '#868e96'}; font-weight: 600;">${pd ? 'Post-survey completed' : 'Post-survey pending'}</small>`;
            } else if (gameState.inOnboarding && gameState.onboardingPhase === 'practice_voting') {
                const pv = player.practice_vote_submitted === true;
                phaseBadge = `<br><small style="color: #1864ab; font-weight: 600;">${pv ? '✓ Practice points submitted' : 'Practice voting'}</small>`;
            } else if (gameState.inOnboarding) {
                phaseBadge = '<br><small style="color: #1864ab; font-weight: 600;">Practice (onboarding)</small>';
            } else if (!selectionStatus && !voteStatus) {
                phaseBadge = '<br><small style="color: #5f3dc4; font-weight: 600;">Prompting</small>';
            }
        }
        const infoDiv = document.createElement('div');
        infoDiv.innerHTML = `
            <small style="color: ${statusColor}">${statusText}</small>
            ${phaseBadge}
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
        
        // Add remove button (lobby or onboarding practice)
        if (showTeamAndRosterControls) {
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
    const msg =
        gameState.inOnboarding && gameState.onboardingPhase === 'prompting'
            ? 'End practice prompting and open practice point distribution (10 points across three images)?'
            : 'End the current round early and move to image selection?';
    if (confirm(msg)) {
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

function lobbyRowIsSelf(player) {
    if (gameState.isAdmin) {
        return !!player.is_admin;
    }
    return !player.is_admin && player.name === gameState.playerName;
}

function lobbyNonAdminStatus(player) {
    const cond = playerCondition(player);
    const hasCondition = cond != null && String(cond).trim() !== '';
    if (hasCondition) return { key: 'ready-green', label: 'Ready' };
    if (player.survey_completed) return { key: 'ready', label: 'Ready' };
    return { key: 'waiting', label: 'Waiting' };
}

function sortLobbyPlayersForDisplay(players) {
    const list = Array.isArray(players) ? [...players] : [];
    list.sort((a, b) => {
        const aSelf = lobbyRowIsSelf(a) ? 0 : 1;
        const bSelf = lobbyRowIsSelf(b) ? 0 : 1;
        if (aSelf !== bSelf) return aSelf - bSelf;
        const an = (a.name || '').toString();
        const bn = (b.name || '').toString();
        return an.localeCompare(bn, undefined, { sensitivity: 'base' });
    });
    return list;
}

function updatePlayerList(players) {
    const playerList = document.getElementById('player-list');
    if (!playerList) {
        console.error('player-list element not found');
        return;
    }
    playerList.innerHTML = '';

    let nonAdminCount = 0;
    const ordered = sortLobbyPlayersForDisplay(players);

    ordered.forEach((player) => {
        const item = document.createElement('div');
        item.className = 'player-item';
        item.setAttribute('role', 'listitem');

        const isSelf = lobbyRowIsSelf(player);
        if (isSelf) {
            item.classList.add('player-item--self');
        }

        let statusHtml = '';
        let ariaStatus = '';

        if (player.is_admin) {
            ariaStatus = 'Gamemaster';
            statusHtml = '<span class="player-lobby-status player-lobby-status--admin">Admin</span>';
        } else {
            nonAdminCount++;
            const st = lobbyNonAdminStatus(player);
            ariaStatus = st.label;
            statusHtml = `<span class="player-lobby-status player-lobby-status--${st.key}">${st.label}</span>`;
        }

        const youPill = isSelf
            ? '<span class="player-item-you-pill" aria-hidden="true">You</span>'
            : '';

        const nameParts = `<span class="player-item-name">${player.name}</span>${youPill}`;
        item.innerHTML = `<div class="player-item-main">${nameParts}</div>${statusHtml}`;

        const youBit = isSelf ? 'You, ' : '';
        item.setAttribute('aria-label', `${youBit}${player.name}, ${ariaStatus}`);

        playerList.appendChild(item);
    });

    const lobbyCountEl = document.getElementById('lobby-count');
    if (lobbyCountEl) {
        lobbyCountEl.textContent = nonAdminCount;
    }
}

socket.on('onboarding_started', (data) => {
    if (gameState.isAdmin) return;

    gameState.imageContextBulletsEnabled = false;
    gameState.inOnboarding = true;
    gameState.onboardingPhase = 'prompting';
    gameState.onboardingMaxPrompts = data.max_prompts || 3;
    gameState.onboardingPromptCount = 0;
    gameState.currentRound = 1;
    gameState.generatedImages = [];
    gameState.selectedImageIndex = null;

    stopCharacterTalking();
    if (gameState.messageAutoHideTimer) {
        clearTimeout(gameState.messageAutoHideTimer);
        gameState.messageAutoHideTimer = null;
    }

    setOnboardingInstructionsPanelVisible(true);

    setGameRoundHeadingPractice();

    const targetImage = document.getElementById('target-image-display');
    if (targetImage && data.target) {
        targetImage.src = data.target.url;
        targetImage.alt = 'Practice target';
    }

    const conversationArea = document.getElementById('conversation-area');
    if (conversationArea) {
        conversationArea.innerHTML = '<p class="empty-conversation">Start generating images by typing a prompt below</p>';
    }

    clearRoundTimerIfAny();
    const timerEl = document.getElementById('timer');
    if (timerEl) {
        timerEl.textContent = '5:00';
        timerEl.classList.remove('warning');
    }

    applyOnboardingGenerateState();
    syncImageContextBulletsVisibility();
    showScreen('game');
});

socket.on('onboarding_practice_voting_started', (data) => {
    if (gameState.isAdmin) return;
    showOnboardingPracticeVotingFromPayload(data);
});

socket.on('onboarding_practice_points_saved', () => {
    if (gameState.isAdmin) return;
    const vals = getObPracticeValues();
    applyObPracticeSubmittedState(vals);
});

socket.on('game_started', (data) => {
    // Don't handle game events if user is admin
    if (gameState.isAdmin) {
        return;
    }

    gameState.inOnboarding = false;
    gameState.onboardingPhase = 'prompting';
    gameState.onboardingPromptCount = 0;
    setOnboardingInstructionsPanelVisible(false);
    const obHint = document.getElementById('onboarding-limit-hint');
    if (obHint) {
        obHint.style.display = 'none';
        obHint.textContent = '';
    }
    const genBtn = document.getElementById('generate-btn');
    const pInput = document.getElementById('prompt-input');
    if (genBtn) {
        genBtn.disabled = false;
        genBtn.style.display = '';
    }
    if (pInput) {
        pInput.disabled = false;
        pInput.style.display = '';
    }

    // Reset selection phase flag for new round
    gameState.inSelectionPhase = false;

    gameState.imageContextBulletsEnabled = data.image_context_bullets === true;
    
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

    setGameRoundHeadingNormal(data.round);

    // Display target image
    const targetImage = document.getElementById('target-image-display');
    targetImage.src = data.target.url;
    targetImage.alt = 'Target Image';

    // Clear conversation area
    const conversationArea = document.getElementById('conversation-area');
    conversationArea.innerHTML = '<p class="empty-conversation">Start generating images by typing a prompt below</p>';

    const aggPanel = document.getElementById('aggregate-heuristics-panel');
    if (aggPanel) {
        aggPanel.style.display = 'none';
        aggPanel.innerHTML = '';
        aggPanel.setAttribute('aria-hidden', 'true');
        // Round 1: panel stays hidden until first image_generated (server does not set the flag).
        // Rounds 2–3 + T_NA/T_HU: server sends show_aggregate_heuristics_immediate + zero totals.
        if (
            data.show_aggregate_heuristics_immediate &&
            Array.isArray(data.aggregate_heuristic_preview) &&
            data.aggregate_heuristic_preview.length
        ) {
            aggPanel.style.display = 'block';
            aggPanel.setAttribute('aria-hidden', 'false');
            aggPanel.innerHTML = `<h4 class="aggregate-heuristics-title">Your round totals</h4>${buildHeuristicLinesHtml(
                data.aggregate_heuristic_preview,
            )}`;
        }
    }

    // Set up initial avatar state based on character data from server
    if (data.character) {
        updateAvatarState(data.character);
        
        // Display welcome message if present (lasts 20 seconds or until first prompt)
        // (Only when character bubble/avatar exist on prompting screen; omitted when Bud/Spud removed below target)
        const welcomeBubble = document.getElementById('character-bubble');
        const welcomeText = document.getElementById('character-bubble-text');
        if (data.character.message && welcomeBubble && welcomeText) {
            // Clear any existing message auto-hide timer
            if (gameState.messageAutoHideTimer) {
                clearTimeout(gameState.messageAutoHideTimer);
                gameState.messageAutoHideTimer = null;
            }
            
            // Display the welcome message
            welcomeText.textContent = data.character.message;
            welcomeBubble.style.display = 'block';
            
            // Style based on character
            if (data.character.character === 'Spud') {
                welcomeBubble.style.background = '#ffe8e8';
                welcomeBubble.style.borderLeft = '4px solid #ff6b6b';
                welcomeBubble.style.setProperty('--bubble-color', '#ffe8e8');
            } else {
                welcomeBubble.style.background = '#fff3bf';
                welcomeBubble.style.borderLeft = '4px solid #fab005';
                welcomeBubble.style.setProperty('--bubble-color', '#fff3bf');
            }
            
            // Auto-hide message after 20 seconds
            gameState.messageAutoHideTimer = setTimeout(() => {
                welcomeBubble.style.display = 'none';
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

    syncImageContextBulletsVisibility();
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
    if (gameState.inOnboarding) {
        return;
    }
    updateAvatarState(data);

    const messageBubble = document.getElementById('character-bubble');
    const messageText = document.getElementById('character-bubble-text');
    if (!messageBubble || !messageText) return;

    // Clear any existing message auto-hide timer
    if (gameState.messageAutoHideTimer) {
        clearTimeout(gameState.messageAutoHideTimer);
        gameState.messageAutoHideTimer = null;
    }

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

const IMAGE_GEN_FAIL_MSG = "That didn't work! Try a different prompt.";

socket.on('image_generation_error', (data) => {
    console.log('Image generation error:', data.error_type, data.message);

    const conversationArea = document.getElementById('conversation-area');
    if (conversationArea) {
        const imageContainers = conversationArea.querySelectorAll('.image-container');
        if (imageContainers.length > 0) {
            const lastContainer = imageContainers[imageContainers.length - 1];
            if (lastContainer.querySelector('.image-loading')) {
                lastContainer.innerHTML = `<div class="image-gen-error-msg" role="alert">${IMAGE_GEN_FAIL_MSG}</div>`;
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
    if (data.prompt_index != null) {
        item.dataset.promptIndex = String(data.prompt_index);
    }
    if (data.onboarding) {
        item.dataset.onboarding = '1';
    }
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
    if (data.onboarding) {
        gameState.onboardingPromptCount = (gameState.onboardingPromptCount || 0) + 1;
    }

    const conversationArea = document.getElementById('conversation-area');
    /** errorPath: prefer a row that still shows loading. Success: fill the row for this prompt_index. */
    const resolveConversationSlot = (errorPath) => {
        if (!conversationArea) return null;
        const byIndex = findConversationImageContainer(conversationArea, data.prompt_index);
        if (byIndex) {
            if (!errorPath) return byIndex;
            if (byIndex.querySelector('.image-loading')) return byIndex;
        }
        return findConversationImageContainerFallback(conversationArea);
    };

    // Skip error images - don't add them to generatedImages or selection gallery
    if (data.error_type) {
        if (data.onboarding) {
            const slot = resolveConversationSlot(true);
            if (slot && slot.querySelector('.image-loading')) {
                slot.innerHTML = `<div class="image-gen-error-msg" role="alert">${IMAGE_GEN_FAIL_MSG}</div>`;
            }
            applyOnboardingGenerateState();
        } else {
            const slot = resolveConversationSlot(true);
            if (slot && slot.querySelector('.image-loading')) {
                let inner = `<div class="image-gen-error-msg" role="alert">${IMAGE_GEN_FAIL_MSG}</div>`;
                if (data.show_prompting_heuristics && Array.isArray(data.per_image_heuristic_display) && data.per_image_heuristic_display.length) {
                    const lines = buildHeuristicLinesHtml(data.per_image_heuristic_display);
                    inner = `<div class="gen-img-row"><div class="gen-img-cell">${inner}</div><div class="heuristic-box">${lines}</div></div>`;
                }
                slot.innerHTML = inner;
            }
            const aggPanelErr = document.getElementById('aggregate-heuristics-panel');
            if (aggPanelErr && data.show_prompting_heuristics && Array.isArray(data.aggregate_heuristic_display) && data.aggregate_heuristic_display.length) {
                aggPanelErr.style.display = 'block';
                const lines = buildHeuristicLinesHtml(data.aggregate_heuristic_display);
                aggPanelErr.innerHTML = `<h4 class="aggregate-heuristics-title">Your round totals</h4>${lines}`;
            }
            if (conversationArea) {
                conversationArea.scrollTop = conversationArea.scrollHeight;
            }
        }
        return;
    }

    gameState.generatedImages.push(data);

    const slot = resolveConversationSlot(false);
    if (slot) {
        const imageSrc = data.image_url || data.image_data || '';
        const pidAttr =
            data.prompt_id != null && data.prompt_id !== ''
                ? ` data-prompt-id="${String(data.prompt_id).replace(/"/g, '&quot;')}"`
                : '';
        const pidxAttr =
            data.prompt_index != null ? ` data-prompt-index="${String(data.prompt_index)}"` : '';
        let imgHtml = `<img src="${imageSrc}" alt="Generated image" class="image-result"${pidAttr}${pidxAttr}>`;
        if (data.show_prompting_heuristics && Array.isArray(data.per_image_heuristic_display) && data.per_image_heuristic_display.length) {
            const lines = buildHeuristicLinesHtml(data.per_image_heuristic_display);
            imgHtml = `<div class="gen-img-row"><div class="gen-img-cell">${imgHtml}</div><div class="heuristic-box">${lines}</div></div>`;
        }
        slot.innerHTML = imgHtml;
    }

    const aggPanel = document.getElementById('aggregate-heuristics-panel');
    if (aggPanel) {
        if (data.show_prompting_heuristics && Array.isArray(data.aggregate_heuristic_display) && data.aggregate_heuristic_display.length) {
            aggPanel.style.display = 'block';
            const lines = buildHeuristicLinesHtml(data.aggregate_heuristic_display);
            aggPanel.innerHTML = `<h4 class="aggregate-heuristics-title">Your round totals</h4>${lines}`;
        } else {
            aggPanel.style.display = 'none';
            aggPanel.innerHTML = '';
        }
    }

    if (conversationArea) {
        conversationArea.scrollTop = conversationArea.scrollHeight;
    }

    if (data.onboarding) {
        applyOnboardingGenerateState();
    }

    const selectionScreen = document.getElementById('selection-screen');
    const isSelectionScreenActive = selectionScreen && selectionScreen.classList.contains('active');

    if (gameState.inSelectionPhase || isSelectionScreenActive) {
        const validImageIndex = gameState.generatedImages.length - 1;

        if (selectionScreen) {
            addImageToSelectionGallery(data, validImageIndex);
        }

        if (!gameState.hasConfirmedSelection && isSelectionScreenActive) {
            gameState.selectedImageIndex = validImageIndex;

            const gallery = document.getElementById('selection-gallery');
            if (gallery) {
                const items = gallery.querySelectorAll('.selection-item');
                if (items.length > 0) {
                    const gi = generatedIndexToGalleryItemIndex(validImageIndex);
                    items.forEach((i) => i.classList.remove('selected'));
                    if (gi >= 0 && items[gi]) {
                        items[gi].classList.add('selected');
                    } else {
                        items[items.length - 1].classList.add('selected');
                    }
                }
            }

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

    const existingItems = gallery.querySelectorAll('.selection-item');
    if (imgData.prompt_id) {
        for (let i = 0; i < existingItems.length; i++) {
            const itemImg = existingItems[i].querySelector('img');
            if (itemImg && itemImg.dataset.promptId === String(imgData.prompt_id)) {
                return;
            }
        }
    } else if (imgData.prompt_index != null) {
        for (let i = 0; i < existingItems.length; i++) {
            if (existingItems[i].dataset.promptIndex === String(imgData.prompt_index)) {
                return;
            }
        }
    } else {
        let validImageCount = 0;
        for (let i = 0; i < index && i < gameState.generatedImages.length; i++) {
            if (!gameState.generatedImages[i].error_type) {
                validImageCount++;
            }
        }
        if (existingItems.length > validImageCount) {
            return;
        }
    }

    const item = document.createElement('div');
    item.className = 'selection-item';
    if (imgData.prompt_index != null) {
        item.dataset.promptIndex = String(imgData.prompt_index);
    }
    const imageSrc = imgData.image_url || imgData.image_data || '';
    const pidAttr =
        imgData.prompt_id != null && imgData.prompt_id !== ''
            ? ` data-prompt-id="${String(imgData.prompt_id).replace(/"/g, '&quot;')}"`
            : '';
    const pidxAttr =
        imgData.prompt_index != null ? ` data-prompt-index="${String(imgData.prompt_index)}"` : '';

    let heurBelow = '';
    if (
        showTreatmentSelectionHeuristics() &&
        Array.isArray(imgData.per_image_heuristic_display) &&
        imgData.per_image_heuristic_display.length
    ) {
        heurBelow = `<div class="selection-heuristics-below heuristic-box">${buildHeuristicLinesHtml(
            imgData.per_image_heuristic_display,
        )}</div>`;
    }

    item.innerHTML = `
            <img src="${imageSrc}" alt="Generated image" class="selection-gallery-img"${pidAttr}${pidxAttr}>
            ${heurBelow}
            <div class="image-context-bullets gameplay-image-context-bullets" aria-hidden="true">
                <ul class="image-context-bullets-list"></ul>
            </div>
        `;

    item.addEventListener('click', () => {
        document.querySelectorAll('.selection-item').forEach((i) => i.classList.remove('selected'));
        item.classList.add('selected');
        gameState.selectedImageIndex = index;
        const confirmBtn = document.getElementById('confirm-selection-btn');
        if (confirmBtn) {
            confirmBtn.disabled = false;
        }
        const defaultNotice = document.getElementById('default-selection-notice');
        if (defaultNotice) {
            defaultNotice.style.display = 'none';
        }
    });

    gallery.appendChild(item);
    syncImageContextBulletsVisibility();
}

socket.on('image_url_updated', (data) => {
    // Update image URL in client-side array when upload completes
    // This allows selection screen to use URLs instead of base64
    if (data.prompt_id && data.image_url) {
        const imageIndex = gameState.generatedImages.findIndex((img) => img.prompt_id === data.prompt_id);
        if (imageIndex !== -1) {
            gameState.generatedImages[imageIndex].image_url = data.image_url;
            if (gameState.generatedImages[imageIndex].image_data) {
                delete gameState.generatedImages[imageIndex].image_data;
            }
        }

        const pid = String(data.prompt_id);
        const gallery = document.getElementById('selection-gallery');
        if (gallery) {
            const img = gallery.querySelector(`img[data-prompt-id="${pid}"]`);
            if (img) {
                img.src = data.image_url;
            }
        }

        const conversationArea = document.getElementById('conversation-area');
        if (conversationArea) {
            const imgC = conversationArea.querySelector(`img.image-result[data-prompt-id="${pid}"]`);
            if (imgC) {
                imgC.src = data.image_url;
            }
        }
    }
});

socket.on('image_prompt_binding', (data) => {
    const { prompt_index, prompt_id } = data;
    if (prompt_index == null || prompt_id == null) return;
    const pidStr = String(prompt_id);
    for (let i = 0; i < gameState.generatedImages.length; i++) {
        const im = gameState.generatedImages[i];
        if (String(im.prompt_index) === String(prompt_index)) {
            im.prompt_id = prompt_id;
            break;
        }
    }
    const gallery = document.getElementById('selection-gallery');
    if (gallery) {
        const item = gallery.querySelector(`.selection-item[data-prompt-index="${prompt_index}"]`);
        const img = item ? item.querySelector('img') : gallery.querySelector(`img[data-prompt-index="${prompt_index}"]`);
        if (img) {
            img.dataset.promptId = pidStr;
        }
    }
    const conversationArea = document.getElementById('conversation-area');
    if (conversationArea) {
        const img2 = conversationArea.querySelector(`img[data-prompt-index="${prompt_index}"]`);
        if (img2) {
            img2.dataset.promptId = pidStr;
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
    clearRoundTimerIfAny();
    gameState.imageContextBulletsEnabled = data.image_context_bullets === true;

    console.log('[CLIENT] Showing selection screen');
    
    // Mark that we're in selection phase (for late-arriving images)
    gameState.inSelectionPhase = true;
    
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
    syncImageContextBulletsVisibility();

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
            const items = gallery ? gallery.querySelectorAll('.selection-item') : [];
            const gi = generatedIndexToGalleryItemIndex(lastValidIndex);
            items.forEach((el) => el.classList.remove('selected'));
            if (gi >= 0 && items[gi]) {
                items[gi].classList.add('selected');
            } else if (items.length) {
                items[items.length - 1].classList.add('selected');
            }
        } else {
            const lastIndex = gameState.generatedImages.length - 1;
            gameState.selectedImageIndex = lastIndex;
            const items = gallery ? gallery.querySelectorAll('.selection-item') : [];
            items.forEach((el) => el.classList.remove('selected'));
            if (items.length) {
                items[items.length - 1].classList.add('selected');
            }
        }
        if (confirmBtn) {
            confirmBtn.disabled = false;
        }
    }

    // Start selection timer
    // Use synchronized start time from server for timer synchronization
    startSelectionTimer(data.duration || 90, data.start_time);
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

    if (timerEl.timerInterval) {
        clearInterval(timerEl.timerInterval);
        timerEl.timerInterval = null;
    }
    
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
            
            // If selection not confirmed, auto-select and notify server
            // Check hasConfirmedSelection instead of selectedImageIndex to handle case where
            // player clicked an image but didn't press "Confirm Selection"
            if (!gameState.hasConfirmedSelection && gameState.generatedImages.length > 0) {
                const defaultNotice = document.getElementById('default-selection-notice');
                if (defaultNotice) {
                    defaultNotice.style.display = 'block';
                }
                
                // Determine which image to select:
                // 1. If player clicked an image (selectedImageIndex is set), use that if it's valid
                // 2. Otherwise, use the last valid (non-error) image
                let effectiveIndex;
                let lastValidIndex = -1;
                
                // Find the last valid (non-error) image
                for (let i = gameState.generatedImages.length - 1; i >= 0; i--) {
                    if (!gameState.generatedImages[i].error_type) {
                        lastValidIndex = i;
                        break;
                    }
                }
                
                // Check if player's clicked image is valid
                if (gameState.selectedImageIndex !== null) {
                    const clickedImage = gameState.generatedImages[gameState.selectedImageIndex];
                    // Use clicked image if it's valid (no error_type)
                    if (clickedImage && !clickedImage.error_type) {
                        effectiveIndex = gameState.selectedImageIndex;
                    } else if (lastValidIndex >= 0) {
                        // Clicked image has error, use last valid instead
                        effectiveIndex = lastValidIndex;
                        gameState.selectedImageIndex = lastValidIndex;
                    } else {
                        // Fallback: use clicked image even if it has an error (shouldn't happen)
                        effectiveIndex = gameState.selectedImageIndex;
                    }
                } else if (lastValidIndex >= 0) {
                    // No image clicked, use last valid image
                    effectiveIndex = lastValidIndex;
                    gameState.selectedImageIndex = lastValidIndex;
                } else {
                    // Fallback: use last image even if it has an error (shouldn't happen)
                    effectiveIndex = gameState.generatedImages.length - 1;
                    gameState.selectedImageIndex = effectiveIndex;
                }
                
                // Visual feedback - select the chosen image in the gallery
                const gallery = document.getElementById('selection-gallery');
                if (gallery) {
                    const items = gallery.querySelectorAll('.selection-item');
                    if (items.length > 0) {
                        items.forEach(i => i.classList.remove('selected'));
                        // Find the item corresponding to effectiveIndex in the gallery
                        // Gallery only contains valid images, so we need to map the index
                        let galleryIndex = 0;
                        for (let i = 0; i <= effectiveIndex && i < gameState.generatedImages.length; i++) {
                            if (!gameState.generatedImages[i].error_type) {
                                if (i === effectiveIndex) {
                                    items[galleryIndex]?.classList.add('selected');
                                    break;
                                }
                                galleryIndex++;
                            }
                        }
                        // Fallback: select last item if mapping failed
                        if (galleryIndex >= items.length) {
                            items[items.length - 1]?.classList.add('selected');
                        }
                    }
                }
                
                // Notify server of auto-selection (send prompt_id to avoid index mismatch)
                const autoSelectedImage = gameState.generatedImages[effectiveIndex];
                if (autoSelectedImage && (autoSelectedImage.prompt_id || autoSelectedImage.prompt_index != null)) {
                    socket.emit('select_image', {
                        prompt_id: autoSelectedImage.prompt_id,
                        prompt_index: autoSelectedImage.prompt_index,
                        image_index: effectiveIndex,
                    });
                    console.log('[CLIENT] Timer expired - auto-selected image (clicked or last valid)');
                } else {
                    console.error('[CLIENT] Timer expired but cannot auto-select - no valid image reference');
                }
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

    gameState.imageContextBulletsEnabled = data.image_context_bullets === true;
    
    showScreen('voting');
    syncAllocationVotingHeaderAlias();

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
    if (!gallery) {
        syncImageContextBulletsVisibility();
        return;
    }
    
    gallery.innerHTML = '';

    // Filter out player's own image
    const mySessionId = data.my_session_id;
    const otherPlayerImages = data.images.filter(item => item.session_id !== mySessionId);

    if (otherPlayerImages.length === 0) {
        gallery.innerHTML = '<p>No other players to vote for!</p>';
        syncImageContextBulletsVisibility();
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
            <div class="image-context-bullets gameplay-image-context-bullets" aria-hidden="true">
                <ul class="image-context-bullets-list"></ul>
            </div>
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

    syncImageContextBulletsVisibility();
    
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

function syncAllocationVotingHeaderAlias() {
    const name = (gameState.playerName || '').trim();
    const allocEl = document.getElementById('allocation-voting-player-name');
    if (allocEl) allocEl.textContent = name;
    const obEl = document.getElementById('ob-practice-voting-player-name');
    if (obEl) obEl.textContent = name;
}

function updateAllocationPointsHeader(a, b, c, elementId) {
    const el = document.getElementById(elementId || 'allocation-points-header');
    if (!el) return;
    const total = (parseInt(a, 10) || 0) + (parseInt(b, 10) || 0) + (parseInt(c, 10) || 0);
    if (total > 10) {
        el.textContent = `${total - 10} over — use exactly 10 points`;
        return;
    }
    const remaining = 10 - total;
    el.textContent = `${remaining} ${remaining === 1 ? 'point' : 'points'} to allocate`;
}

socket.on('allocation_vote_started', (data) => {
    if (gameState.isAdmin) return;
    clearRoundTimerIfAny();
    showScreen('voting');
    syncAllocationVotingHeaderAlias();
    gameState.allocationRoundIndex = data.voting_round_index || 1;
    const ins = document.getElementById('allocation-instructions');
    if (ins) ins.textContent = 'Distribute 10 points among the following images';
    const rn = document.getElementById('allocation-round-num');
    const rt = document.getElementById('allocation-round-total');
    if (rn) rn.textContent = String(data.voting_round_index || 1);
    if (rt) rt.textContent = String(data.total_voting_rounds || 10);
    const tgt = document.getElementById('voting-target-image');
    if (tgt && data.target_image_url) {
        tgt.src = data.target_image_url;
    }
    const slots = document.getElementById('allocation-slots');
    if (!slots) return;
    slots.innerHTML = '';
    let opts = data.options || [];
    if (opts.length !== 3) {
        console.error('[CLIENT] allocation_vote_started: expected 3 options, got', opts.length, data);
        opts = [
            { image_url: '/static/voting_fixtures/HU/options/slot_a.svg', heuristic_display: [] },
            { image_url: '/static/voting_fixtures/HU/options/slot_b.svg', heuristic_display: [] },
            { image_url: '/static/voting_fixtures/HU/options/slot_c.svg', heuristic_display: [] },
        ];
    }
    opts.forEach((opt, idx) => {
        const col = document.createElement('div');
        col.className = 'allocation-slot';
        const imgUrl = opt.image_url || '';
        let heurHtml = '';
        if (data.show_voting_heuristics && Array.isArray(opt.heuristic_display) && opt.heuristic_display.length) {
            heurHtml = '<div class="heuristic-box voting-heur">' + opt.heuristic_display.map((h) => {
                const lab = (h.label || '').replace(/</g, '&lt;');
                const val = (h.value || '').replace(/</g, '&lt;');
                return `<div class="heuristic-line"><span class="hl">${lab}</span>: <span class="hv">${val}</span></div>`;
            }).join('') + '</div>';
        }
        col.innerHTML = `
            <div class="allocation-slot-img-wrap"><img src="${imgUrl}" alt="Option ${idx + 1}" class="allocation-opt-img"></div>
            ${heurHtml}
            <label class="allocation-pts-label">Points</label>
            <input type="number" min="0" max="10" step="1" class="allocation-pts-input" data-slot="${idx}" value="0">
        `;
        slots.appendChild(col);
    });
    const inputs = slots.querySelectorAll('.allocation-pts-input');
    const sync = () => {
        const v = [0, 1, 2].map((i) => {
            const inp = slots.querySelector(`.allocation-pts-input[data-slot="${i}"]`);
            return inp ? inp.value : '0';
        });
        updateAllocationPointsHeader(v[0], v[1], v[2], 'allocation-points-header');
        const t = (parseInt(v[0], 10) || 0) + (parseInt(v[1], 10) || 0) + (parseInt(v[2], 10) || 0);
        const btn = document.getElementById('confirm-allocation-btn');
        if (btn) btn.disabled = t !== 10;
    };
    inputs.forEach((inp) => inp.addEventListener('input', sync));
    sync();
    const btn = document.getElementById('confirm-allocation-btn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Submit points';
        btn.onclick = () => {
            const v = [0, 1, 2].map((i) => {
                const inp = slots.querySelector(`.allocation-pts-input[data-slot="${i}"]`);
                return parseInt(inp && inp.value, 10) || 0;
            });
            if (v[0] + v[1] + v[2] !== 10) return;
            socket.emit('submit_point_allocation', {
                points_slot_1: v[0],
                points_slot_2: v[1],
                points_slot_3: v[2],
                voting_round_index: gameState.allocationRoundIndex,
            });
            btn.disabled = true;
            btn.textContent = 'Submitted';
        };
    }
});

socket.on('allocation_saved', (data) => {
    if (gameState.isAdmin) return;
    const ins = document.getElementById('allocation-instructions');
    if (data && data.session_complete && data.waiting_for_others && ins) {
        ins.textContent = 'All your voting rounds are complete. Waiting for other players to finish…';
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

    const hintGo = document.getElementById('gameover-post-survey-hint');
    if (hintGo) hintGo.style.display = 'block';

    gameState.pendingGameOver = data;
    renderGameOverContent(data);
});

socket.on('game_restarted', (data) => {
    // Admin stays in the game, just reset their view
    if (gameState.isAdmin) {
    showScreen('lobby');
    // Reset state
    gameState.currentRound = 0;
    gameState.inOnboarding = false;
    gameState.inAllocationVoting = false;
    gameState.onboardingPhase = 'prompting';
    gameState.onboardingPromptCount = 0;
    setOnboardingInstructionsPanelVisible(false);
    gameState.selectedImageIndex = null;
    gameState.generatedImages = [];
    gameState.votedFor = null;
    gameState.postSurveyActive = false;
    gameState.postSurveyCompleted = false;
    gameState.canStartPostSurvey = false;
    gameState.pendingGameOver = null;
    syncStartPostSurveyButton();
        
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
    gameState.postSurveyActive = false;
    gameState.postSurveyCompleted = false;
    gameState.canStartPostSurvey = false;
    gameState.pendingGameOver = null;
    delete document.getElementById('post-game-survey-submit-btn')?.dataset?.submitted;
    resetPostGameSurveyForm();
    gameState.imageContextBulletsEnabled = false;
    syncImageContextBulletsVisibility();
    gameState.currentRound = 0;
    gameState.inOnboarding = false;
    gameState.onboardingPhase = 'prompting';
    gameState.onboardingPromptCount = 0;
    setOnboardingInstructionsPanelVisible(false);
    resetObPracticeVotingForm();
    gameState.selectedImageIndex = null;
    gameState.generatedImages = [];
    gameState.votedFor = null;
    gameState.playerName = null;
    gameState.playerCondition = null;
    gameState.playerCharacter = null;
    gameState.isAdmin = false;
    gameState.hasConfirmedSelection = false;
    
    const joinBtn = document.getElementById('join-btn');
    if (joinBtn) joinBtn.disabled = false;
    const aliasEl = document.getElementById('current-alias');
    if (aliasEl) {
        aliasEl.textContent = '';
        aliasEl.style.display = 'none';
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
    const joinBtn = document.getElementById('join-btn');
    if (joinBtn) joinBtn.disabled = false;
    const msg = data && data.message ? data.message : 'Something went wrong.';
    const obScreen = screens.onboardingPracticeVoting;
    if (obScreen && obScreen.classList.contains('active')) {
        const err = document.getElementById('ob-practice-vote-error');
        if (err) {
            err.textContent = msg;
            err.style.display = 'block';
            return;
        }
    }
    const pgScreen = screens.postGameSurvey;
    if (pgScreen && pgScreen.classList.contains('active')) {
        const errPg = document.getElementById('post-game-survey-error');
        if (errPg) {
            errPg.textContent = msg;
            errPg.style.display = 'block';
            return;
        }
    }
    alert(msg);
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
    // Only update the main round timer while on the game screen (avoid fighting selection / other UIs)
    if (!screens.game || !screens.game.classList.contains('active')) {
        return;
    }
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
    gameState.imageContextBulletsEnabled = false;
    syncImageContextBulletsVisibility();
    gameState.inSelectionPhase = false;
    gameState.selectedImageIndex = null;
    gameState.generatedImages = [];
    gameState.votedFor = null;
    gameState.tempVoteSelection = null;
    gameState.currentRound = 0;
    gameState.inOnboarding = false;
    gameState.onboardingPhase = 'prompting';
    gameState.onboardingPromptCount = 0;
    setOnboardingInstructionsPanelVisible(false);
    clearRoundTimerIfAny();
    resetObPracticeVotingForm();
    const obHintRt = document.getElementById('onboarding-limit-hint');
    if (obHintRt) {
        obHintRt.style.display = 'none';
        obHintRt.textContent = '';
    }
    const genBtnRt = document.getElementById('generate-btn');
    const pInRt = document.getElementById('prompt-input');
    if (genBtnRt) {
        genBtnRt.disabled = false;
        genBtnRt.style.display = '';
    }
    if (pInRt) {
        pInRt.disabled = false;
        pInRt.style.display = '';
    }
    
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

    const hintRt = document.getElementById('gameover-post-survey-hint');
    if (hintRt) hintRt.style.display = 'none';
    delete document.getElementById('post-game-survey-submit-btn')?.dataset?.submitted;
    resetPostGameSurveyForm();
    if (gameState.isAdmin) {
        syncStartPostSurveyButton();
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
