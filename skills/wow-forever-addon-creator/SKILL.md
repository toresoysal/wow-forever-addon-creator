---
name: wow-forever-addon-creator
description: Build, debug, review and package World of Warcraft addons (Lua 5.1, .toc, XML, SavedVariables) for WoW Forever, Retail 12.x and Classic, with rules tested in the live client for taint, combat lockdown and secret values. This skill should be used when the user wants to create or port a WoW addon, fix "Interface action failed because of an AddOn", ADDON_ACTION_BLOCKED/FORBIDDEN or secret-value Lua errors, build cast bars, unit frames, orbs or bag windows, extend another addon such as Questie without forking it, review addon code, or package an addon zip — including when they only say "wow addon", "addon yap", ".toc", "taint" or name a WoW API like UnitHealth or CreateFrame.
version: 0.2.0
---

# WoW Forever Addon Creator

Distilled from addons built with Claude Code and then checked in the live WoW Forever client in November 2026: a school-coloured cast bar with proc alerts, Diablo-style orbs and unit frames, a smart bag and a Questie translation layer — and one failure, ground range rings, which taught the feasibility rule below. Every rule exists because something broke without it; the cases are in `references/field-notes.md`.

The single most important fact: **the WoW API an LLM remembers is mostly older Classic/Retail tutorial code, and modern clients reject a lot of it.** WoW Forever (Interface 16001) and Retail Midnight (12.x) are the same modern Mainline family: secret values, `C_` namespaces, Edit Mode, duration objects, a combat log closed to addons. Treat memory as a hypothesis and the client's own UI source as the authority — and the client itself as the final word.

Scripts live next to this file. From another working directory call them as `python "${CLAUDE_PLUGIN_ROOT}/skills/wow-forever-addon-creator/scripts/<script>.py"` (on Windows `py -3`). Below they are written as `scripts/<script>.py`.

## Workflow

Follow the phases in order. Skipping phase 1 is the most common cause of addons that look correct and fail in game.

### 1. Pin the client and check feasibility

1. Ask which client the addon is for, or have the player run `/run print(GetBuildInfo())` (version, build, date, interface). `select(4, GetBuildInfo())` goes into `## Interface:`. Never write an interface number from memory.
2. Read `references/client-targets.md` for what differs between Forever, Retail and Classic Era.
3. **Feasibility before code.** For every part of the request, find the API that would deliver it in the client's UI source (a local checkout of `Gethe/wow-ui-source` on the matching branch, or an API MCP server such as `hated-wow-mcp`). If no API exists — drawing on the ground, reading the world camera, reading auras or the combat log in combat on modern clients — say so before writing anything and offer what is possible. A convincing fake (a screen-space ellipse pretending to be a ground ring) looks wrong in game; see field note 24.
4. Note which facts are *measured in game* and which are only *in the source or docs*. Keep that distinction in every report.

### 2. Scaffold

`python scripts/new_addon.py <AddonName> --interface <N> --out <dir>` copies `assets/template/`. `assets/template/Core.lua` is the canonical implementation of the patterns the references describe:

- `local addonName, ns = ...` namespace, no accidental globals
- one event hub, every handler wrapped in `ns.Guard` (pcall → log → `geterrorhandler()`)
- SavedVariables with nil-checked defaults and a version-keyed migration that skips fresh installs
- a disk-backed rolling log readable after `/reload`
- `ns.AfterCombat` for protected work, with a chat line when a command has to wait
- `.luacheckrc` with `std = "lua51"` and explicit global lists

### 3. Build — route work to the right specialist

| Work | Agent | Main references |
|---|---|---|
| Frames, textures, fonts, StatusBars, masks, FlipBooks, layout, scaling, movers, options window | `wow-ui-builder` | `ui-construction.md`, `client-targets.md` |
| Events, combat state, secure buttons, secret values, cast/aura/proc logic, SavedVariables, hooks into other addons | `wow-mechanics-engineer` | `taint-and-combat.md`, `secret-values.md`, `events-and-performance.md`, `savedvariables.md`, `hooking-other-addons.md` |
| Review before every commit or release | `wow-addon-reviewer` | `review-checklist.md` |

For a small change, do it directly and still apply the review checklist.

### 4. Gate offline

`python scripts/check_addon.py <addon-folder> --ui-source <wow-ui-source>/Interface [--luacheck <exe>]` runs eight gates:

| Gate | Fails on |
|---|---|
| toc | missing listed file, no/odd `## Interface`, TOC name ≠ folder |
| luacheck | lint errors with the addon's `.luacheckrc` |
| compile | Lua 5.2+ syntax (`goto`, `//`, `<const>`) |
| api | methods, globals, events, templates not found in the client's UI source — including names that exist only in Blizzard deprecation shims |
| smoke | Lua errors while loading every TOC file on `assets/stub.lua` and firing login, target, combat enter/leave and slash commands |
| globals | new globals that are not SavedVariables, `SLASH_*`, named frames or `.luacheckrc` globals (hints when a `…DB` global is missing from the TOC) |
| secret | comparing, adding or concatenating values the stub returns as secret in combat |
| taint | fields written onto Blizzard-owned frames (also through local variables); `SetAttribute`/`Show`/`Hide`/`SetScale` on secure frames in combat |

