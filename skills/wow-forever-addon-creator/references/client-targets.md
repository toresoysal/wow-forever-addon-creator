# Client targets

Last reviewed 2026-11-24. Interface numbers move with every patch — always confirm in the client.

## Detect, do not remember

```lua
/run print(GetBuildInfo())          -- version, build, date, interface
/run print(select(4, GetBuildInfo()))  -- interface number only
/run print(WOW_PROJECT_ID)          -- project id; compare with WOW_PROJECT_* constants
```

Write the measured interface into `## Interface:`. One addon may list several numbers on one line (`## Interface: 120007, 16001`) when the client supports it; otherwise ship one TOC per flavor with suffixes (`MyAddon_Mainline.toc`, `MyAddon_Vanilla.toc`, ...). Do not copy Blizzard-internal directives such as `[Family]`, `[Game]` or `AllowLoadGameType` into addon TOCs.

## Families

| Client | Engine family | Interface (as observed) | Notes |
|---|---|---|---|
| **WoW Forever** | Modern Mainline (project "camelot") | 16001 on build 1.60.1.x (Nov 2026) | Classic-like *game*, modern *API*: secret values, `C_` namespaces, Edit Mode, duration objects, closed combat log. Classic Era tutorials are wrong here. |
| **Retail Midnight** | Mainline 12.x | *reported*: 120000 (12.0.0), 120001 (12.0.1), 120005, 120007 (12.0.7, Jun 2026) — newer since | *Reported* (Warcraft Wiki "Patch 12.0.0/API changes"): secret values, CLEU registration forbidden, "load out of date" disabled for older TOCs. Not measured by this skill's authors. |
| **Classic Era / Anniversary / SoD** | Classic | 11xxx family | Older API surface; many `C_` namespaces absent or partial. |
| **MoP/Cata Classic** | Classic progression | 5xxxx / 4xxxx | Mixed. |

The Forever row is the one this skill was proven on. For the others, the rules about taint and combat lockdown still hold; the secret-value rules apply to the modern Mainline family.

## Forever-specific facts (measured in game, Nov 2026)

- Present: `C_LossOfControl`, `C_Spell.GetSpellCooldownDuration`, `C_CurveUtil`, `C_CooldownViewer`, `EditModeManagerFrame`, `C_Traits`, `C_ClassTalents`, `C_NamePlate`, `C_AddOns`, `C_CurrencyInfo`, `C_Item`.
- Missing globals that old code calls (nil in the client): `GetItemCount` (use `C_Item.GetItemCount`), `GetCoinTextureString` (use `C_CurrencyInfo.GetCoinTextureString`), `CombatLogGetCurrentEventInfo`.
- **Deprecation shims are not a promise.** `CombatLogGetCurrentEventInfo` is defined in the Forever source by `Blizzard_DeprecatedCombatLog` ("will be removed at the next expansion") and was still nil in game. A name that exists only in a `Blizzard_Deprecated*` addon must be treated as absent; `check_addon.py`'s API gate flags it.
- **Absent from the docs is not absent from the client.** An earlier project gate called `GameTooltip:AddDoubleLine` missing because it is not in the generated API docs; Blizzard's own Forever code calls it in dozens of files, so it exists (C-side widget method). Search Blizzard call sites as well as the docs before declaring an API missing.
- `IsCombatLogRestricted()` returns true; registering `COMBAT_LOG_EVENT_UNFILTERED` delivered 0 events and the client showed "<Addon> has been blocked".
- Auras are unreadable in combat on tainted paths ("Auras cannot be accessed when secret while tainted").
- One specialization per class; `GetSpecializationInfo` returns the class name. Read talent trees through `C_ClassTalents.GetActiveConfigID()` → `C_Traits`.
- Characters can have surnames: use `GetUnitName(unit, true)` for display, not `UnitName`.
- Some Blizzard UI is excluded for the project (`[ExcludeLoadGameType camelot]`), e.g. the soul-shard bar; Soul Shards are bag items. Blizzard frame layouts differ from Classic — measure from the client's own UI source.
- No world camera for addons: every camera function in the Forever source belongs to ModelScene/SimpleModel (UI 3D frames), Commentator (spectator) or the barber shop. No ground drawing. The one official world→screen path is the map user waypoint's navigation frame (`C_Navigation.GetFrame()`); see `ui-construction.md`, "Drawing in the world".
- `UnitPosition`, `C_Map.GetPlayerMapPosition` and `C_Map.SetUserWaypoint` exist (SecretArguments "AllowedWhenUntainted"); availability in instances and in combat not measured.

## Removed or moved globals (common LLM mistakes on modern clients)

Verify each in the target client's source before use; this list is a starting point, not exhaustive.

| Old call | Modern replacement |
|---|---|
| `GetAddOnMetadata` | `C_AddOns.GetAddOnMetadata` |
| `GetSpellInfo` | `C_Spell.GetSpellInfo` (returns a table) |
| `GetSpellCooldown` | `C_Spell.GetSpellCooldown` / `GetSpellCooldownDuration` |
| `UnitAura`, `UnitBuff`, `UnitDebuff` | `C_UnitAuras.*` (secret-aware) |
| `GetItemCount`, `GetItemInfo` | `C_Item.*` |
| `GetCoinTextureString` | `C_CurrencyInfo.GetCoinTextureString` |
| `InterfaceOptions_AddCategory` | `Settings.RegisterCanvasLayoutCategory` or a custom window |
| `COMBAT_LOG_EVENT_UNFILTERED` | `UNIT_COMBAT`, `UNIT_SPELLCAST_*` |

## Sources worth checking

- Blizzard UI source mirror per branch: `github.com/Gethe/wow-ui-source` (branches include live, classic_era, forever).
- Warcraft Wiki API change pages, e.g. `warcraft.wiki.gg/wiki/Patch_12.0.0/API_changes`.
- Ketho's `vscode-wow-api` annotations (LuaLS IntelliSense).
- MCP servers that index these: `hated-wow-mcp` (Forever, Retail, Classic indexes), `wow-api-mcp`.
