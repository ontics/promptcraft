# Playtest 2 Testing Checklist

This checklist helps verify that the issues from Playtest 1 are fixed. Test each scenario below and document whether it passes or fails.

## Issue 1: Error Images Being Selected

**Original Problem**: Error images (blank placeholders) were being selected and submitted, forcing other players to vote on blank images.

### Test Scenario 1.1: Manual Selection of Error Image
1. Start a game with at least 2 players
2. Have a player submit prompts until they get an error image (blank placeholder)
3. Try to manually select the error image on the selection screen
4. **Expected**: Selection should be rejected with an error message, and the UI should automatically select the last valid image instead
5. **Check**: Look for server log message: `❌ ERROR: Player X attempted to select error image`

### Test Scenario 1.2: Auto-Selection with Only Error Images
1. Start a game with at least 2 players
2. Have a player submit prompts until they ONLY have error images (all prompts fail)
3. Wait for the selection timer to expire
4. **Expected**: Server should log an error: `❌ ERROR: Player X has no valid images to auto-select`, and the game should NOT progress (admin can handle manually)
5. **Check**: Game should be stuck at selection screen, not advance to voting

---

## Issue 2: Player Reconnection Data Loss

**Original Problem**: Players who reconnected in Rounds 2/3 didn't have their images restored, and their data wasn't saved to the database.

### Test Scenario 2.1: Reconnection During Playing Phase
1. Start a game with at least 2 players
2. Have Player A submit several prompts and generate images in Round 1
3. Have Player A refresh their browser (simulating disconnection/reconnection)
4. **Expected**: 
   - Player A should see all their previously generated images restored
   - Server should log: `[RECONNECT] Restored X images for player A in round 1 (status: playing)`
   - Player A should be able to continue submitting prompts
5. **Check**: Verify images appear in the conversation area and selection gallery

### Test Scenario 2.2: Reconnection During Selection Phase
1. Start a game with at least 2 players
2. Have Player A generate images in Round 1
3. Wait for selection screen to appear
4. Have Player A refresh their browser
5. **Expected**:
   - Player A should see the selection screen with all their images restored
   - Server should log: `[RECONNECT] Restored X images for player A in round 1 (status: voting)`
   - Player A should be able to select an image
6. **Check**: Verify images appear in selection gallery, and selection works

### Test Scenario 2.3: Reconnection Data Persistence
1. Start a game with at least 2 players
2. Have Player A generate images and select one in Round 1
3. Have Player A refresh and rejoin
4. Complete Round 1 and start Round 2
5. Have Player A generate images in Round 2
6. **Expected**: 
   - Player A's Round 1 selection should be saved to database
   - Player A's Round 2 images should be saved to database
   - Check Supabase to verify data exists for both rounds
7. **Check**: Query Supabase `image_selections` and `prompts` tables for Player A's data

---

## Issue 3: Admin Disconnection

**Original Problem**: Admin disconnected during the game and was unable to use admin controls.

### Test Scenario 3.1: Admin Disconnection and Reconnection
1. Start a game as admin
2. Have at least 2 players join and start playing
3. Refresh the admin's browser (simulating disconnection)
4. Rejoin as admin using the admin code
5. **Expected**:
   - Admin should regain admin status
   - Server should log: `Admin X disconnected, transferring admin to Y` or `Player Y reconnected as ADMIN`
   - Admin dashboard should be visible and functional
6. **Check**: Admin should be able to use all controls (skip selection, skip voting, next round, etc.)

### Test Scenario 3.2: Admin Takeover
1. Start a game as Admin A
2. Have Admin A disconnect (close browser)
3. Have a new player join with the admin code
4. **Expected**:
   - New player should become admin
   - Server should log: `Admin X disconnected, new admin Y taking over`
   - Old admin's `is_admin` status should be set to False
6. **Check**: New admin should have full control, old admin (if they rejoin) should not be admin

---

## Issue 4: Voting Completion Edge Case

**Original Problem**: One player's vote was skipped before they confirmed it, causing the game to progress prematurely.

