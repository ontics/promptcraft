# Stress Test Script - How to Run

## Overview
This script simulates 30 players (Bot1, Bot2, ... Bot30) joining your PromptCraft game, waiting for teams to be assigned and the game to start, then sending 5-15 prompts each randomly distributed over the 5-minute round duration.

## Prerequisites

1. **Install dependencies:**
   ```bash
   pip install python-socketio
   ```
   
   Note: 
   - `python-socketio` is already in `requirements.txt`, so if you have the project dependencies installed, you should be good.
   - `asyncio` is a built-in Python module (Python 3.7+), no installation needed.

2. **Make sure your Railway app is running** at `https://promptcraft.up.railway.app`

## Running the Test

### Basic Usage:
```bash
python3 stress_test.py
```

### Custom Server URL:
```bash
python3 stress_test.py https://your-custom-url.com
```

## Test Flow

1. **Script connects 30 players** (Bot1 through Bot30) to your game
2. **You (as admin) need to:**
   - Go to the game admin dashboard
   - Assign teams (or use auto-assign button)
   - Click "Start Game"
3. **Script automatically:**
   - Waits for `game_started` event
   - Each bot sends 5-15 prompts randomly distributed over 5 minutes
   - Prompts are spaced out with random intervals (minimum 5 seconds between prompts)
   - Each bot starts sending at a random time within the first 30 seconds
4. **After 5 minutes + buffer**, the script collects statistics and disconnects

## What to Monitor

While the test runs, monitor:

1. **Railway Dashboard:**
   - Memory usage (should stay reasonable)
   - CPU usage
   - Response times
   - Error rates

2. **Game Admin Dashboard:**
   - All 30 bots should appear in the lobby
   - They should receive team assignments
   - They should start sending prompts once the game starts
   - Check for any errors or disconnections

3. **Script Output:**
   - Connection status for each bot
   - Prompt sending progress
   - Final statistics (prompts sent, images received, errors)

## Expected Results

- **30 players** should join successfully
- **150-450 total prompts** (30 players × 5-15 prompts each)
- **Images received** should roughly match prompts sent (some may fail due to API limits)
- **Memory usage** should remain stable (watch for memory leaks)

## Troubleshooting

### Bots don't connect:
- Check that Railway app is running
- Verify the URL is correct (use `https://` not `http://`)
- Check Railway logs for connection errors

### Bots don't send prompts:
- Make sure you assigned teams and started the game
- Check that bots received the `game_started` event (script will show this)
- Verify the game is in "playing" status

### Too many errors:
- May hit Gemini API rate limits with 30 concurrent players
- Consider reducing `NUM_PLAYERS` to 10-15 for initial testing
- Check Railway memory limits

## Configuration

Edit `stress_test.py` to adjust:
- `NUM_PLAYERS = 30` - Number of bots
- `PROMPTS_PER_PLAYER_MIN = 5` - Minimum prompts per bot
- `PROMPTS_PER_PLAYER_MAX = 15` - Maximum prompts per bot
- `ROUND_DURATION = 300` - Round duration in seconds (5 minutes)




## Overview
This script simulates 30 players (Bot1, Bot2, ... Bot30) joining your PromptCraft game, waiting for teams to be assigned and the game to start, then sending 5-15 prompts each randomly distributed over the 5-minute round duration.

## Prerequisites

1. **Install dependencies:**
   ```bash
   pip install python-socketio
   ```
   
   Note: 
   - `python-socketio` is already in `requirements.txt`, so if you have the project dependencies installed, you should be good.
   - `asyncio` is a built-in Python module (Python 3.7+), no installation needed.

2. **Make sure your Railway app is running** at `https://promptcraft.up.railway.app`

## Running the Test

### Basic Usage:
```bash
python3 stress_test.py
```

### Custom Server URL:
```bash
python3 stress_test.py https://your-custom-url.com
```

## Test Flow

1. **Script connects 30 players** (Bot1 through Bot30) to your game
2. **You (as admin) need to:**
   - Go to the game admin dashboard
   - Assign teams (or use auto-assign button)
   - Click "Start Game"
3. **Script automatically:**
   - Waits for `game_started` event
   - Each bot sends 5-15 prompts randomly distributed over 5 minutes
   - Prompts are spaced out with random intervals (minimum 5 seconds between prompts)
   - Each bot starts sending at a random time within the first 30 seconds
4. **After 5 minutes + buffer**, the script collects statistics and disconnects

## What to Monitor

While the test runs, monitor:

1. **Railway Dashboard:**
   - Memory usage (should stay reasonable)
   - CPU usage
   - Response times
   - Error rates

2. **Game Admin Dashboard:**
   - All 30 bots should appear in the lobby
   - They should receive team assignments
   - They should start sending prompts once the game starts
   - Check for any errors or disconnections

3. **Script Output:**
   - Connection status for each bot
   - Prompt sending progress
   - Final statistics (prompts sent, images received, errors)

## Expected Results

- **30 players** should join successfully
- **150-450 total prompts** (30 players × 5-15 prompts each)
- **Images received** should roughly match prompts sent (some may fail due to API limits)
- **Memory usage** should remain stable (watch for memory leaks)

## Troubleshooting

### Bots don't connect:
- Check that Railway app is running
- Verify the URL is correct (use `https://` not `http://`)
- Check Railway logs for connection errors

### Bots don't send prompts:
- Make sure you assigned teams and started the game
- Check that bots received the `game_started` event (script will show this)
- Verify the game is in "playing" status

### Too many errors:
- May hit Gemini API rate limits with 30 concurrent players
- Consider reducing `NUM_PLAYERS` to 10-15 for initial testing
- Check Railway memory limits

## Configuration

Edit `stress_test.py` to adjust:
- `NUM_PLAYERS = 30` - Number of bots
- `PROMPTS_PER_PLAYER_MIN = 5` - Minimum prompts per bot
- `PROMPTS_PER_PLAYER_MAX = 15` - Maximum prompts per bot
- `ROUND_DURATION = 300` - Round duration in seconds (5 minutes)