Statuses: **PASS**, **FAIL**, **CHECK** (the code calls something the stub does not know — either a real missing API or a stand-in to add with `--stub-extra`), **NOT RUN** (tool or input missing; never a pass). Exit codes: 0 pass, 1 fail, 2 check only, 3 nothing provable.

Then `python scripts/check_addon.py --negative <folder> <same options>`: it breaks a temporary copy eight ways, one per gate, and requires each gate to turn red. A gate that cannot fail proves nothing. Arms whose gate cannot run here are reported as unproven.

Then `python scripts/review_scan.py <folder>` for static leads (combat-log registration, removed globals, `x = x or true`, unguarded protected calls, secret arithmetic, Lua 5.2 syntax). Hits are leads, not verdicts.

The stub is not the client. PASS means the addon's own logic runs offline; it never means an API works in game.

### 5. Verify in game — the only real proof

1. New `.lua`/`.tga` file or TOC change → fully restart the game. Code-only change → `/reload`.
2. `/console scriptErrors 1`. For taint: `/console taintLog 1`, reproduce, `/reload`, read `Logs/taint.log`.
3. Test out of combat **and** in combat: enter combat, change target, level up, swap pages, hover buttons, open bags.
4. Read the addon's SavedVariables after `/reload` (`WTF/Account/<acct>/SavedVariables/<Addon>.lua`); the template's log lands there.
5. Report in three buckets — **static** (gates), **simulated** (stub), **in game** (what the player saw). Anything untested is "not run". Never write "works" for something only the stub saw.

### 6. Package

Read `references/packaging-release.md`: one top-level folder named exactly like the `.toc`, sorted entries with fixed timestamps for a reproducible SHA-256, licence file, reopen the zip and compare it with the source.

## Non-negotiable rules (short form)

1. **Never wrap or replace Blizzard functions or secure-button methods** (`SetAttribute`, `OnClick`, `UseAction`). Use `hooksecurefunc`. *(measured: field notes 3, 9)*
2. **Never write fields onto Blizzard frames or tables.** Keep state in a side table keyed by the frame. *(measured: 1, 6)*
3. **Protected work only out of combat**: secure frame creation, `SetAttribute`, `SetPoint`/`SetScale`/`Show` on secure frames, override bindings. Check `InCombatLockdown()` and queue to `PLAYER_REGEN_ENABLED`. *(measured: 4, 5)*
4. **Treat combat values as possibly secret** on modern clients: guard with `issecretvalue(v)` before comparing, adding, concatenating or using as a key. *(measured on Forever: 2, 11, 14, 18)*
5. **Do not register `COMBAT_LOG_EVENT_UNFILTERED` on modern clients.** Measured on Forever (field note 15); reported for Retail 12.x by Warcraft Wiki. Use `UNIT_COMBAT`, `UNIT_SPELLCAST_*` and secret-aware code.
6. **SavedVariables exist only after `ADDON_LOADED` for your addon**, reach disk only on `/reload` or logout, and defaults are nil-checked, never `db.x = db.x or true`.
7. **Build the essential part first, decoration last, each step guarded**; hide replaced Blizzard UI only after your build succeeded.
8. **Define local functions before their first use**; a later `local function` is a nil global at the call site.
9. **Lua 5.1 only**: no `goto`, `//`, integer division or `utf8` library.
10. **Check return positions of multi-return APIs in the docs** (`CombatLogGetCurrentEventInfo`, `UnitCastingInfo`, `GetBuildInfo`): position 12 of the combat-log tuple is the spell ID, not the amount.
11. **Fonts**: Friz Quadrata cannot draw many non-Latin-1 letters (Turkish ğ ş İ render as boxes, measured); use `Fonts\ARIALN.TTF` or a bundled OFL font.

## Additional resources

### Reference files (load on demand)

- **`references/client-targets.md`** — flavors, interface numbers, Forever vs Retail vs Classic Era, moved APIs, deprecation shims.
- **`references/taint-and-combat.md`** — how taint spreads, secure-button rules, combat queue, reading `taint.log`.
- **`references/secret-values.md`** — what may and may not touch secrets, curves, duration objects.
- **`references/events-and-performance.md`** — load order, unit events, OnUpdate throttling, hook storms.
- **`references/ui-construction.md`** — media, orb fills, FlipBooks, fonts, scaling, movers, options windows, drawing in the world.
- **`references/savedvariables.md`** — defaults, migrations, per-folder DB names, CVar backup.
- **`references/hooking-other-addons.md`** — extending an addon without forking it (Questie case), anchored patching.
- **`references/testing-gates.md`** — how each gate and negative arm works; project-specific gates.
- **`references/packaging-release.md`** — zip layout, reproducible SHA, licences, multi-language packages.
- **`references/review-checklist.md`** — the reviewer's checklist.
- **`references/field-notes.md`** — dated cases: symptom → evidence → cause → fix.

### Scripts

- **`scripts/new_addon.py`** — scaffold from `assets/template/`.
- **`scripts/check_addon.py`** — the eight offline gates; `--negative` proves they can fail.
- **`scripts/review_scan.py`** — static red-flag scan.

### Assets

- **`assets/template/`** — addon skeleton (`.toc`, `Log.lua`, `Core.lua`, example `Main.lua`, `.luacheckrc`).
- **`assets/stub.lua`** — offline API stand-in: secret sentinel, event bus, timers, combat flag, target unit, Blizzard action buttons that record taint.