### Test Scenario 4.1: Disconnection During Voting
1. Start a game with 3+ players
2. Complete Round 1 selection phase
3. When voting screen appears, have Player A start voting but DON'T confirm yet
4. Have Player B disconnect (refresh browser)
5. Have Player C vote and confirm
6. **Expected**:
   - Server should track players active at voting start: `[VOTING] Tracked X active players at voting start`
   - Game should NOT progress until Player A confirms their vote
   - Server should log: `[VOTING] Progress: 1/X players have voted (from voting start list)`
7. **Check**: Game should wait for Player A's vote, not skip it

### Test Scenario 4.2: All Players Vote
1. Start a game with 3+ players
2. Complete selection phase
3. Have all players vote and confirm
4. **Expected**:
   - Server should log: `[VOTING] Progress: X/X players have voted`
   - Server should log: `[VOTING] All X players have voted, showing results`
   - Round results should appear
5. **Check**: Results should show immediately after all votes are cast

---

## Issue 5: Database Save Failures

**Original Problem**: Selections with `prompt_id: None` failed to save, with only a warning printed.

### Test Scenario 5.1: Valid Image Selection Save
1. Start a game with at least 2 players
2. Have Player A generate a valid image (not an error)
3. Have Player A select and confirm the image
4. **Expected**:
   - Server should log: `✅ Saved image selection for player A in round 1, prompt_id=XXX`
   - Database should have an entry in `image_selections` table
5. **Check**: Query Supabase `image_selections` table for Player A's selection

### Test Scenario 5.2: Error Image Selection Attempt
1. Start a game with at least 2 players
2. Have Player A generate an error image
3. Try to select the error image (should be rejected)
4. **Expected**:
   - Server should log: `❌ ERROR: Player A attempted to select error image`
   - No database save should be attempted
   - Client should show error message
5. **Check**: No entry should be created in `image_selections` for the error image

---

## Issue 6: Auto-Selection Fallback

**Original Problem**: Auto-selection had a fallback that would select error images if no valid images existed.

### Test Scenario 6.1: Auto-Selection with Valid Images
1. Start a game with at least 2 players
2. Have Player A generate multiple valid images
3. Wait for selection timer to expire without Player A selecting
4. **Expected**:
   - Server should auto-select the last valid image (with prompt_id)
   - Server should log: `[SELECTION] Auto-selected valid image (prompt_id=XXX) for player A`
   - Database should have an entry for the auto-selected image
5. **Check**: Verify selection is saved to database

### Test Scenario 6.2: Auto-Selection with Only Error Images
1. Start a game with at least 2 players
2. Have Player A generate ONLY error images (all prompts fail)
3. Wait for selection timer to expire
4. **Expected**:
   - Server should log: `❌ ERROR: Player A has no valid images to auto-select in round 1`
   - Game should NOT progress (stuck at selection screen)
   - Admin should be able to manually handle this
5. **Check**: Game should remain at selection screen, not advance

---

## General Testing Notes

### What to Monitor:
1. **Server Logs**: Watch for error messages, warnings, and the new logging statements
2. **Database**: Check Supabase after each round to verify data is being saved
3. **Client Behavior**: Watch for error messages, UI updates, and state restoration
4. **Network**: Monitor browser console for WebSocket errors or failed requests

### Red Flags (Indicates Issues Not Fixed):
- Error images appearing in selection gallery
- Players unable to see their images after reconnection
- Votes being skipped or game progressing prematurely
- Missing data in Supabase after rounds complete
- Admin controls not working after reconnection
- Game getting stuck without clear error messages

### Success Criteria:
- ✅ All error images are filtered out and cannot be selected
- ✅ Reconnected players see all their images restored
- ✅ All player data is saved to database for all rounds
- ✅ Admin can reconnect and regain control
- ✅ Voting waits for all players who were active at voting start
- ✅ Auto-selection never selects error images
- ✅ Database saves succeed for all valid selections

---

## Quick Test Sequence (30 minutes)

For a quick verification, run this sequence:

1. **Start game** with 3 players + admin
2. **Round 1**: 
   - Have Player A generate images (some valid, some errors)
   - Have Player B refresh during playing phase (test reconnection)
   - Wait for selection screen
   - Try to select an error image (should fail)
   - Have Player C refresh during selection (test reconnection)
   - Complete selection and voting
3. **Round 2**:
   - Have admin refresh (test admin reconnection)
   - Complete round normally
4. **Check Supabase**: Verify all data is saved for all players in all rounds

If all of the above works without errors, the fixes are likely successful!

