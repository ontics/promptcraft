import socketio
import asyncio
import random
import time
import sys
import threading
from datetime import datetime

# Configuration
SERVER_URL = "https://promptcraft.up.railway.app"  # Change if needed
NUM_PLAYERS = 30
PROMPTS_PER_PLAYER_MIN = 5
PROMPTS_PER_PLAYER_MAX = 15
ROUND_DURATION = 300  # 5 minutes in seconds

class SimulatedPlayer:
    def __init__(self, player_id, server_url):
        self.player_id = player_id
        self.name = f"Bot{player_id}"
        self.sio = socketio.Client()
        self.server_url = server_url
        self.connected = False
        self.joined = False
        self.game_started = False
        self.current_round = 0
        self.prompts_sent = 0
        self.images_received = 0
        self.errors = []
        self.round_start_time = None
        self.prompt_thread = None
        self.round_prompts_sent = {}  # Track prompts per round
        
        # Setup event handlers
        self.sio.on('connect', self.on_connect)
        self.sio.on('disconnect', self.on_disconnect)
        self.sio.on('game_joined', self.on_game_joined)
        self.sio.on('game_started', self.on_game_started)
        self.sio.on('round_results', self.on_round_results)
        self.sio.on('game_over', self.on_game_over)
        self.sio.on('image_generated', self.on_image_generated)
        self.sio.on('error', self.on_error)
        self.sio.on('prompt_sent', self.on_prompt_sent)
    
    def connect(self):
        try:
            self.sio.connect(self.server_url)
            self.connected = True
            print(f"[{self.name}] Connected")
        except Exception as e:
            print(f"[{self.name}] Connection failed: {e}")
            self.errors.append(f"Connection: {e}")
    
    def disconnect(self):
        if self.connected:
            self.sio.disconnect()
            self.connected = False
    
    def on_connect(self):
        print(f"[{self.name}] Socket connected")
        # Join game immediately
        self.sio.emit('join_game', {'name': self.name})
    
    def on_disconnect(self):
        print(f"[{self.name}] Disconnected - attempting to reconnect...")
        self.connected = False
        # Attempt to reconnect
        try:
            time.sleep(2)  # Wait a bit before reconnecting
            self.sio.connect(self.server_url)
            self.connected = True
            # Rejoin the game
            self.sio.emit('join_game', {'name': self.name})
            print(f"[{self.name}] Reconnected and rejoined game")
        except Exception as e:
            print(f"[{self.name}] Reconnection failed: {e}")
            self.errors.append(f"Reconnection: {e}")
    
    def on_game_joined(self, data):
        self.joined = True
        print(f"[{self.name}] Joined game successfully")
    
    def on_game_started(self, data):
        round_num = data.get('round', 1)
        end_time = data.get('end_time', 0)
        
        # If this is a new round, reset and start sending prompts
        if round_num != self.current_round:
            self.current_round = round_num
            self.game_started = True
            self.round_start_time = time.time()
            
            # Stop any existing prompt thread
            if self.prompt_thread and self.prompt_thread.is_alive():
                # Can't stop thread directly, but it will check game_started flag
                pass
            
            print(f"[{self.name}] Round {round_num} started, will send prompts over 5 minutes")
            # Start sending prompts in a background thread
            self.prompt_thread = threading.Thread(target=self.send_prompts_over_time, daemon=True)
            self.prompt_thread.start()
    
    def on_round_results(self, data):
        round_num = data.get('round', 0)
        print(f"[{self.name}] Round {round_num} results received, waiting for next round...")
        # Don't reset game_started - we'll wait for the next game_started event
    
    def on_game_over(self, data):
        print(f"[{self.name}] Game over! Final results received.")
        self.game_started = False
    
    def on_image_generated(self, data):
        self.images_received += 1
        if self.images_received % 5 == 0:
            print(f"[{self.name}] Received {self.images_received} images")
    
    def on_error(self, data):
        error_msg = data.get('message', 'Unknown error')
        self.errors.append(error_msg)
        print(f"[{self.name}] Error: {error_msg}")
    
    def on_prompt_sent(self, data):
        pass  # Prompt was accepted
    
    def send_prompts_over_time(self):
        """Send prompts randomly distributed over the 5-minute round duration"""
        round_num = self.current_round
        num_prompts = random.randint(PROMPTS_PER_PLAYER_MIN, PROMPTS_PER_PLAYER_MAX)
        print(f"[{self.name}] Round {round_num}: Will send {num_prompts} prompts over 5 minutes")
        
        if num_prompts == 0:
            return
        
        # Track prompts for this round
        self.round_prompts_sent[round_num] = 0
        
        # Calculate time intervals to distribute prompts evenly over 5 minutes
        # Add some randomness so they don't all send at the same times
        total_time = ROUND_DURATION - 10  # Leave 10 seconds buffer at the end
        intervals = []
        
        # Generate random intervals that sum to approximately total_time
        remaining_time = total_time
        for i in range(num_prompts - 1):
            # Random interval between prompts (minimum 5 seconds, maximum based on remaining time)
            max_interval = min(remaining_time / (num_prompts - i), 60)  # Cap at 60 seconds
            min_interval = max(5, remaining_time / (num_prompts - i) * 0.3)  # At least 30% of average
            interval = random.uniform(min_interval, max_interval)
            intervals.append(interval)
            remaining_time -= interval
        
        # Add a small random delay before first prompt (0-30 seconds)
        initial_delay = random.uniform(0, 30)
        time.sleep(initial_delay)
        
        # Send prompts at calculated intervals
        for i in range(num_prompts):
            if not self.connected or not self.game_started:
                break
            
            # Check if round has ended (with buffer)
            if self.round_start_time and (time.time() - self.round_start_time) > (ROUND_DURATION - 5):
                print(f"[{self.name}] Round ending soon, stopping prompts")
                break
            
            # Generate a random prompt
            prompt = self.generate_random_prompt()
            
            try:
                # Check connection before sending
                if not self.connected or not self.sio.connected:
                    print(f"[{self.name}] Not connected, attempting to reconnect...")
                    try:
                        self.sio.connect(self.server_url)
                        self.connected = True
                        self.sio.emit('join_game', {'name': self.name})
                        time.sleep(1)  # Wait for rejoin
                    except:
                        print(f"[{self.name}] Reconnection failed, skipping prompt")
                        break
                
                self.sio.emit('send_prompt', {'prompt': prompt})
                self.prompts_sent += 1
                self.round_prompts_sent[round_num] += 1
                print(f"[{self.name}] Round {round_num}: Sent prompt {self.round_prompts_sent[round_num]}/{num_prompts}: {prompt[:50]}...")
            except Exception as e:
                self.errors.append(f"Round {round_num}, prompt {i+1}: {e}")
                print(f"[{self.name}] Failed to send prompt: {e}")
                # Try to reconnect if connection lost
                if not self.connected:
                    try:
                        self.sio.connect(self.server_url)
                        self.connected = True
                        self.sio.emit('join_game', {'name': self.name})
                    except:
                        pass
            
            # Wait for next interval (except after last prompt)
            if i < num_prompts - 1:
                wait_time = intervals[i] if i < len(intervals) else 10
                time.sleep(wait_time)
        
        print(f"[{self.name}] Round {round_num} finished. Sent {self.round_prompts_sent.get(round_num, 0)}/{num_prompts} prompts. Total prompts: {self.prompts_sent}")
    
    def generate_random_prompt(self):
        """Generate a random prompt for testing"""
        subjects = ['a cat', 'a dog', 'a tree', 'a house', 'a car', 'a mountain', 'a beach', 
                    'a city', 'a flower', 'a bird', 'a sunset', 'a forest', 'a river', 
                    'a bridge', 'a castle', 'a spaceship', 'a robot', 'a dragon']
        styles = ['watercolor', 'digital art', 'photography', 'sketch', '3D render', 
                 'oil painting', 'pencil drawing', 'anime style', 'realistic', 'abstract']
        actions = ['in the style of', 'with', 'featuring', 'showing', 'depicting', 
                  'illustrating', 'rendered as', 'painted in']
        
        subject = random.choice(subjects)
        action = random.choice(actions)
        style = random.choice(styles)
        
        return f"{subject.capitalize()} {action} {style}"

