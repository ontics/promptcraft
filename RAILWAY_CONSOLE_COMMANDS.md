# Railway Console Commands

This document provides step-by-step instructions for accessing Railway's console and running admin commands to control the game.

## Accessing Railway Console

1. Log in to [Railway](https://railway.app)
2. Select your PromptCraft project
3. Click on your service/deployment
4. Click the "Shell" or "Console" tab (or look for a terminal icon)
5. You should see a command prompt where you can run Python commands

## Available Console Commands

### 1. Skip Selection Screen (Go from Selection to Voting)

**Python Command:**
```python
python -c "from app import *; skip_selection()"
```

**HTTP Alternative:**
```bash
curl -X POST https://your-app.railway.app/admin/console/skip-selection
```

**When to use:** When players are stuck on the selection screen and all have selected (or timer expired).

---

### 2. Skip Voting Screen (Go from Voting to Round Results)

**Python Command:**
```python
python -c "from app import *; skip_voting_console()"
```

**HTTP Alternative:**
```bash
curl -X POST https://your-app.railway.app/admin/console/skip-voting
```

**When to use:** When all players have voted but the game hasn't advanced to results.

---

### 3. Next Round (Go from Round Results to Next Round or Final Leaderboard)

**Python Command:**
```python
python -c "from app import *; next_round_console()"
```

**HTTP Alternative:**
```bash
curl -X POST https://your-app.railway.app/admin/console/next-round
```

**When to use:** After round results are shown, to advance to the next round (or final leaderboard if round 3).

---

### 4. Restart Game (Clear All Players and Reset Game)

**Python Command:**
```python
python -c "from app import *; restart_game_console()"
```

**HTTP Alternative:**
```bash
curl -X POST https://your-app.railway.app/admin/console/restart-game
```

**When to use:** To start a fresh game session. This kicks all players (including admin) and resets the game state.

---

### 5. Set Player Team (Manually Assign Team)

**Python Command:**
```python
python -c "from app import *; set_player_team_console('SESSION_ID_HERE', 'Green')"
```

Replace `SESSION_ID_HERE` with the actual session_id of the player (you can find this in the admin dashboard or logs).

**HTTP Alternative:**
```bash
curl -X POST https://your-app.railway.app/admin/console/set-player-team \
  -H "Content-Type: application/json" \
  -d '{"session_id": "SESSION_ID_HERE", "team": "Green"}'
```

**When to use:** If a player rejoins between rounds and needs to be reassigned to their correct team.

**Finding Session IDs:**
- Check the admin dashboard player list (session_id is shown)
- Check Railway logs for player join events
- Use Python in console: `python -c "from app import players; print([(p['name'], p['session_id']) for p in players.values()])"`

---

## Troubleshooting

### Command Not Found
If you get an error like "command not found", make sure you're in the correct directory. Try:
```bash
cd /app
python -c "from app import *; skip_selection()"
```

### Import Errors
If you get import errors, the app may not be fully loaded. Try:
```python
python
>>> from app import *
>>> skip_selection()
```

### Checking Game State
To check the current game state:
```python
python -c "from app import game_state, players; print(f\"Status: {game_state['status']}, Round: {game_state['current_round']}, Players: {len(players)}\")"
```

### Listing All Players
To see all players and their session IDs:
```python
python -c "from app import players; [print(f\"{p['name']}: {p['session_id']}\") for p in players.values()]"
```

---

## Important Notes

- **All commands require admin privileges** - they will only work if called from the server context
- **HTTP endpoints are unauthenticated** - consider adding authentication if exposing publicly
- **Restart game** kicks ALL players including admin - you'll need to rejoin
- **Team assignment** persists to database - players keep their team even after reconnection

---

## Quick Reference

| Action | Python Command | HTTP Endpoint |
|--------|---------------|---------------|
| Skip Selection | `skip_selection()` | `/admin/console/skip-selection` |
| Skip Voting | `skip_voting_console()` | `/admin/console/skip-voting` |
| Next Round | `next_round_console()` | `/admin/console/next-round` |
| Restart Game | `restart_game_console()` | `/admin/console/restart-game` |
| Set Team | `set_player_team_console('session_id', 'Green')` | `/admin/console/set-player-team` |

