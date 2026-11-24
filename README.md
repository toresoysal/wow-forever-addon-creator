# WoW Forever Addon Creator

A Claude Code plugin for building World of Warcraft addons that survive the live client: one skill, three specialist agents and offline test gates.

It was distilled from addons we built with Claude Code and then tested in the WoW Forever client (Interface 16001) in November 2026: a school-coloured cast bar with proc alerts, Diablo-style orbs and unit frames, a smart bag, a target range arrow, and a Turkish translation layer on top of Questie. It also kept one failure: ground range rings faked as a screen ellipse, which became the skill's feasibility rule. Every rule exists because one of those addons broke without it; the dated cases are in `skills/wow-forever-addon-creator/references/field-notes.md`.

The addons themselves are free and open on GitHub: [devsoy-wow-forever-addon-pack](https://github.com/toresoysal/devsoy-wow-forever-addon-pack).

## Why it exists

The WoW API a language model remembers is mostly older Classic and Retail tutorial code. Modern clients reject a lot of it. WoW Forever and Retail Midnight (12.x) belong to the same modern Mainline family: secret values, `C_` namespaces, Edit Mode, a combat log that addons cannot read. Code that looks right compiles, loads, and then breaks in combat with "Interface action failed because of an AddOn".

This plugin makes Claude treat its memory as a guess and the client as the judge: pin the client version first, check every API name against the client's own UI source, run the addon on an offline stub, then hand you a short in-game test.

## Two ways to use it

**1. Build an addon from scratch.** Describe what you want; the skill scaffolds the addon, the agents build it, the gates test it.

The addons below came first: the skill was distilled from building them, not used to make them from the start. EZ Target, the newest, was checked with the skill's gates on every version.

| Addon (in the pack repo) | What it does | What the skill had to get right |
|---|---|---|
| FelCast | Cast bar dressed by spell school, proc arcs, DoT warning, healing numbers | Combat log closed to addons; secret values in combat |
| Forever Diablo UI | Action bars and Diablo-style health and mana orbs | Not tainting Blizzard's secure action buttons |
| Forever Smart Bag | All bags in one window, grouped by type | Secure item use from a custom bag window |
| EZ Target | Arrow over your target: green, yellow or red by spell range | Ground drawing is impossible, so it reads the game's own range check |

**2. Adapt an addon that already exists.** The Forever Turkish Pack sits on top of Questie and translates its interface and quest text. Changing someone else's addon without breaking it on their next update is its own skill: see `references/hooking-other-addons.md` (hook the function that actually runs, keep your changes reversible, detect when the host addon changes).

## The agents

The skill holds the rules; three agents divide the work, so each one reads only the references it needs.

| Agent | Takes | Does not take | Runs |
|---|---|---|---|
| `wow-ui-builder` | Frames, textures and TGA media, status bars, orb fills with masks, FlipBook animations, fonts with non-Latin letters, scaling, movable frames, options windows | Combat logic, protected actions | The gates after every change |
| `wow-mechanics-engineer` | Events, combat state, secure buttons, secret values, cast/aura/cooldown/proc tracking, SavedVariables defaults and migrations, slash commands, hooking or translating another addon | Visual styling | The gates, plus an in-game test script for anything the stub cannot prove |
| `wow-addon-reviewer` | Read-only review before a commit, release or upload | Editing code | The checklist, the gates and the static scan; returns ranked findings with `file:line` and evidence |

A typical run: the UI builder and the mechanics engineer build their halves, then the reviewer goes over the result with fresh eyes. The reviewer is invoked proactively after the other two change an addon.

## The gates

`scripts/check_addon.py` runs eight offline checks:

1. TOC: a numeric interface line, and every listed file present.
2. luacheck.
3. Lua 5.1 compile.
4. API names against the client's UI source (`--ui-source`), including names that only exist as deprecation shims.
5. Smoke load on a stub client: login, a target, entering and leaving combat.
6. Global leaks.
7. Secret-value misuse: arithmetic or comparisons on values the client hides in combat.
8. Taint: fields written onto Blizzard frames, protected changes during combat.

`--negative` breaks a temporary copy of the addon eight ways and requires every gate to turn red. A gate that cannot fail proves nothing.

`scripts/review_scan.py` adds static red flags: combat-log registration, fields on Blizzard frames, removed globals, the Lua `a and b or c` trap when `b` can be false, unguarded protected calls, Lua 5.2 syntax.

## Measured

We ran two tasks with and without the skill, each with its own agent and an automatic grader:

| Task | With the skill | Without |
|---|---|---|
| Build "TargetPulse", an addon that must not error in combat | 11/11 | 10/11: compared a secret health value in combat |
| Review "TargetAlert", written by another AI (6 hidden defects + 1 bonus) | 8/8 | 5/8: missed the closed combat log and the secret health value |

One run per task: this shows a direction, not a statistic. The run without the skill also found something the skill had missed at first, and that lesson went back into the skill.

## Install

```bash
claude plugin marketplace add toresoysal/wow-forever-addon-creator
claude plugin install wow-forever-addon-creator@wow-forever-addon-creator
```

Optional tools: `pip install lupa` (Lua 5.1 compile and smoke gates) and `luacheck` on PATH. Without them those gates report "not run" instead of passing.

## Use

Ask Claude Code things like:

- "Make a WoW Forever addon that shows my mana as a Diablo-style orb."
- "My addon causes 'Interface action failed because of an AddOn' in combat. Find out why."
- "Translate Questie's quest text without forking Questie."
- "Review this addon before I upload it."

The skill pins the client first (`/run print(GetBuildInfo())`), builds with the reference rules, runs the gates and gives you an in-game test script. It reports results in three buckets (static, simulated, in game) and marks anything untested as "not run".

## What it does not do

- The offline stub is not the game. PASS means the addon's own logic runs; only the client proves an API works.
- It does not replace an API index. Pair it with an API MCP server such as [hated-wow-mcp](https://github.com/RdyGaming/hated-wow-mcp) or the Blizzard UI source mirror [Gethe/wow-ui-source](https://github.com/Gethe/wow-ui-source).
- The static scan cannot see fields written onto Blizzard frames through local variables; the taint gate catches them at run time for the frames the stub models, and the reviewer traces the rest by hand.
- The API gate proves a name occurs in the client's UI source, not that the object you call it on has it.

## Related work

- [JBurlison/WoWAddonAPIAgents](https://github.com/JBurlison/WoWAddonAPIAgents): a broad multi-client API skill pack with Forever targets; complementary to this plugin's in-game-tested rules and gates.
- [Ketho/vscode-wow-api](https://github.com/Ketho/vscode-wow-api): LuaLS annotations for editor IntelliSense.

## Licence

MIT. Made by Devsoy · [wowforeveraddon.com](https://www.wowforeveraddon.com). World of Warcraft is a trademark of Blizzard Entertainment, Inc.; this project is not affiliated with Blizzard.
