# Review checklist

Apply to every diff before commit and to the whole addon before release. Record each item as OK, ISSUE (with file:line) or N/A. Severity: **blocker** (taint, Lua error, data loss, licence), **major** (wrong behaviour in a common path), **minor** (style, perf in cold path).

## A. Target and structure
- [ ] `## Interface` matches the measured client value; multi-flavor handled deliberately.
- [ ] Every TOC file exists; load order puts locale/lang and core before modules; XML templates before the Lua that uses them.
- [ ] Folder name == TOC name; paths built from `addonName`, not hard-coded.
- [ ] File starts with `local addonName, ns = ...`; no accidental globals (luacheck clean with explicit `globals`/`read_globals`).
- [ ] Every API, event, template and XML attribute used exists in the target client's source (not assumed from memory). Removed globals (see `client-targets.md`) not called.
- [ ] Lua 5.1 syntax only; locals defined before first use.
- [ ] No `a and b or c` where `b` can be `false` or `nil` (boolean API results silently become `c`).
- [ ] No call to a name that exists only in a Blizzard deprecation shim (`Blizzard_Deprecated*`).
- [ ] Return positions of multi-return APIs checked against the docs (e.g. combat-log tuple: 12 = spell ID, not amount).

## B. Taint and combat
- [ ] No wrapping/replacing of Blizzard functions or secure-button methods; `hooksecurefunc` used instead.
- [ ] No fields written onto Blizzard frames/tables — including through locals and function arguments that hold Blizzard buttons; side tables used.
- [ ] Every `SetAttribute`, secure-frame creation, `SetPoint`/`SetScale`/`Show`/`Hide` on protected frames, and override binding is out of combat or queued to `PLAYER_REGEN_ENABLED`.
- [ ] Addon-made buttons from Blizzard templates are removed from shared Blizzard event lists (or the template choice is justified).
- [ ] Click registration does not route right-click through tainted `self.action`.
- [ ] User commands that need protected work refuse clearly in combat.

## C. Secret values (modern Mainline)
- [ ] No comparison, arithmetic, concatenation, `tostring`, table-key use or string matching on values that can be secret (health, power, cooldowns, auras, spellcast IDs, tooltip text, damage meter) without `issecretvalue` guard.
- [ ] Numbers shown through `SetFormattedText` / `BreakUpLargeNumbers`, not `..`.
- [ ] Thresholds use curves or plain-only paths; cooldowns use duration objects.
- [ ] No `COMBAT_LOG_EVENT(_UNFILTERED)` registration on modern clients.
- [ ] Secrets never stored in SavedVariables.

## D. Events and lifecycle
- [ ] Handlers guarded (pcall + log + error handler); one failure cannot stop other handlers.
- [ ] SavedVariables read at `ADDON_LOADED` for this addon; `Settings.*` after `SETTINGS_LOADED`.
- [ ] `PLAYER_ENTERING_WORLD` re-entry (every loading screen) handled idempotently.
- [ ] Unit events use `RegisterUnitEvent`; OnUpdate throttled or frame hidden when idle; no per-frame allocations.
- [ ] Essential build before decoration; Blizzard UI hidden only after own build succeeded (or the opposite is justified in a comment).

## E. Data
- [ ] Defaults nil-checked (no `x = x or true`); migrations one-way, versioned, commented with reason.
- [ ] CVars changed only with backup and restore; not in combat.
- [ ] Log capped and deduplicated.

## F. UI
- [ ] Fonts cover the target languages (Friz Quadrata lacks ğ ş İ and others).
- [ ] Media paths exist, TGA uncompressed; flipbook grids match textures; flipbooks ≥ 24 fps.
- [ ] Scale and positions survive UI scale changes; movers lock in combat.
- [ ] Every effect has an off switch and a test trigger.

## G. Other addons and licences
- [ ] Integration uses documented extension points or defensive `pcall` imports; no overwriting other packs.
- [ ] Side effects on shared CVars/widgets are restored.
- [ ] Licences present for code, art and fonts; GPL derivatives carry licence + NOTICE.

## H. Evidence
- [ ] Offline gates PASS (or CHECK explained) and negative run all red — paste the summary; list unproven arms.
- [ ] In-game result listed separately; untested paths listed as "not run".