async def run_stress_test():
    print("="*70)
    print("PROMPTCRAFT STRESS TEST")
    print("="*70)
    print(f"Players: {NUM_PLAYERS}")
    print(f"Prompts per player: {PROMPTS_PER_PLAYER_MIN}-{PROMPTS_PER_PLAYER_MAX}")
    print(f"Round duration: {ROUND_DURATION} seconds (5 minutes)")
    print(f"Server: {SERVER_URL}")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    print()
    
    players = []
    
    # Create and connect all players
    print("Connecting players...")
    for i in range(NUM_PLAYERS):
        player = SimulatedPlayer(i + 1, SERVER_URL)
        player.connect()
        players.append(player)
        # Stagger connections slightly to avoid overwhelming the server
        await asyncio.sleep(0.2)
    
    print(f"\n✅ All {NUM_PLAYERS} players connected and joined.")
    print("\n📋 NEXT STEPS:")
    print("   1. Go to the game admin dashboard")
    print("   2. Assign teams (or use auto-assign)")
    print("   3. Start the game")
    print("   4. Players will automatically start sending prompts over 5 minutes")
    print("\n⏳ Waiting for game to start...\n")
    
    # Wait for all players to join
    await asyncio.sleep(2)
    
    # Check if all players joined
    joined_count = sum(1 for p in players if p.joined)
    print(f"Players joined: {joined_count}/{NUM_PLAYERS}")
    
    # Wait for game to start and complete (with timeout)
    start_wait_time = time.time()
    max_wait_time = 600  # 10 minutes max wait for game start
    
    while time.time() - start_wait_time < max_wait_time:
        games_started = sum(1 for p in players if p.game_started)
        if games_started > 0:
            print(f"\n🎮 Game started! {games_started} players received game_started event")
            break
        await asyncio.sleep(1)
    
    if games_started == 0:
        print("\n⚠️  WARNING: Game did not start within 10 minutes. Ending test.")
        for player in players:
            player.disconnect()
        return
    
    # Wait for all 3 rounds to complete
    print(f"\n⏳ Waiting for all 3 rounds to complete...")
    print("   (Each round is 5 minutes + selection/voting phases)")
    
    # Wait for round 1 (5 min + buffer for selection/voting)
    await asyncio.sleep(ROUND_DURATION + 60)
    print(f"\n✅ Round 1 should be complete, waiting for round 2...")
    
    # Wait for round 2
    await asyncio.sleep(ROUND_DURATION + 60)
    print(f"\n✅ Round 2 should be complete, waiting for round 3...")
    
    # Wait for round 3
    await asyncio.sleep(ROUND_DURATION + 60)
    print(f"\n✅ Round 3 should be complete, collecting results...")
    
    # Give a bit more time for final results
    await asyncio.sleep(30)
    
    # Collect statistics
    print("\n" + "="*70)
    print("STRESS TEST RESULTS")
    print("="*70)
    
    total_prompts = sum(p.prompts_sent for p in players)
    total_images = sum(p.images_received for p in players)
    total_errors = sum(len(p.errors) for p in players)
    players_with_errors = sum(1 for p in players if p.errors)
    players_started = sum(1 for p in players if p.current_round > 0)
    
    # Count prompts per round
    round_stats = {}
    for player in players:
        for round_num, count in player.round_prompts_sent.items():
            if round_num not in round_stats:
                round_stats[round_num] = 0
            round_stats[round_num] += count
    
    print(f"Total Players: {NUM_PLAYERS}")
    print(f"Players Joined: {sum(1 for p in players if p.joined)}")
    print(f"Players Started (at least 1 round): {players_started}")
    print(f"Total Prompts Sent: {total_prompts}")
    print(f"Total Images Received: {total_images}")
    print(f"Total Errors: {total_errors}")
    print(f"Players with Errors: {players_with_errors}")
    
    if round_stats:
        print(f"\n📊 Prompts per Round:")
        for round_num in sorted(round_stats.keys()):
            print(f"   Round {round_num}: {round_stats[round_num]} prompts")
    
    if players_started > 0:
        print(f"\nAverage Prompts per Player: {total_prompts / players_started:.1f}")
        print(f"Average Images per Player: {total_images / players_started:.1f}")
        print(f"Success Rate: {(total_images / total_prompts * 100) if total_prompts > 0 else 0:.1f}%")
    
    if total_errors > 0:
        print(f"\n⚠️  Errors occurred:")
        error_summary = {}
        for player in players:
            for error in player.errors:
                error_summary[error] = error_summary.get(error, 0) + 1
        
        for error, count in list(error_summary.items())[:10]:  # Show top 10 errors
            print(f"   {error}: {count} occurrences")
    
    # Show per-player summary (first 10 players)
    print(f"\n📊 Per-Player Summary (first 10):")
    for player in players[:10]:
        status = "✅" if player.game_started and player.prompts_sent > 0 else "⚠️"
        print(f"   {status} {player.name}: {player.prompts_sent} prompts, {player.images_received} images, {len(player.errors)} errors")
    
    # Disconnect all players
    print("\n🔌 Disconnecting players...")
    for player in players:
        player.disconnect()
    
    print(f"\n✅ Stress test complete! End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        SERVER_URL = sys.argv[1]
        print(f"Using custom server URL: {SERVER_URL}")
    
    try:
        asyncio.run(run_stress_test())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)




