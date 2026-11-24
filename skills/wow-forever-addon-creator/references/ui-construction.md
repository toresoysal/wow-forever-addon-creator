# UI construction

## Media

- Ship art as **uncompressed 32-bit TGA** (or BLP); power-of-two sizes are safest. Path: `"Interface\\AddOns\\" .. addonName .. "\\Media\\name"` (extension optional). Build the path from `addonName` so the same code works when the folder is renamed.
- Paint art **near-white/grey and tint in code** (`SetVertexColor`): one texture set serves every theme, school colour or class colour.
- Author art at 2–5× its on-screen size; the client downsamples cleanly, it does not upsample cleanly.
- A **new** media file is only found after a full game restart; `/reload` is not enough.
- Track third-party art in a licences file (source URL, author, licence). Prefer CC0; reject "free" assets without a clear licence. Packaging should fail when a third-party file is missing from that list.

## Orb / liquid fill (Diablo-style globes)

A vertical StatusBar whose fill texture is masked round; effects ride on the fill edge without reading the (possibly secret) value:

```lua
local bar = CreateFrame("StatusBar", nil, parent)
bar:SetOrientation("VERTICAL")
bar:SetStatusBarTexture(MEDIA .. "orb-liquid")
local fill = bar:GetStatusBarTexture()
local mask = bar:CreateMaskTexture()
mask:SetAllPoints(bar)
mask:SetTexture(MEDIA .. "orb-fill", "CLAMPTOBLACKADDITIVE", "CLAMPTOBLACKADDITIVE")
fill:AddMaskTexture(mask)

local clip = CreateFrame("Frame", nil, bar)            -- swirl/bubbles live here
clip:SetPoint("TOPLEFT", fill, "TOPLEFT", 0, 0)        -- follows the liquid level
clip:SetPoint("BOTTOMRIGHT", bar, "BOTTOMRIGHT", 0, 0)
clip:SetClipsChildren(true)
bar:SetValue(UnitPower("player"))                      -- secret is fine here
```

## Animation

- **Sprite-sheet flipbooks must be declared in XML** (`<FlipBook>` inside an `<AnimationGroup>` with `flipBookRows`, `flipBookColumns`, `flipBookFrames`). `CreateAnimation("TextureCoordTranslation")` from Lua returns an animation without `SetOffset`; building it in Lua failed. Load the XML in the TOC before the Lua that uses its templates.
- Keep the grid in the XML equal to the real texture grid — add a check that compares them, because a hand-typed multiplier silently drifts when the art is re-exported.
- A 9 fps flipbook looked frozen in game; ~24 fps looked right. Start there and judge by eye.
- Moving secure frames in combat: a `Translation` animation instead of `SetPoint` (used in shipped code, not separately measured).
- Smooth sub-pixel shrinking: `tex:SetSnapToPixelGrid(false)` and `tex:SetTexelSnappingBias(0)`.
- Motion budget: a few signature effects, `transform`-like changes (alpha, scale, translation) only, honour a user toggle to turn effects off.

## Fonts

- `Fonts\\FRIZQT__.TTF` (Friz Quadrata) cannot draw many letters outside Latin-1 (Turkish ğ Ğ ş Ş İ render as boxes — measured). `Fonts\\ARIALN.TTF` draws them. For full coverage bundle an OFL-licensed font with its `OFL.txt`.
- Player names may be Cyrillic/CJK: use `STANDARD_TEXT_FONT` for unit names.
- Template font strings keep the template font: re-font them explicitly after creation.
- To change fonts only where needed, detect UTF-8 lead bytes (e.g. `text:find("[\195-\197][\128-\191]")`) — but check the text is not secret first.

## Scaling and positions

- Store positions in UIParent units relative to a stable anchor point; divide by the frame's own scale when restoring.
- A frame parented to a Blizzard bar inherits its scale: `scale * UIParent:GetEffectiveScale() / parent:GetEffectiveScale()` to get a visual size independent of the parent.
- Recompute screen-relative sizes on `UI_SCALE_CHANGED` and `DISPLAY_SIZE_CHANGED`.

