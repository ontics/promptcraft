# User story: Lobby seat number (required for players) and admin dashboard display, sorting, and sticky controls

---

**Area** (where in the app this lives — pick one or list screens):  
- [x] Lobby  
- [ ] Onboarding  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [ ] Voting screen  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Post Survey  
- [x] Admin / gamemaster  
- [ ] Other: _______________

**What to do** (one or two sentences in plain language):  
> In the lobby, before non-admin players join the game, add an open text field labeled **Seat Number** next to **Join Game**. The field must accept **numeric input only** and cannot be empty when a player attempts to join; admins may join without filling it. The entered seat number should be stored with the player and shown **next to the player’s name on the admin dashboard only** (not in the lobby player list). On the admin dashboard, provide controls to **sort or filter** the visible player list by **seat number**, by **treatment group**, and by **points earned in round 10**. The **top section** of the admin dashboard that shows these values and filter/sort controls should remain **visible at all times** while scrolling the player list (sticky header / pinned toolbar behavior).

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] Lobby shows **Seat Number** beside **Join Game**; input is restricted to numbers; **Join** is blocked for non-admins if the field is empty; admins can join with the field empty.  
- [ ] Each joined **non-admin** player’s seat number appears next to their name on the **admin dashboard** only; the lobby does not display seat numbers next to names.  
- [ ] Admin can **reorder or filter** the player list by **seat number**, **treatment group**, and **round-10 earned points**; while scrolling, the **top dashboard area** that shows these controls (and any summary values) **stays visible** (sticky/pinned) so filters remain accessible.

**Do not change** (optional — what to leave alone):  
> Do not change core game flow, scoring rules, or treatment assignment logic except as needed to **read** treatment group for filtering/sorting. Do not show seat numbers in non-admin UI beyond the lobby input field. Preserve existing admin capabilities unless this story explicitly requires an update.

**Depends on** (optional — other stories or data that must exist first):  
> Assumes treatment group is already available in player state or admin payloads. Assumes round-10 earned points are available to the admin dashboard (or will be wired consistently with existing round-10 points display).

**Files likely involved** (optional — helps the AI and you focus):  
> `templates/index.html` (lobby join row: seat field + labels), `static/js/game.js` (validation, join payload, admin list rendering, sort/filter UI, sticky header CSS hooks), `static/css/style.css` (sticky admin toolbar / scroll container), `app.py` (accept and validate seat number on join; store on player; include in admin status payloads; enforce admin bypass).

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
