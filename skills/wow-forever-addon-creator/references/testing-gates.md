# Offline gates and negative tests

## Why

An LLM can write a thousand lines of plausible addon Lua in minutes. The client then rejects it for reasons the code does not show (taint, secrets, missing APIs). Offline gates catch the cheap failures before the player loads the game; in-game testing catches the rest. Each gate must be proven able to fail — and must be able to *see* the code it judges (a gate that never reaches the code is a false green).

## The gates in `scripts/check_addon.py`

| Gate | Catches | Does not catch |
|---|---|---|
| toc | missing listed files, no/odd Interface line, TOC name ≠ folder | a wrong but numeric interface number |
| luacheck | undefined/leaked globals, unused vars, shadowing, later-defined locals | API existence |
| compile | `goto`, `//`, `<const>`, other 5.2+ syntax (luacheck accepts some of these) | runtime errors |
| api | `:Method(`, bare global calls, registered events and `CreateFrame` templates that do not occur in the client's UI source; names defined only in `Blizzard_Deprecated*` shims | a name that exists but not on that object type; behaviour |
| smoke | errors at load, login, target change, combat enter/leave, slash commands | real API behaviour |
| globals | accidental globals (hints when a `…DB` global is not in the TOC) | writes into existing Blizzard tables (see taint) |
| secret | comparing / arithmetic / concatenating values the stub returns as secret in combat | `secret == 0` across types (Lua 5.1 never calls `__eq` there) |
| taint | fields written onto stubbed Blizzard frames (ActionButton1-12, MultiBar…, PlayerFrame, TargetFrame), also through locals; `SetAttribute`/`Show`/`Hide`/`SetScale` on secure frames in combat | Blizzard frames the stub does not model; taint through shared tables |

Statuses: PASS, FAIL, CHECK, NOT RUN. A missing tool or input is NOT RUN, never PASS. CHECK means the code called something the stub does not define: confirm it exists in the client, then add a stand-in with `--stub-extra extra.lua` (the file receives `harness` as `...`).

### How the API gate decides

It collects names from the UI source in three ways: documented names (`Name = "…"` in the generated API docs), Blizzard call sites (`:Method(` anywhere in Blizzard Lua/XML) and definitions (`function X`, `X =`). Call sites matter: C-side widget methods such as `GameTooltip:AddDoubleLine` are not in the generated docs, and an earlier docs-only gate wrongly called that method missing. Deprecation shims are collected separately because a shim in the source is not proof the function exists in game (`CombatLogGetCurrentEventInfo` was nil on Forever although a shim defines it).

## The stub (`assets/stub.lua`)

- `CreateFrame` returns objects whose unknown Capitalised members are permissive stand-ins: callable (returning `0` for `GetNum*`/`*Count`, `false` for `Is*/Has*/Can*`, a new stand-in for `Create*`) and indexable (so `frame.Sheet:SetVertexColor()` from an XML template's `parentKey` keeps running).
- Common getters return numbers (`GetFrameLevel`, `GetPoint`, `GetFont`, `GetWidth`…).
- Events registered on frames are delivered with `harness.fire(event, ...)`; `C_Timer` callbacks queue and run with `harness.flush()`; OnUpdate runs with `harness.update(dt)`.
- `InCombatLockdown()` returns `harness.combat`; `UnitExists("target")` is true, so target code paths run.
- Health/power/cooldown/aura stand-ins return `harness.SECRET` in combat; its metatable raises on every operator.
- Blizzard frames record field writes; secure frames record protected changes in combat.
- Unknown `C_*` namespaces resolve to permissive stand-ins (API existence is the api gate's job).

Keep project stand-ins in a separate `--stub-extra` file; a stub proves only your own logic.

## Negative tests

`check_addon.py --negative` refuses to start on a base with a FAIL (a red base proves nothing), then copies the addon to a temp folder and appends one break per arm:

| Arm | Must turn red |
|---|---|
| `goto skip ::skip::` in the first Lua file | compile |
| `local forgeUnusedLocal = 1` | luacheck |
| `UIParent:ForgeNoSuchMethod()` inside a local function | api |
| `ForgeNegativeLeak = 1` | globals |
| a login handler that calls `error(...)` | smoke |
| a combat-start handler comparing `UnitHealth("player") < 1` | secret |
| a login handler doing `local b = _G["ActionButton" .. 1]; b.forgeFlag = true` | taint |
| an extra `ForgeMissingFile.lua` line in the TOC | toc |

An arm whose gate cannot run here (no luacheck, no `--ui-source`) is reported as *unproven*. If a gate stays green under its arm the script prints `NEGATIVE ESCAPED` and exits 1.

## Writing project gates (patterns that worked)

- **Break by exact text**: each arm is `(name, file, old, new)` and asserts `old` occurs exactly once, so the arm cannot silently stop applying after a refactor.
- **Known-answer scenario for math-heavy code**: give the code a fake world with a known answer and require it to recover that answer (Range Rings 0.2.0 reconstructs a known camera homography to < 0.01 px from four simulated navigation samples), then break each step of the pipeline (axis scale, perspective divide, unit conversion) and require red.
- **XML gate**: well-formed, and every tag and attribute appears somewhere in Blizzard's XML.
- **Isolated load per addon** in a fresh Lua state: catches one addon relying on another's globals.
- **Copy equals source** when one tree generates several addons.
- **Re-open the artefact you ship** (zip, generated Lua) and compare it with the source by bytes or round trip.
- **Prove a checker against a known-bad build** (an older broken zip is a perfect negative fixture).

## Test-harness traps we hit

- A stub with no target unit let a secret-value gate pass code that compares target health — the code path never ran. Measure what the gate actually exercised.
- A refactor broke an older feature (first-person hiding) while the new feature's tests were green; keep the old scenarios and rerun them after every change.
- A negative arm that breaks a line the scenario never reaches stays green (twice on 24 Nov: a passive spell whose range was already covered; a hide path that ran after the dot was already hidden). Make the scenario put the code in the state the arm needs first, then break it.
- Clearing the whole error list between steps blinded a negative arm.
- Loading two single-copy packages into one Lua state made the second sleep; the guard was right, the test was wrong — isolate states.
- A shell heredoc ate backslashes in generated code; write generated files from a script, not through the shell.
- A piped command's exit code is the last command's (`script | tail`); write logs to a file and read them.