## Movers and lock

- A dedicated anchor frame: `SetMovable(true)`, `RegisterForDrag("LeftButton")`, `SetClampedToScreen(true)`, a tinted overlay while unlocked, mouse enabled only while unlocked.
- Lock automatically on `PLAYER_REGEN_DISABLED`; refuse dragging secure frames in combat.
- Optional grid snap on drag stop.

## Options window

- A hand-built window works everywhere; `Settings.RegisterCanvasLayoutCategory` is the modern native route on Mainline clients. Pick one per client and verify the API exists.
- `UISliderTemplateWithLabels` + `slider:SetObeyStepOnDrag(true)` (note the spelling — `SetObeyStepsOnDrag` does not exist; an API gate caught it).
- Snap slider values: `math.floor(v * 100 + 0.5) / 100` (`6 * 0.05` is `0.30000000000000004`).
- `tinsert(UISpecialFrames, frame:GetName())` makes ESC close a named window.
- Give every visual a **test button** (and a slash form): users want to see the effect without waiting for a proc or a fight.

## Drawing in the world (range rings, ground markers)

Addons cannot draw on the ground and cannot read the world camera (pitch, distance, field of view). Two attempts, Nov 2026:

1. **Screen-space ellipse, calibrated once** (Range Rings 0.1.0): looked wrong in game — camera pitch and slopes break it (field note 24). Do not ship this as "ground rings".
2. **Projection through the navigation frame** (Range Rings 0.2.0, *seen in game 24 Nov: perspective correct, but rings float above the ground, look too large, and the minimap waypoint pin spins because the waypoint moves every frame — not shippable; opt-in only*): `C_Map.SetUserWaypoint` at points around the player, read `C_Navigation.GetFrame():GetCenter()` (the client's own projection of that world point), solve a ground→screen homography from four samples, draw rings as `Line` regions. Costs: it borrows the player's map waypoint and super-tracking (save and restore them), and the minimap pin moves. Offline it reconstructs a known camera to < 0.01 px; whether the client's navigation frame behaves this way is the open question.

Before building anything "in the world", run the feasibility step in SKILL.md and tell the user these limits up front.

## Decorating a nameplate (range dot, target arrow)

- Get the frame with `C_NamePlate.GetNamePlateForUnit("target", false)`; it is nil for forbidden (instance) plates and when plates are off. Read `plate.UnitFrame.healthBar` (Forever sets it in `Blizzard_NamePlateUnitFrame.lua`) only to anchor.
- Keep your frames parented to `UIParent` and attach with `SetPoint(..., plate, ...)`. Do not reparent into the plate and do not write fields on it.
- Re-anchor on `PLAYER_TARGET_CHANGED`, `NAME_PLATE_UNIT_ADDED` and `NAME_PLATE_UNIT_REMOVED`: the same unit can get a different plate frame.
- Game art works well for markers: `NPE_ArrowDown` / `NPE_ArrowDownGlow` (Blizzard's tutorial arrow) with a looping `Translation` bob; a round dot is a colour texture masked with `Interface\CharacterFrame\TempPortraitAlphaMask`.
- Status: measured in game (WoW Forever, 24 Nov 2026, Range Rings 0.4.0): the dot sits left of the target's health bar and switches red / yellow / green at the right distances, also in combat; the arrow shows above the target. Not checked in instances (forbidden plates). Range Rings 0.4.3 (same evening): the arrow itself tinted by range and a quest `!` from `C_QuestLog.UnitIsRelatedToActiveQuest` (atlas `QuestNormal`) both seen working on a quest mob, in and out of combat.

## Replacing Blizzard UI

Hide Blizzard frames only after your replacement built successfully, keep them hidden with `hooksecurefunc` on the methods Blizzard uses to show them, and give the user a command to restore Blizzard's frame.