import random
import time
import sys
import threading
from datetime import datetime

# Configuration
SERVER_URL = "https://promptcraft.up.railway.app"  # Change if needed
NUM_PLAYERS = 30
PROMPTS_PER_PLAYER_MIN = 5
PROMPTS_PER_PLAYER_MAX = 15
ROUND_DURATION = 300  # 5 minutes in seconds

class SimulatedPlayer:
    def __init__(self, player_id, server_url):
        self.player_id = player_id
        self.name = f"Bot{player_id}"
        self.sio = socketio.Client()
        self.server_url = server_url
        self.connected = False
        self.joined = False
        self.game_started = False
        self.current_round = 0
        self.prompts_sent = 0
        self.images_received = 0
        self.errors = []
        self.round_start_time = None
        self.prompt_thread = None
        self.round_prompts_sent = {}  # Track prompts per round
        
        # Setup event handlers
        self.sio.on('connect', self.on_connect)
        self.sio.on('disconnect', self.on_disconnect)
        self.sio.on('game_joined', self.on_game_joined)
        self.sio.on('game_started', self.on_game_started)
        self.sio.on('round_results', self.on_round_results)
        self.sio.on('game_over', self.on_game_over)
        self.sio.on('image_generated', self.on_image_generated)
        self.sio.on('error', self.on_error)
        self.sio.on('prompt_sent', self.on_prompt_sent)
    
    def connect(self):
        try:
            self.sio.connect(self.server_url)
            self.connected = True
            print(f"[{self.name}] Connected")
        except Exception as e:
            print(f"[{self.name}] Connection failed: {e}")
            self.errors.append(f"Connection: {e}")
    
    def disconnect(self):
        if self.connected:
            self.sio.disconnect()
            self.connected = False
    
    def on_connect(self):
        print(f"[{self.name}] Socket connected")
        # Join game immediately
        self.sio.emit('join_game', {'name': self.name})
    
    def on_disconnect(self):
        print(f"[{self.name}] Disconnected - attempting to reconnect...")
        self.connected = False
        # Attempt to reconnect
        try:
            time.sleep(2)  # Wait a bit before reconnecting
            self.sio.connect(self.server_url)
            self.connected = True
            # Rejoin the game
            self.sio.emit('join_game', {'name': self.name})
            print(f"[{self.name}] Reconnected and rejoined game")
        except Exception as e:
            print(f"[{self.name}] Reconnection failed: {e}")
            self.errors.append(f"Reconnection: {e}")
    
    def on_game_joined(self, data):
        self.joined = True
        print(f"[{self.name}] Joined game successfully")
    
    def on_game_started(self, data):
        round_num = data.get('round', 1)
        end_time = data.get('end_time', 0)
        
        # If this is a new round, reset and start sending prompts
        if round_num != self.current_round:
            self.current_round = round_num
            self.game_started = True
            self.round_start_time = time.time()
            
            # Stop any existing prompt thread
            if self.prompt_thread and self.prompt_thread.is_alive():
                # Can't stop thread directly, but it will check game_started flag
                pass
            
            print(f"[{self.name}] Round {round_num} started, will send prompts over 5 minutes")
            # Start sending prompts in a background thread
            self.prompt_thread = threading.Thread(target=self.send_prompts_over_time, daemon=True)
            self.prompt_thread.start()
    
    def on_round_results(self, data):
        round_num = data.get('round', 0)
        print(f"[{self.name}] Round {round_num} results received, waiting for next round...")
        # Don't reset game_started - we'll wait for the next game_started event
    
    def on_game_over(self, data):
        print(f"[{self.name}] Game over! Final results received.")
        self.game_started = False
    
    def on_image_generated(self, data):
        self.images_received += 1
        if self.images_received % 5 == 0:
            print(f"[{self.name}] Received {self.images_received} images")
    
    def on_error(self, data):
        error_msg = data.get('message', 'Unknown error')
        self.errors.append(error_msg)
        print(f"[{self.name}] Error: {error_msg}")
    
    def on_prompt_sent(self, data):
        pass  # Prompt was accepted
    
    def send_prompts_over_time(self):
        """Send prompts randomly distributed over the 5-minute round duration"""
        round_num = self.current_round
        num_prompts = random.randint(PROMPTS_PER_PLAYER_MIN, PROMPTS_PER_PLAYER_MAX)
        print(f"[{self.name}] Round {round_num}: Will send {num_prompts} prompts over 5 minutes")
        
        if num_prompts == 0:
            return
        
        # Track prompts for this round
        self.round_prompts_sent[round_num] = 0
        
        # Calculate time intervals to distribute prompts evenly over 5 minutes
        # Add some randomness so they don't all send at the same times
        total_time = ROUND_DURATION - 10  # Leave 10 seconds buffer at the end
        intervals = []
        
        # Generate random intervals that sum to approximately total_time
        remaining_time = total_time
        for i in range(num_prompts - 1):
            # Random interval between prompts (minimum 5 seconds, maximum based on remaining time)
            max_interval = min(remaining_time / (num_prompts - i), 60)  # Cap at 60 seconds
            min_interval = max(5, remaining_time / (num_prompts - i) * 0.3)  # At least 30% of average
            interval = random.uniform(min_interval, max_interval)
            intervals.append(interval)
            remaining_time -= interval
        
        # Add a small random delay before first prompt (0-30 seconds)
        initial_delay = random.uniform(0, 30)
        time.sleep(initial_delay)
        
        # Send prompts at calculated intervals
        for i in range(num_prompts):
            if not self.connected or not self.game_started:
                break
            
            # Check if round has ended (with buffer)
            if self.round_start_time and (time.time() - self.round_start_time) > (ROUND_DURATION - 5):
                print(f"[{self.name}] Round ending soon, stopping prompts")
                break
            
            # Generate a random prompt
            prompt = self.generate_random_prompt()
            
            try:
                # Check connection before sending
                if not self.connected or not self.sio.connected:
                    print(f"[{self.name}] Not connected, attempting to reconnect...")
                    try:
                        self.sio.connect(self.server_url)
                        self.connected = True
                        self.sio.emit('join_game', {'name': self.name})
                        time.sleep(1)  # Wait for rejoin
                    except:
                        print(f"[{self.name}] Reconnection failed, skipping prompt")
                        break
                
                self.sio.emit('send_prompt', {'prompt': prompt})
                self.prompts_sent += 1
                self.round_prompts_sent[round_num] += 1
                print(f"[{self.name}] Round {round_num}: Sent prompt {self.round_prompts_sent[round_num]}/{num_prompts}: {prompt[:50]}...")
            except Exception as e:
                self.errors.append(f"Round {round_num}, prompt {i+1}: {e}")
                print(f"[{self.name}] Failed to send prompt: {e}")
                # Try to reconnect if connection lost
                if not self.connected:
                    try:
                        self.sio.connect(self.server_url)
                        self.connected = True
                        self.sio.emit('join_game', {'name': self.name})
                    except:
                        pass
            
            # Wait for next interval (except after last prompt)
            if i < num_prompts - 1:
                wait_time = intervals[i] if i < len(intervals) else 10
                time.sleep(wait_time)
        
        print(f"[{self.name}] Round {round_num} finished. Sent {self.round_prompts_sent.get(round_num, 0)}/{num_prompts} prompts. Total prompts: {self.prompts_sent}")
    
    def generate_random_prompt(self):
        """Generate a random prompt for testing"""
        subjects = ['a cat', 'a dog', 'a tree', 'a house', 'a car', 'a mountain', 'a beach', 
                    'a city', 'a flower', 'a bird', 'a sunset', 'a forest', 'a river', 
                    'a bridge', 'a castle', 'a spaceship', 'a robot', 'a dragon']
        styles = ['watercolor', 'digital art', 'photography', 'sketch', '3D render', 
                 'oil painting', 'pencil drawing', 'anime style', 'realistic', 'abstract']
        actions = ['in the style of', 'with', 'featuring', 'showing', 'depicting', 
                  'illustrating', 'rendered as', 'painted in']
        
        subject = random.choice(subjects)
        action = random.choice(actions)
        style = random.choice(styles)
        
        return f"{subject.capitalize()} {action} {style}"

