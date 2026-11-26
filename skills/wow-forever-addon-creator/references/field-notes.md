# Field notes — real cases, WoW Forever, November 2026

Each entry: date (2026) · symptom → evidence → cause → fix. They come from addons built with Claude Code and checked in the live client (Interface 16001). "Evidence" says how it was seen: in-game error, saved log, taint.log, screenshot, or an offline gate. Use them as patterns: when a symptom matches, start from the listed cause.

| # | Date | Symptom | Evidence | Cause | Fix |
|---|---|---|---|---|---|
| 1 | 7 Nov | `OverrideActionBarButton2Cooldown:SetCooldown` secret error on every skill | error popup, every cast | addon buttons inside Blizzard's shared action-button event list tainted the loop | remove own buttons from the lists, relay events, re-remove on `RegisterFrame` |
| 2 | 7 Nov | `SetCooldown` refuses secret values on an addon button | error on cooldown start | secret start/duration from addon code | `SetCooldownFromDurationObject` with the duration object |
| 3 | 7 Nov | `UseAction FORBIDDEN` after a "safe" refactor | errors on every click | a wrapper around `SetAttribute` on secure buttons | delete the wrapper; never wrap secure methods |
| 4 | 8 Nov | "Interface action failed because of an AddOn" in fights | saved log 00:20–00:26 | `ACTIONBAR_SLOT_CHANGED` → Blizzard `Update()` writes attributes in combat | icon-only update in combat, full update at `PLAYER_REGEN_ENABLED` |
| 5 | 8 Nov | 164 `ADDON_ACTION_BLOCKED` lines per session | lines follow the mouse path | hover → Blizzard `OnEnter` → attribute writes | guarded OnEnter path in combat → 0 lines |
| 6 | 8 Nov | `UseAction` forbidden on right-click | taint.log: "reading field action - ActionButton.lua:1404" | right-click reads addon-written `self.action` | register left clicks only |
| 7 | 7 Nov | every icon flashes the gold cast animation | screenshot | spellcast events relayed to all buttons | send only to the button whose spell matches |
| 8 | 7 Nov | Lua error `SetOffset` is nil | error on load | Lua-created `TextureCoordTranslation` has no `SetOffset` | XML `<FlipBook>` template |
| 9 | 8 Nov | green band and double level number on unit frame | screenshot | `SetVertexColor(r,g,b,a)` resets `SetAlpha(0)` | `hooksecurefunc` on both methods to keep alpha 0 |
| 10 | 8 Nov | cast bar closes when a second spell is spammed | in game | `UNIT_SPELLCAST_FAILED` of the second spell | end only if `UnitCastingInfo` shows nothing |
| 11 | 8 Nov | DoT timers blank in combat | probe log | auras secret while tainted | time own casts; learn durations out of combat |
| 12 | 13 Nov | bag window crashes, old bag stays open | error: `GetCoinTextureString` nil | removed global | `C_CurrencyInfo.GetCoinTextureString`; close Blizzard bag first |
| 13 | 13 Nov | using an item on an item from the addon bag is blocked | blocked message | protected action from addon button | secure overlay buttons placed out of combat, hidden on `PLAYER_REGEN_DISABLED` |
| 14 | 18 Nov | combat text has no spell icons in real fights | dummy test vs real fight | secret spell IDs dropped as "invalid" | pass the secret ID to `C_Spell.GetSpellTexture` → `SetTexture` |
| 15 | 18 Nov | "<Addon> has been blocked" popup, 0 damage events | in game, measured | registering `COMBAT_LOG_EVENT_UNFILTERED` | removed; `UNIT_COMBAT` instead, outgoing damage lane off by default |
| 16 | Nov | `Settings.SetValue` fails at login | error | setting not registered before `SETTINGS_LOADED` | move to that event |
| 17 | 11 Nov | Turkish letters render as boxes | screenshot | Friz Quadrata lacks ğ ş İ | Arial Narrow or a bundled OFL font |
| 18 | Nov | translation addon throws on a minimap tooltip | error | tooltip text arrives secret; `:find` on it | `issecretvalue` guard before string ops |
| 19 | 24 Nov | translated package: map and minimap icons invisible | 69 paths left pointing at the old folder | case-sensitive path rewrite (`Addons` vs `AddOns`) and an equally blind leftover check | case-insensitive rewrite and check; proven red on the broken zip |
| 20 | 10 Nov | new texture or Lua file not picked up | in game | `/reload` does not rescan files | full game restart |
| 21 | Nov | options slider shows 0.30000000000000004 | screenshot | floating point | round to two decimals |
| 22 | 17 Nov | rebuilt zip 91 bytes different | SHA mismatch | CRLF checkout | normalise to LF before packaging |
| 23 | 17 Nov | typo'd method `SetObeyStepsOnDrag` | caught by an offline API gate | invented method name | API gate against client source (`check_addon.py --ui-source`) |
| 24 | 24 Nov | ground "range rings" looked wrong | player's in-game verdict | no ground drawing or camera API; a calibrated screen ellipse breaks with camera pitch and slopes | say "not possible this way" up front; experimental projection via the waypoint navigation frame (`ui-construction.md`) |
| 25 | 24 Nov | an API gate called `GameTooltip:AddDoubleLine` missing | Blizzard's own Forever code calls it in dozens of files | gate only read the generated docs; C-side widget methods are not listed there | count Blizzard call sites as known names |
| 26 | 24 Nov | `CombatLogGetCurrentEventInfo` "exists" in the source but is nil in game | source: only in `Blizzard_DeprecatedCombatLog`; client: nil | deprecation shim not loaded | treat shim-only names as absent |
| 28 | 24 Nov | projection rings: drawn in perspective but above the ground and too large; minimap waypoint pin spinning | player's screenshots + report | navigation frame point sits above the ground (or waypoint height differs); re-placing the waypoint every frame moves the map/minimap pin | not shippable as is; projection mode made opt-in, flat mode default again |
| 29 | 24 Nov | range indicator showed "range ?" when the target was out of range | offline scenario (known distances) | `x = cond and r or nil` turns `r == false` into `nil` (Lua's and/or idiom) | explicit `if … then x = r else x = nil end` for boolean results |
| 27 | 24 Nov | a secret-value gate passed code that compares target health | skill evaluation, offline | the stub had no target, so the code path never ran | stub defines a target and fires target events in combat |
| 30 | 26 Nov | class icon showed on teammates in a battleground, never on enemies | player's report, then `/ezt why`: `class-secret` | `UnitClass` is `SecretWhenUnitIdentityRestricted`: secret for units outside your party/raid | `UnitName` is open for players in PvP (`SecretWhenUnitNameIdentityRestricted`) and `C_PvP.GetScoreInfo` `name`/`classToken` are `NeverSecret`: look the target up in the score table (`RequestBattlefieldScoreData`, `UPDATE_BATTLEFIELD_SCORE`) |
| 31 | 26 Nov | score-table lookup still missed every enemy (`not-in-scores`) | in game: player's screenshot of the scoreboard | on WoW Forever the second return of `UnitName` is the **surname**, not the realm, and the surname separator is a space (`Camelot/NameUtil.lua`); the code built "Name-Surname" | build "Name Surname", then "Name"; index the table by full name, name without a "-realm" suffix and first name; a first-name clash shows nothing. Seen working in game |

## Process lessons

- The player (not the model) drives the game; the model reads SavedVariables, `taint.log` and screenshots afterwards.
- Every claim in a status report is tagged static / simulated / in game. "Not run" is a valid status; "works" without in-game evidence is not.
- A gate's "method exists" proves the name is in the client, not that this object type has it — the client is the last word.
- Feasibility comes before code: check that an API can deliver the feature before building a convincing imitation of it (#24).
