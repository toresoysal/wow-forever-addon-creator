# SavedVariables

## Lifecycle

- Declared in the TOC: `## SavedVariables: MyAddonDB` (account-wide) or `## SavedVariablesPerCharacter: MyAddonCharDB`.
- The global exists (or is nil on first run) when `ADDON_LOADED` fires with `arg1 == addonName`. Not earlier.
- Written to `WTF/Account/<account>/SavedVariables/<Addon>.lua` only on `/reload`, logout or exit. A crash loses the session's changes.
- Secrets, functions, frames and userdata cannot be saved. Save plain numbers, strings, booleans and tables of those.

## Defaults: nil-check, never `or`

`ApplyDefaults` in `assets/template/Core.lua` walks the defaults table recursively and fills only keys that are `nil`. `db.enabled = db.enabled or true` silently turns a saved `false` back into `true` every login.

## Migrations: one-way, keyed on a version

```lua
-- fresh install: the saved table was empty before defaults -> start at the current schema
local from = fresh and SCHEMA or (db.schema or 1)    -- old saves without a schema field are version 1
if from < 2 then db.textOut = false end             -- 2026-11-18: reason …
if from < 3 then db.scale = db.scale * 0.9 end      -- 2026-11-20: art re-exported larger
db.schema = SCHEMA
```

A fresh install must not run migrations meant for old data (a brand-new user would get `scale * 0.9`), and an old save that predates the `schema` field must run all of them. The template decides "fresh" by checking whether the saved table was empty before defaults were applied.

Write the reason and date in a comment next to each step; future readers need to know why a user's setting was changed.

## One codebase, several folders

Derive the DB name from the folder: `local db = _G[addonName .. "DB"]` with `## SavedVariables: <Folder>DB` written by the packager. This lets a TR and an EN package (or a dev copy) coexist. Add a single-copy guard so two installed copies do not both run:

```lua
local owner = _G["MyFamily_Running"]
ns.sleeping = owner ~= nil and owner ~= addonName
if not ns.sleeping then _G["MyFamily_Running"] = addonName end
```

## Touching the player's CVars

Back up the value before changing it (`db.cvarBackup[name] = C_CVar.GetCVar(name)`), restore it when the option is turned off, and never change CVars in combat.

## The log trick

A small rolling log stored in the DB (cap 200–400 lines) gives a readable record of what happened in the last session after `/reload`. Log errors once (dedupe), skip secret messages, and log the session start so a flood does not push it out.

## Moving settings between addon names

When an addon is renamed or split, migrate offline with a script that reads the old SavedVariables file and writes the new one while the game is closed; the game overwrites the files on exit.