async def run_stress_test():
    print("="*70)
    print("PROMPTCRAFT STRESS TEST")
    print("="*70)
    print(f"Players: {NUM_PLAYERS}")
    print(f"Prompts per player: {PROMPTS_PER_PLAYER_MIN}-{PROMPTS_PER_PLAYER_MAX}")
    print(f"Round duration: {ROUND_DURATION} seconds (5 minutes)")
    print(f"Server: {SERVER_URL}")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    print()
    
    players = []
    
    # Create and connect all players
    print("Connecting players...")
    for i in range(NUM_PLAYERS):
        player = SimulatedPlayer(i + 1, SERVER_URL)
        player.connect()
        players.append(player)
        # Stagger connections slightly to avoid overwhelming the server
        await asyncio.sleep(0.2)
    
    print(f"\n✅ All {NUM_PLAYERS} players connected and joined.")
    print("\n📋 NEXT STEPS:")
    print("   1. Go to the game admin dashboard")
    print("   2. Assign teams (or use auto-assign)")
    print("   3. Start the game")
    print("   4. Players will automatically start sending prompts over 5 minutes")
    print("\n⏳ Waiting for game to start...\n")
    
    # Wait for all players to join
    await asyncio.sleep(2)
    
    # Check if all players joined
    joined_count = sum(1 for p in players if p.joined)
    print(f"Players joined: {joined_count}/{NUM_PLAYERS}")
    
    # Wait for game to start and complete (with timeout)
    start_wait_time = time.time()
    max_wait_time = 600  # 10 minutes max wait for game start
    
    while time.time() - start_wait_time < max_wait_time:
        games_started = sum(1 for p in players if p.game_started)
        if games_started > 0:
            print(f"\n🎮 Game started! {games_started} players received game_started event")
            break
        await asyncio.sleep(1)
    
    if games_started == 0:
        print("\n⚠️  WARNING: Game did not start within 10 minutes. Ending test.")
        for player in players:
            player.disconnect()
        return
    
    # Wait for all 3 rounds to complete
    print(f"\n⏳ Waiting for all 3 rounds to complete...")
    print("   (Each round is 5 minutes + selection/voting phases)")
    
    # Wait for round 1 (5 min + buffer for selection/voting)
    await asyncio.sleep(ROUND_DURATION + 60)
    print(f"\n✅ Round 1 should be complete, waiting for round 2...")
    
    # Wait for round 2
    await asyncio.sleep(ROUND_DURATION + 60)
    print(f"\n✅ Round 2 should be complete, waiting for round 3...")
    
    # Wait for round 3
    await asyncio.sleep(ROUND_DURATION + 60)
    print(f"\n✅ Round 3 should be complete, collecting results...")
    
    # Give a bit more time for final results
    await asyncio.sleep(30)
    
    # Collect statistics
    print("\n" + "="*70)
    print("STRESS TEST RESULTS")
    print("="*70)
    
    total_prompts = sum(p.prompts_sent for p in players)
    total_images = sum(p.images_received for p in players)
    total_errors = sum(len(p.errors) for p in players)
    players_with_errors = sum(1 for p in players if p.errors)
    players_started = sum(1 for p in players if p.current_round > 0)
    
    # Count prompts per round
    round_stats = {}
    for player in players:
        for round_num, count in player.round_prompts_sent.items():
            if round_num not in round_stats:
                round_stats[round_num] = 0
            round_stats[round_num] += count
    
    print(f"Total Players: {NUM_PLAYERS}")
    print(f"Players Joined: {sum(1 for p in players if p.joined)}")
    print(f"Players Started (at least 1 round): {players_started}")
    print(f"Total Prompts Sent: {total_prompts}")
    print(f"Total Images Received: {total_images}")
    print(f"Total Errors: {total_errors}")
    print(f"Players with Errors: {players_with_errors}")
    
    if round_stats:
        print(f"\n📊 Prompts per Round:")
        for round_num in sorted(round_stats.keys()):
            print(f"   Round {round_num}: {round_stats[round_num]} prompts")
    
    if players_started > 0:
        print(f"\nAverage Prompts per Player: {total_prompts / players_started:.1f}")
        print(f"Average Images per Player: {total_images / players_started:.1f}")
        print(f"Success Rate: {(total_images / total_prompts * 100) if total_prompts > 0 else 0:.1f}%")
    
    if total_errors > 0:
        print(f"\n⚠️  Errors occurred:")
        error_summary = {}
        for player in players:
            for error in player.errors:
                error_summary[error] = error_summary.get(error, 0) + 1
        
        for error, count in list(error_summary.items())[:10]:  # Show top 10 errors
            print(f"   {error}: {count} occurrences")
    
    # Show per-player summary (first 10 players)
    print(f"\n📊 Per-Player Summary (first 10):")
    for player in players[:10]:
        status = "✅" if player.game_started and player.prompts_sent > 0 else "⚠️"
        print(f"   {status} {player.name}: {player.prompts_sent} prompts, {player.images_received} images, {len(player.errors)} errors")
    
    # Disconnect all players
    print("\n🔌 Disconnecting players...")
    for player in players:
        player.disconnect()
    
    print(f"\n✅ Stress test complete! End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        SERVER_URL = sys.argv[1]
        print(f"Using custom server URL: {SERVER_URL}")
    
    try:
        asyncio.run(run_stress_test())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)



