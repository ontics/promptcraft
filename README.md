# PromptCraft - AI Image Generation Game

PromptCraft is a real-time multiplayer web game where players compete to generate AI images that match target images. Players are assigned to teams and compete over 3 rounds to create the best matching images.

## Features

- 🎮 Real-time multiplayer (up to 40 players)
- 🤖 AI image generation using Google Gemini API
- ⏱️ 3 rounds of 5 minutes each
- 🎯 Target-based image matching challenges
- 🗳️ Player voting system
- 🏆 Leaderboard and scoring
- 📱 Responsive design for desktop and mobile

## Requirements

- Python 3.8+
- Google Gemini API key
- Supabase account (for database and image storage)

## Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd promptcraft
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   Create a `.env` file in the project root with the following:
   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   SUPABASE_URL=your_supabase_project_url
   SUPABASE_KEY=your_supabase_anon_key
   ADMIN_CODE=your_secret_admin_code
   ```

   Get your Gemini API key from: https://makersuite.google.com/app/apikey
   
   For Supabase setup, create a project at https://supabase.com and get your project URL and anon key from the project settings.

## Running the Game

1. **Start the server:**
   ```bash
   python app.py
   ```

2. **Access the game:**
   - On the host machine: http://localhost:8000
   - On other devices in your local network: http://YOUR_IP_ADDRESS:8000

3. **Find your local IP address:**
   - macOS/Linux: `ifconfig | grep inet`
   - Windows: `ipconfig`
   - Look for an address like `192.168.x.x`

## How to Play

### Pre-Game
1. Enter your name and join the lobby
2. Wait for other players to join
3. The gamemaster starts the game when ready

### During Rounds (5 minutes each)
1. View the target image
2. Chat with the AI to generate images matching the target
3. The AI remembers context from your conversation
4. Create multiple images to find the best match
5. Your character provides feedback during gameplay

### End of Round
1. Select your best image (30 seconds)
2. Vote on other players' images
3. Earn points based on votes received
4. View round results and leaderboard

### Game End
- After 3 rounds, view final rankings
- Option to return to lobby

## Game Mechanics

### Teams
- Players are randomly assigned to Team A or Team B
- Teams compete together, but scoring is individual

### Scoring
- Players vote on images they think best match the target
- Points are awarded based on votes received
- Total score across 3 rounds determines the winner

### AI Integration
- Uses Google Gemini API for image generation
- Maintains conversation context within each round
- Provides feedback and responds to prompts

## Deployment

### Railway Deployment
The project includes a `Procfile` for easy deployment to Railway:

1. Connect your GitHub repository to Railway
2. Set environment variables in Railway dashboard:
   - `GEMINI_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `ADMIN_CODE`
   - `PORT` (Railway will set this automatically)
3. Railway will automatically deploy from your repository

## Technical Details

### Backend
- **Framework**: Flask with Flask-SocketIO
- **Real-time**: WebSocket connections via Socket.IO
- **Database**: Supabase (PostgreSQL)
- **Storage**: Supabase Storage for generated images
- **AI**: Google Gemini API (gemini-2.0-flash-exp model)

### Frontend
- **Template Engine**: Jinja2 (Flask templates)
- **Real-time Updates**: Socket.IO client
- **Styling**: Custom CSS with responsive design
- **No Build Process**: Direct HTML/CSS/JS served by Flask

## Troubleshooting

### Cannot connect from other devices
- Ensure all devices are on the same network
- Check firewall settings on the host machine
- Verify you're using the correct IP address

### API rate limiting
- Gemini API has a limit of 1,000 requests/minute
- With many players, space out prompt submissions
- The game includes basic error handling for API failures

### Images not generating
- Verify your `GEMINI_API_KEY` is correctly set in `.env`
- Check internet connection
- Review console logs for API errors

### Database connection issues
- Verify your `SUPABASE_URL` and `SUPABASE_KEY` are correct
- Ensure your Supabase project is active
- Check that the Storage bucket `generated-images` exists

## Project Structure

```
promptcraft/
├── app.py                 # Main Flask application
├── db.py                  # Database helper module
├── requirements.txt       # Python dependencies
├── Procfile              # Railway deployment configuration
├── .env                  # Environment variables (not in git)
├── static/
│   ├── css/
│   │   └── style.css     # Game styling
│   ├── js/
│   │   └── game.js       # Client-side game logic
│   └── images/           # Game assets (avatars, target images)
└── templates/
    └── index.html        # Main game template
```

## License

MIT License - Feel free to modify and use for your own purposes.
